//! view agrees with validate and with the holes of every corpus case.

use std::fs;

use serde_json::Value;

const DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/corpus");
const EXTRA_PIECE_KEYS: [&str; 4] = ["size", "position", "rotation", "line"];

fn sources() -> Vec<(String, String)> {
    let mut paths: Vec<_> = fs::read_dir(DIR)
        .unwrap()
        .map(|e| e.unwrap().path())
        .filter(|p| p.extension().is_some_and(|e| e == "nd"))
        .collect();
    paths.sort();
    paths
        .into_iter()
        .map(|p| (p.display().to_string(), fs::read_to_string(&p).unwrap()))
        .collect()
}

fn f(value: &Value) -> f64 {
    value.as_f64().unwrap()
}

fn close(a: f64, b: f64) -> bool {
    (a - b).abs() <= 1e-6
}

fn apply(piece: &Value, local: [f64; 3]) -> [f64; 3] {
    std::array::from_fn(|r| {
        (0..3)
            .map(|k| f(&piece["rotation"][r][k]) * local[k])
            .sum::<f64>()
            + f(&piece["position"][r])
    })
}

#[test]
fn without_its_additions_view_is_validate() {
    for (name, source) in sources() {
        let mut view = nichiyou_daiku_core::view(&source);
        let validate = nichiyou_daiku_core::validate(&source);
        let object = view.as_object_mut().unwrap();
        object.remove("connections").expect("connections");
        object.remove("holes").expect("holes");
        for key in ["parts", "steps", "steps_declared", "steps_hint"] {
            object.remove(key).expect(key);
        }
        for piece in object["pieces"].as_array_mut().unwrap() {
            for key in EXTRA_PIECE_KEYS {
                piece.as_object_mut().unwrap().remove(key).expect(key);
            }
        }
        assert_eq!(view, validate, "{name}");
    }
}

#[test]
fn poses_give_the_boxes_validate_reports() {
    for (name, source) in sources() {
        let view = nichiyou_daiku_core::view(&source);
        for piece in view["pieces"].as_array().unwrap() {
            let size: [f64; 3] = std::array::from_fn(|i| f(&piece["size"][i]));
            let mut low = [f64::INFINITY; 3];
            let mut high = [f64::NEG_INFINITY; 3];
            for corner in 0..8 {
                let local =
                    std::array::from_fn(|i| if corner >> i & 1 == 1 { size[i] } else { 0.0 });
                let world = apply(piece, local);
                for i in 0..3 {
                    low[i] = low[i].min(world[i]);
                    high[i] = high[i].max(world[i]);
                }
            }
            for i in 0..3 {
                assert!(
                    close(low[i], f(&piece["min"][i])) && close(high[i], f(&piece["max"][i])),
                    "{name}: {}",
                    piece["id"]
                );
            }
        }
    }
}

#[test]
fn holes_are_the_pieces_holes_in_the_world() {
    for (name, source) in sources() {
        let view = nichiyou_daiku_core::view(&source);
        let Some(local) = nichiyou_daiku_core::holes(&source) else {
            assert!(view["holes"].as_array().unwrap().is_empty(), "{name}");
            continue;
        };
        for piece in view["pieces"].as_array().unwrap() {
            let id = piece["id"].as_str().unwrap();
            let mut expected: Vec<[f64; 3]> = local["pieces"]
                .get(id)
                .and_then(Value::as_array)
                .map(|holes| {
                    holes
                        .iter()
                        .map(|h| apply(piece, std::array::from_fn(|i| f(&h["center"][i]))))
                        .collect()
                })
                .unwrap_or_default();
            let mut actual: Vec<[f64; 3]> = view["holes"]
                .as_array()
                .unwrap()
                .iter()
                .filter(|h| h["piece"] == id)
                .map(|h| std::array::from_fn(|i| f(&h["center"][i])))
                .collect();
            let order = |a: &[f64; 3], b: &[f64; 3]| a.partial_cmp(b).unwrap();
            expected.sort_by(order);
            actual.sort_by(order);
            assert_eq!(expected.len(), actual.len(), "{name}: {id}");
            for (e, a) in expected.iter().zip(&actual) {
                assert!(
                    (0..3).all(|i| (e[i] - a[i]).abs() <= 2e-6),
                    "{name}: {id}: {e:?} != {a:?}"
                );
            }
        }
    }
}
