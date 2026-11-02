//! The check image's labels and note match the Python version's
//! (NAME.render.json, written by tools/make_goldens.py --cli).

use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_drawing::render::render_sheet;
use serde_json::{Value, json};

#[path = "../../nichiyou-daiku-core/tests/common/mod.rs"]
mod common;

const CORPUS: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../nichiyou-daiku-core/tests/corpus"
);

#[test]
fn render_labels_and_notes_match_the_python_version() {
    let mut paths: Vec<PathBuf> = fs::read_dir(CORPUS)
        .unwrap()
        .map(|e| e.unwrap().path())
        .filter(|p| p.to_string_lossy().ends_with(".render.json"))
        .collect();
    paths.sort();
    let mut differ = Vec::new();
    for path in &paths {
        let want: Value = serde_json::from_str(&fs::read_to_string(path).unwrap()).unwrap();
        let source =
            fs::read_to_string(path.to_string_lossy().replace(".render.json", ".nd")).unwrap();
        let assembly = Assembly::of(nichiyou_daiku_core::dsl::parse(&source).unwrap()).unwrap();
        let sheet = render_sheet(&assembly, "case.nd", 1400);
        let labels: serde_json::Map<String, Value> = sheet
            .labels
            .iter()
            .filter(|(_, ids)| !ids.is_empty())
            .map(|(caption, ids)| (caption.to_string(), json!(ids)))
            .collect();
        let got = json!({"labels": labels, "unlabelled": sheet.unlabelled, "note": sheet.note});
        let want = common::normalize(want, &mut HashMap::new());
        let got = common::normalize(got, &mut HashMap::new());
        if want != got {
            differ.push(format!(
                "{}\n  python: {want}\n  rust:   {got}",
                path.display()
            ));
        }
    }
    assert!(
        paths.len() >= 20,
        "only {} render goldens: run tools/make_goldens.py --cli",
        paths.len()
    );
    assert!(
        differ.is_empty(),
        "{} of {} differ:\n{}",
        differ.len(),
        paths.len(),
        differ.join("\n")
    );
}
