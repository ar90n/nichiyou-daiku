//! The CLI against what the Python version printed (tools/make_goldens.py
//! --cli): validate, validate --json and report for every corpus case, and
//! the option cases in tests/cli.

use std::collections::HashMap;
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

#[path = "../../nichiyou-daiku-core/tests/common/mod.rs"]
mod common;

const CORPUS: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../nichiyou-daiku-core/tests/corpus"
);

/// What the CLI prints, in the golden files' form, the report's date fixed.
fn run(args: &[&str], stdin: &str, dir: &Path) -> String {
    let mut child = Command::new(env!("CARGO_BIN_EXE_nichiyou-daiku"))
        .args(args)
        .current_dir(dir)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    // The CLI may stop before reading it all
    let _ = child.stdin.take().unwrap().write_all(stdin.as_bytes());
    let out = child.wait_with_output().unwrap();
    let text = format!(
        "exit: {}\n--- stdout\n{}--- stderr\n{}",
        out.status.code().unwrap(),
        String::from_utf8(out.stdout).unwrap(),
        String::from_utf8(out.stderr).unwrap()
    );
    fixed_date(&text)
}

fn fixed_date(text: &str) -> String {
    text.split_inclusive('\n')
        .map(|line| {
            let bare = line.trim_end_matches('\n');
            if bare.starts_with("*Generated on ") && bare.ends_with('*') {
                line.replacen(bare, "*Generated on DATE*", 1)
            } else {
                line.to_string()
            }
        })
        .collect()
}

/// The same output, but for the names of anonymous pieces (random UUIDs in
/// the Python version) and the syntax messages the corpus test allows.
fn same_output(expected: &str, actual: &str) -> bool {
    let expected = common::rename_uuids(expected, &mut HashMap::new());
    let actual = common::rename_uuids(actual, &mut HashMap::new());
    if expected == actual {
        return true;
    }
    let (e, a): (Vec<&str>, Vec<&str>) = (expected.lines().collect(), actual.lines().collect());
    e.len() == a.len()
        && e.iter().zip(&a).all(|(e, a)| {
            e == a || (e.contains("Syntax error at line") && common::same_syntax_message(e, a))
        })
}

fn corpus_cases() -> Vec<(String, String)> {
    let mut paths: Vec<PathBuf> = fs::read_dir(CORPUS)
        .unwrap()
        .map(|entry| entry.unwrap().path())
        .filter(|path| path.extension().is_some_and(|ext| ext == "nd"))
        .collect();
    paths.sort();
    paths
        .into_iter()
        .map(|path| {
            (
                path.file_stem().unwrap().to_string_lossy().into_owned(),
                fs::read_to_string(&path).unwrap(),
            )
        })
        .collect()
}

/// Run `args` on every corpus case and compare with NAME.<suffix>.
fn check_corpus(args: &[&str], suffix: &str, expected: impl Fn(&str) -> Option<String>) {
    let show = std::env::var("ND_CORPUS_SHOW").ok();
    let (mut failures, mut checked) = (Vec::new(), 0);
    for (name, source) in corpus_cases() {
        let Some(want) = expected(&name) else {
            continue;
        };
        checked += 1;
        let got = run(args, &source, Path::new(CORPUS));
        if !same_output(&want, &got) {
            if show.as_deref().is_some_and(|part| name.contains(part)) {
                println!("--- {name}\n{want}\n+++\n{got}");
            }
            failures.push(name);
        }
    }
    println!("{suffix}: {}/{checked}", checked - failures.len());
    assert!(
        failures.is_empty(),
        "{} cases differ (ND_CORPUS_SHOW=<name> shows one): {:?}",
        failures.len(),
        &failures[..failures.len().min(20)]
    );
}

fn golden(name: &str, suffix: &str) -> Option<String> {
    fs::read_to_string(Path::new(CORPUS).join(format!("{name}.{suffix}"))).ok()
}

#[test]
fn validate_prints_what_the_python_version_prints() {
    check_corpus(&["validate", "-"], "cli-validate.txt", |name| {
        golden(name, "cli-validate.txt")
    });
}

#[test]
fn validate_json_prints_the_python_reports_with_their_keys_in_order() {
    // NAME.validate.json keeps pydantic's key order; the CLI indents it by 2
    check_corpus(&["validate", "--json", "-"], "validate.json", |name| {
        let text = golden(name, "validate.json")?;
        let report: serde_json::Value = serde_json::from_str(&text).unwrap();
        let code = if report["valid"] == true { 0 } else { 1 };
        Some(format!(
            "exit: {code}\n--- stdout\n{}\n--- stderr\n",
            serde_json::to_string_pretty(&report).unwrap()
        ))
    });
}

#[test]
fn validate_json_is_the_text_the_python_cli_prints() {
    check_corpus(
        &["validate", "--json", "-"],
        "cli-validate-json.txt",
        |name| golden(name, "cli-validate-json.txt"),
    );
}
