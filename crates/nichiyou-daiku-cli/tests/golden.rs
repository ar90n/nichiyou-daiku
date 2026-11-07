//! What the CLI prints against the golden files: validate, validate --json
//! and report for every corpus case, and the option cases in tests/cli.

use std::fs;
use std::io::Write;
use std::path::Path;
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

/// Runs `args` on the corpus cases `wanted` picks, at least `least` of them,
/// and compares the output with NAME.<suffix>.
fn check_corpus(args: &[&str], suffix: &str, least: usize, wanted: impl Fn(&str) -> bool) {
    let (mut failures, mut checked) = (Vec::new(), 0);
    for (name, source) in common::corpus(Path::new(CORPUS)) {
        let got = wanted(&name).then(|| run(args, &source, Path::new(CORPUS)));
        checked += usize::from(got.is_some());
        let path = Path::new(CORPUS).join(format!("{name}.{suffix}"));
        if let Err(error) = common::check_golden(&path, got.as_deref()) {
            failures.push(error);
        }
    }
    assert!(checked >= least, "only {checked} cases for {suffix}");
    common::assert_none(&failures, checked);
}

#[test]
fn validate_prints_its_golden_files() {
    check_corpus(&["validate", "-"], "cli-validate.txt", 700, |_| true);
}

#[test]
fn validate_json_prints_the_core_s_report() {
    // The core's tests write NAME.validate.json, which may be mid-rewrite
    if common::blessing() {
        return;
    }
    let cases = common::corpus(Path::new(CORPUS));
    let mut failures = Vec::new();
    for (name, source) in &cases {
        let path = Path::new(CORPUS).join(format!("{name}.validate.json"));
        let report = fs::read_to_string(&path).unwrap();
        let valid: serde_json::Value = serde_json::from_str(&report).unwrap();
        let code = if valid["valid"] == true { 0 } else { 1 };
        let want = format!("exit: {code}\n--- stdout\n{report}--- stderr\n");
        let got = run(&["validate", "--json", "-"], source, Path::new(CORPUS));
        if want != got {
            failures.push(format!("{name}:\n{got}"));
        }
    }
    common::assert_none(&failures, cases.len());
}

#[test]
fn validate_json_prints_its_golden_files() {
    check_corpus(
        &["validate", "--json", "-"],
        "cli-validate-json.txt",
        9,
        |name| name.starts_with("example-"),
    );
}

#[test]
fn report_prints_its_golden_files() {
    check_corpus(&["report", "-"], "cli-report.txt", 700, |_| true);
}

#[derive(serde::Deserialize)]
struct OptionCase {
    name: String,
    args: Vec<String>,
    file: Option<String>,
    text: Option<String>,
}

#[test]
fn options_print_their_golden_files() {
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
        let got = run(&args, &stdin, Path::new(CLI_DIR));
        let path = Path::new(CLI_DIR).join(format!("{}.txt", case.name));
        if let Err(error) = common::check_golden(&path, Some(&got)) {
            failures.push(error);
        }
    }
    common::assert_none(&failures, cases.len());
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
    // The file has no final newline; printing adds one
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
