//! The check image's labels and note for the examples' and the docs'
//! designs, against NAME.render.json.

use std::path::Path;

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_drawing::render::render_sheet;
use serde_json::{Value, json};

#[path = "../../nichiyou-daiku-core/tests/common/mod.rs"]
mod common;

const CORPUS: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../nichiyou-daiku-core/tests/corpus"
);

fn render(source: &str) -> String {
    let assembly = Assembly::of(nichiyou_daiku_core::dsl::parse(source).unwrap()).unwrap();
    let sheet = render_sheet(&assembly, "case.nd", 1400);
    let labels: serde_json::Map<String, Value> = sheet
        .labels
        .iter()
        .filter(|(_, ids)| !ids.is_empty())
        .map(|(caption, ids)| (caption.to_string(), json!(ids)))
        .collect();
    common::pretty(&json!({"labels": labels, "unlabelled": sheet.unlabelled, "note": sheet.note}))
}

#[test]
fn render_labels_and_notes_match_their_golden_files() {
    let (mut failures, mut checked) = (Vec::new(), 0);
    for (name, source) in common::corpus(Path::new(CORPUS)) {
        let got = common::shown(&name).then(|| render(&source));
        checked += usize::from(got.is_some());
        let path = Path::new(CORPUS).join(format!("{name}.render.json"));
        if let Err(error) = common::check_golden(&path, got.as_deref()) {
            failures.push(error);
        }
    }
    assert!(checked >= 20, "only {checked} shown cases");
    common::assert_none(&failures, checked);
}
