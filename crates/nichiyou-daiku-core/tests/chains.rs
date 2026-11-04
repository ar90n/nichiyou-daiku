//! The technical drawing's chain dimensions for every corpus case that
//! assembles, against NAME.chains.json.

use std::path::Path;

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_core::dimensioning::drawing_chains;
use nichiyou_daiku_core::placement::overall_bounds;
use nichiyou_daiku_core::pyfmt::round_mm;
use serde_json::{Value, json};

mod common;
use common::{assert_none, check_golden, corpus, pretty};

const DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/corpus");
const AXES: [&str; 3] = ["x", "y", "z"];

/// The chains as the golden files have them: moved to the model's origin.
fn chains_json(assembly: &Assembly) -> Value {
    let origin = overall_bounds(&assembly.model, &assembly.placement).0;
    drawing_chains(assembly)
        .iter()
        .map(|(view, chain)| {
            let at = |value: f64| round_mm(value - origin[chain.axis]);
            json!({
                "view": view,
                "axis": AXES[chain.axis],
                "side": chain.side.as_str(),
                "stops": chain.stops.iter().map(|&s| at(s)).collect::<Vec<_>>(),
                "segments": chain
                    .segments
                    .iter()
                    .map(|s| json!({"start": at(s.start), "end": at(s.end), "lumber": s.lumber}))
                    .collect::<Vec<_>>(),
            })
        })
        .collect()
}

fn chains(source: &str) -> Option<String> {
    let model = nichiyou_daiku_core::dsl::parse(source).ok()?;
    let assembly = Assembly::of(model).ok()?;
    Some(pretty(&chains_json(&assembly)))
}

#[test]
fn drawing_chains_match_their_golden_files() {
    let (mut failures, mut checked) = (Vec::new(), 0);
    for (name, source) in corpus(Path::new(DIR)) {
        let got = chains(&source);
        checked += usize::from(got.is_some());
        let path = Path::new(DIR).join(format!("{name}.chains.json"));
        if let Err(error) = check_golden(&path, got.as_deref()) {
            failures.push(error);
        }
    }
    assert!(checked >= 600, "only {checked} cases assemble");
    assert_none(&failures, checked);
}
