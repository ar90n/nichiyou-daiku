//! Helpers the golden-file tests share. The golden files hold the Rust
//! version's own output: `ND_BLESS=1 cargo test` writes what the tests get
//! over them, to review in the diff before committing.

// Each test crate uses a part of these
#![allow(dead_code)]

use std::fs;
use std::path::{Path, PathBuf};

use serde_json::Value;

pub fn blessing() -> bool {
    std::env::var_os("ND_BLESS").is_some()
}

/// JSON as the golden files keep it: indented, with a final newline.
pub fn pretty(value: &Value) -> String {
    serde_json::to_string_pretty(value).unwrap() + "\n"
}

/// Compares what a test got with the golden file at `path`, None meaning
/// the case has no such file; when blessing, writes or removes it instead.
pub fn check_golden(path: &Path, got: Option<&str>) -> Result<(), String> {
    if blessing() {
        match got {
            Some(text) => fs::write(path, text).unwrap(),
            None if path.exists() => fs::remove_file(path).unwrap(),
            None => {}
        }
        return Ok(());
    }
    let name = path.display();
    match (fs::read_to_string(path).ok(), got) {
        (None, None) => Ok(()),
        (Some(_), None) => Err(format!(
            "{name} belongs to no output any more; run with ND_BLESS=1 to remove it"
        )),
        (None, Some(_)) => Err(format!(
            "{name} is missing; run with ND_BLESS=1 to write it"
        )),
        (Some(want), Some(got)) if want == got => Ok(()),
        (Some(want), Some(got)) => {
            let same = want
                .lines()
                .zip(got.lines())
                .take_while(|(w, g)| w == g)
                .count();
            Err(format!(
                "{name} differs at line {}:\n  golden: {}\n  got:    {}",
                same + 1,
                want.lines().nth(same).unwrap_or("<end>"),
                got.lines().nth(same).unwrap_or("<end>")
            ))
        }
    }
}

/// The corpus's designs (`NAME.nd` in `dir`): their names and sources, by name.
pub fn corpus(dir: &Path) -> Vec<(String, String)> {
    let mut paths: Vec<PathBuf> = fs::read_dir(dir)
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

/// The examples' and the docs' designs, which also get images and solids.
pub fn shown(name: &str) -> bool {
    name.starts_with("example-") || name.starts_with("doc-")
}

/// Fails listing the first differences, if any, of `checked` comparisons.
pub fn assert_none(failures: &[String], checked: usize) {
    assert!(
        failures.is_empty(),
        "{} of {checked} differ (ND_BLESS=1 cargo test rewrites the golden files; review the diff):\n{}",
        failures.len(),
        failures[..failures.len().min(5)].join("\n")
    );
}
