//! The parts and steps the viewer gets (`view`) for every corpus case that
//! assembles, against NAME.steps.json.

use std::path::Path;

use serde_json::{Map, Value};

mod common;
use common::{assert_none, check_golden, corpus, pretty};

const DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/corpus");
const KEYS: [&str; 4] = ["parts", "steps", "steps_declared", "steps_hint"];

fn steps(source: &str) -> Option<String> {
    let view = nichiyou_daiku_core::view(source);
    if !view["error"].is_null() {
        return None;
    }
    let picked: Map<String, Value> = KEYS
        .iter()
        .map(|key| (key.to_string(), view[*key].clone()))
        .collect();
    Some(pretty(&Value::Object(picked)))
}

#[test]
fn parts_and_steps_match_their_golden_files() {
    let (mut failures, mut checked) = (Vec::new(), 0);
    for (name, source) in corpus(Path::new(DIR)) {
        let got = steps(&source);
        checked += usize::from(got.is_some());
        let path = Path::new(DIR).join(format!("{name}.steps.json"));
        if let Err(error) = check_golden(&path, got.as_deref()) {
            failures.push(error);
        }
    }
    assert!(checked >= 600, "only {checked} cases assemble");
    assert_none(&failures, checked);
}
