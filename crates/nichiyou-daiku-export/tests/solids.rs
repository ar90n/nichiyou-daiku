//! Every piece of every design in the corpus is a closed solid, and the
//! examples' volumes and boxes match NAME.solids.json.

use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_core::pyfmt::round_mm;
use nichiyou_daiku_export::model;
use serde_json::json;

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
fn solids_match_their_golden_files() {
    let (mut failures, mut checked) = (Vec::new(), 0);
    for (path, assembly) in designs() {
        let name = path.file_stem().unwrap().to_string_lossy().into_owned();
        let got = common::shown(&name).then(|| {
            let mut pieces = serde_json::Map::new();
            for solid in &model(&assembly).solids {
                let extreme = |i: usize, f: fn(f64, f64) -> f64, start: f64| {
                    round_mm(solid.vertices.iter().map(|v| v[i]).fold(start, f))
                };
                pieces.insert(
                    solid.name.clone(),
                    json!({
                        // To a thousandth of a mm³: the last bits of a sum vary between machines
                        "volume": (solid.volume * 1000.0).round() / 1000.0,
                        "min": (0..3).map(|i| extreme(i, f64::min, f64::MAX)).collect::<Vec<_>>(),
                        "max": (0..3).map(|i| extreme(i, f64::max, f64::MIN)).collect::<Vec<_>>(),
                    }),
                );
            }
            common::pretty(&json!({ "pieces": pieces }))
        });
        checked += usize::from(got.is_some());
        if let Err(error) =
            common::check_golden(&path.with_extension("solids.json"), got.as_deref())
        {
            failures.push(error);
        }
    }
    assert!(checked >= 20, "only {checked} shown cases");
    common::assert_none(&failures, checked);
}

#[test]
fn every_edge_runs_through_its_vertices() {
    use nichiyou_daiku_export::solid::Curve;
    let mut off = Vec::new();
    for (path, assembly) in designs() {
        for solid in model(&assembly).solids {
            for edge in &solid.edges {
                let on = |p: [f64; 3]| match edge.curve {
                    Curve::Line { origin, direction } => {
                        let d = [0, 1, 2].map(|i| p[i] - origin[i]);
                        let along: f64 = (0..3).map(|i| d[i] * direction[i]).sum();
                        (0..3).all(|i| (d[i] - along * direction[i]).abs() < 1e-9)
                    }
                    Curve::Circle {
                        centre,
                        axis,
                        radius,
                        ..
                    } => {
                        let d = [0, 1, 2].map(|i| p[i] - centre[i]);
                        let height: f64 = (0..3).map(|i| d[i] * axis[i]).sum();
                        let r = (0..3).map(|i| d[i] * d[i]).sum::<f64>().sqrt();
                        height.abs() < 1e-9 && (r - radius).abs() < 1e-9
                    }
                };
                if !on(solid.vertices[edge.start]) || !on(solid.vertices[edge.end]) {
                    off.push(format!("{} {}", path.display(), solid.name));
                }
            }
        }
    }
    off.dedup();
    assert!(
        off.is_empty(),
        "{} edges:\n{}",
        off.len(),
        off[..off.len().min(5)].join("\n")
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
