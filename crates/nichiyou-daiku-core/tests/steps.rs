//! The parts, steps and fasteners view gives match the Python version's
//! (NAME.steps.json, written by tools/make_goldens.py).

use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

mod common;
use common::normalize;

const DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/corpus");
const KEYS: [&str; 4] = ["parts", "steps", "steps_declared", "steps_hint"];

/// The view with the pieces' holes as the Python version records them: the
/// parts and steps compared here come from those, while the view's own hole
/// list stays countersunk (diagnostics' tests cover it).
fn python_form_view(source: &str) -> serde_json::Value {
    let located = nichiyou_daiku_core::dsl::parse_located(source).expect("a source that assembles");
    let mut assembly = nichiyou_daiku_core::assembly::Assembly::of(located.model.clone())
        .expect("a source that assembles");
    common::python_holes(&mut assembly);
    nichiyou_daiku_core::diagnostics::view_report(&assembly, &located.pieces, &located.connections)
}

#[test]
fn parts_steps_and_fasteners_match_the_python_version() {
    let mut paths: Vec<PathBuf> = fs::read_dir(DIR)
        .unwrap()
        .map(|e| e.unwrap().path())
        .filter(|p| p.extension().is_some_and(|e| e == "nd"))
        .collect();
    paths.sort();
    let mut checked = 0;
    let mut differ = Vec::new();
    for path in paths {
        let golden = path.with_extension("steps.json");
        let Ok(text) = fs::read_to_string(&golden) else {
            continue;
        };
        let expected = normalize(serde_json::from_str(&text).unwrap(), &mut HashMap::new());
        let view = normalize(
            python_form_view(&fs::read_to_string(&path).unwrap()),
            &mut HashMap::new(),
        );
        if let Some(key) = KEYS.iter().find(|key| view[**key] != expected[**key]) {
            differ.push(format!(
                "{}: {key}\n  rust:   {}\n  python: {}",
                path.display(),
                view[*key],
                expected[*key]
            ));
        }
        checked += 1;
    }
    assert!(
        checked >= 600,
        "only {checked} cases have steps goldens: run tools/make_goldens.py --steps-only"
    );
    assert!(
        differ.is_empty(),
        "{} of {checked} cases differ:\n{}",
        differ.len(),
        differ
            .iter()
            .take(5)
            .cloned()
            .collect::<Vec<_>>()
            .join("\n")
    );
}
