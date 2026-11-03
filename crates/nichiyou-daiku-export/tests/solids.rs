//! Every piece of every design in the corpus is a closed solid, and the
//! examples' volumes and boxes match the Python version's 3D
//! (NAME.solids.json, written by tools/make_goldens.py --cli).

use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_core::pyfmt::round_mm;
use nichiyou_daiku_export::model;
use serde_json::{Value, json};

#[path = "../../nichiyou-daiku-core/tests/common/mod.rs"]
mod common;

const CORPUS: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../nichiyou-daiku-core/tests/corpus"
);

fn designs() -> Vec<(PathBuf, Assembly)> {
    let mut paths: Vec<PathBuf> = fs::read_dir(CORPUS)
        .unwrap()
        .map(|e| e.unwrap().path())
        .filter(|p| p.extension().is_some_and(|e| e == "nd"))
        .collect();
    paths.sort();
    paths
        .into_iter()
        .filter_map(|path| {
            let model =
                nichiyou_daiku_core::dsl::parse(&fs::read_to_string(&path).unwrap()).ok()?;
            Some((path, Assembly::of(model).ok()?))
        })
        .collect()
}

#[test]
fn every_piece_is_a_closed_solid() {
    let mut checked = 0;
    for (path, assembly) in designs() {
        for solid in model(&assembly).solids {
            let loops: usize = solid.faces.iter().map(|f| f.loops.len()).sum();
            let (v, e, f) = (
                solid.vertices.len() as i64,
                solid.edges.len() as i64,
                solid.faces.len() as i64,
            );
            assert_eq!(
                v - e + f - (loops as i64 - f),
                2 * (1 - solid.through as i64),
                "{} {}",
                path.display(),
                solid.name
            );
            assert!(solid.volume > 0.0, "{} {}", path.display(), solid.name);
            checked += 1;
        }
    }
    assert!(checked > 1000, "only {checked} pieces");
}

#[test]
fn solids_match_the_python_version() {
    let mut differ = Vec::new();
    let mut checked = 0;
    for (path, mut assembly) in designs() {
        let Ok(text) = fs::read_to_string(path.with_extension("solids.json")) else {
            continue;
        };
        common::python_holes(&mut assembly);
        let made = model(&assembly);
        let mut pieces = serde_json::Map::new();
        for solid in &made.solids {
            let extreme = |i: usize, f: fn(f64, f64) -> f64, start: f64| {
                round_mm(solid.vertices.iter().map(|v| v[i]).fold(start, f))
            };
            pieces.insert(
                solid.name.clone(),
                json!({
                    "volume": solid.volume,
                    "min": (0..3).map(|i| extreme(i, f64::min, f64::MAX)).collect::<Vec<_>>(),
                    "max": (0..3).map(|i| extreme(i, f64::max, f64::MIN)).collect::<Vec<_>>(),
                }),
            );
        }
        let want: Value =
            common::normalize(serde_json::from_str(&text).unwrap(), &mut HashMap::new());
        let got = common::normalize(json!({ "pieces": pieces }), &mut HashMap::new());
        for (id, w) in want["pieces"].as_object().unwrap() {
            let g = &got["pieces"][id];
            let (wv, gv) = (
                w["volume"].as_f64().unwrap(),
                g["volume"].as_f64().unwrap_or(-1.0),
            );
            if (wv - gv).abs() > 1e-6 * wv + 1e-2 || w["min"] != g["min"] || w["max"] != g["max"] {
                differ.push(format!(
                    "{} {id}\n  python: {w}\n  rust:   {g}",
                    path.display()
                ));
            }
        }
        checked += 1;
    }
    assert!(
        checked >= 20,
        "only {checked} cases have solids.json: run tools/make_goldens.py --cli"
    );
    assert!(
        differ.is_empty(),
        "{} differ:\n{}",
        differ.len(),
        differ
            .iter()
            .take(5)
            .cloned()
            .collect::<Vec<_>>()
            .join("\n")
    );
}

#[test]
fn every_piece_meshes_watertight_to_its_volume() {
    for (path, assembly) in designs() {
        for solid in model(&assembly).solids {
            let mesh = nichiyou_daiku_export::mesh::mesh(&solid);
            let mut seen = HashMap::new();
            for t in &mesh.triangles {
                for k in 0..3 {
                    *seen.entry((t[k], t[(k + 1) % 3])).or_insert(0) += 1;
                }
            }
            let tight = seen
                .iter()
                .all(|(&(a, b), &n)| n == 1 && seen.get(&(b, a)) == Some(&1));
            assert!(tight, "{} {}: not watertight", path.display(), solid.name);
            let v = nichiyou_daiku_export::mesh::volume(&mesh);
            assert!(
                v >= solid.volume - 1e-6,
                "{} {}: {v} < {}",
                path.display(),
                solid.name,
                solid.volume
            );
        }
    }
}
