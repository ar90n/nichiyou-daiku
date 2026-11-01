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

const CLI_DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/cli");
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

#[test]
fn report_prints_what_the_python_version_prints() {
    check_corpus(&["report", "-"], "cli-report.txt", |name| {
        golden(name, "cli-report.txt")
    });
}

#[derive(serde::Deserialize)]
struct OptionCase {
    name: String,
    args: Vec<String>,
    file: Option<String>,
    text: Option<String>,
}

/// TOML parsers word their errors differently: the words in the brackets
/// are the parser's.
fn toml_reason_hidden(text: &str) -> String {
    match (text.find("not valid TOML ("), text.find("). Write e.g.")) {
        (Some(start), Some(end)) if start < end => {
            format!("{}not valid TOML (…{}", &text[..start], &text[end..])
        }
        _ => text.to_string(),
    }
}

#[test]
fn options_print_what_the_python_version_prints() {
    let cases: Vec<OptionCase> =
        serde_json::from_str(&fs::read_to_string(Path::new(CLI_DIR).join("cases.json")).unwrap())
            .unwrap();
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let mut failures = Vec::new();
    for case in &cases {
        let stdin = match (&case.file, &case.text) {
            (Some(file), _) => fs::read_to_string(root.join(file)).unwrap(),
            (None, Some(text)) => text.clone(),
            (None, None) => String::new(),
        };
        let args: Vec<&str> = case.args.iter().map(String::as_str).collect();
        let want =
            fs::read_to_string(Path::new(CLI_DIR).join(format!("{}.txt", case.name))).unwrap();
        let got = run(&args, &stdin, Path::new(CLI_DIR));
        if !same_output(&toml_reason_hidden(&want), &toml_reason_hidden(&got)) {
            failures.push(format!("--- {}\n{want}\n+++\n{got}", case.name));
        }
    }
    assert!(
        failures.is_empty(),
        "{} option cases differ:\n{}",
        failures.len(),
        failures.join("\n")
    );
}

#[test]
fn a_report_written_to_a_file_is_the_one_printed() {
    let dir = std::env::temp_dir().join(format!("nd-cli-{}", std::process::id()));
    fs::create_dir_all(&dir).unwrap();
    let table = fs::read_to_string(
        Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../examples/nd_files/simple_table_compact.nd"),
    )
    .unwrap();
    let printed = run(&["report", "-"], &table, &dir);
    let written = run(&["report", "-o", "out/report.md", "-"], &table, &dir);
    assert_eq!(
        written,
        "exit: 0\n--- stdout\n--- stderr\nReport written to: out/report.md\n"
    );
    let report = fixed_date(&fs::read_to_string(dir.join("out/report.md")).unwrap());
    // Python's write_text adds no final newline; click.echo does
    assert_eq!(
        format!("exit: 0\n--- stdout\n{report}\n--- stderr\n"),
        printed
    );
    let refused = run(&["report", "-o", "out", "-"], &table, &dir);
    assert_eq!(
        refused,
        "exit: 1\n--- stdout\n--- stderr\nError: Output path is not a file: out\n"
    );
    fs::remove_dir_all(&dir).unwrap();
}
