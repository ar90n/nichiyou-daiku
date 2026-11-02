//! The technical drawing's chain dimensions match the Python version's
//! (NAME.chains.json, written by tools/make_goldens.py --steps-only).

use std::fs;
use std::path::PathBuf;

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_core::dimensioning::drawing_chains;
use nichiyou_daiku_core::placement::overall_bounds;
use nichiyou_daiku_core::pyfmt::round_mm;
use serde_json::{Value, json};

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

#[test]
fn drawing_chains_match_the_python_version() {
    let mut paths: Vec<PathBuf> = fs::read_dir(DIR)
        .unwrap()
        .map(|e| e.unwrap().path())
        .filter(|p| p.extension().is_some_and(|e| e == "nd"))
        .collect();
    paths.sort();
    let (mut checked, mut differ) = (0, Vec::new());
    for path in paths {
        let Ok(text) = fs::read_to_string(path.with_extension("chains.json")) else {
            continue;
        };
        let want: Value = serde_json::from_str(&text).unwrap();
        let model = nichiyou_daiku_core::dsl::parse(&fs::read_to_string(&path).unwrap()).unwrap();
        let got = chains_json(&Assembly::of(model).unwrap());
        if want != got {
            differ.push(format!(
                "{}\n  python: {want}\n  rust:   {got}",
                path.display()
            ));
        }
        checked += 1;
    }
    assert!(
        checked >= 600,
        "only {checked} cases have chains.json: run tools/make_goldens.py --steps-only"
    );
    assert!(
        differ.is_empty(),
        "{} of {checked} differ:\n{}",
        differ.len(),
        differ
            .iter()
            .take(3)
            .cloned()
            .collect::<Vec<_>>()
            .join("\n")
    );
}
