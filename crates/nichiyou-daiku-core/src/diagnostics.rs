//! The problems `validate` reports, and its JSON: piece boxes, the overall
//! size and the problems, or why validation stopped.

use serde_json::{Value, json};

use crate::assembly::{Assembly, Hole, LayoutIssue};
use crate::geometry::{Face, SurfacePoint};
use crate::placement::{ConstraintKind, axis_index, find_overlaps, overall_bounds, rotate};
use crate::pyfmt::{format_mm, round_mm};

const AXES: [&str; 3] = ["x", "y", "z"];

fn vector(values: [f64; 3]) -> Value {
    json!(values.map(round_mm))
}

/// The world direction a vector points to: +x … -z.
fn direction(vector: [f64; 3]) -> String {
    let axis = axis_index(vector);
    format!(
        "{}{}",
        if vector[axis] > 0.0 { '+' } else { '-' },
        AXES[axis]
    )
}

fn minus(a: [f64; 3], b: [f64; 3]) -> [f64; 3] {
    std::array::from_fn(|i| a[i] - b[i])
}

fn origin(assembly: &Assembly) -> [f64; 3] {
    overall_bounds(&assembly.model, &assembly.placement).0
}

fn hole(
    assembly: &Assembly,
    piece_id: &str,
    at: SurfacePoint,
    hole: Hole,
    origin: [f64; 3],
) -> Value {
    let pose = assembly.placement.pose(piece_id);
    let shape = assembly
        .model
        .piece(piece_id)
        .expect("a hole is in a piece")
        .shape();
    let entry = pose.apply(at.to_point(shape));
    let inward = rotate(&pose.rotation, at.face.normal().map(|x| -f64::from(x)));
    json!({
        "entry": vector(minus(entry, origin)),
        "direction": direction(inward),
        "depth": hole.depth.map(round_mm),
        "diameter": round_mm(hole.diameter),
    })
}

fn fastener_problem(assembly: &Assembly, issue: &LayoutIssue, origin: [f64; 3]) -> Value {
    let message = format!(
        "Connection {} -> {}: {}",
        issue.base_id, issue.target_id, issue.message
    );
    let connection = json!([issue.base_id, issue.target_id]);
    match (&issue.piece_id, &issue.other, &issue.holes) {
        (Some(piece), Some(other), Some((later, earlier))) => json!({
            "kind": "hole_collision",
            "message": message,
            "connection": connection,
            "other_connection": [other.0, other.1],
            "piece": piece,
            "fastener": issue.kind.as_str(),
            "holes": [
                hole(assembly, piece, later.0, later.1, origin),
                hole(assembly, piece, earlier.0, earlier.1, origin),
            ],
        }),
        _ => json!({
            "kind": "fastener",
            "message": message,
            "connection": connection,
            "fastener": issue.kind.as_str(),
        }),
    }
}

/// Contradicting connections, then pieces not connected, then fasteners, then
/// overlapping pieces (diagnostics.py: collect_problems).
pub fn collect_problems(assembly: &Assembly) -> Vec<Value> {
    let placement = &assembly.placement;
    let origin = origin(assembly);
    let mut problems = Vec::new();
    for conflict in &placement.conflicts {
        let looped = conflict.looped.join(" -> ");
        let place = format!("Connection {} -> {}", conflict.base_id, conflict.target_id);
        let message = match (conflict.kind, conflict.axis) {
            (ConstraintKind::Rotation, _) => {
                format!("{place}: orientation contradicts the other connections (loop: {looped})")
            }
            (kind, axis) => format!(
                "{place}: {} ({}) is off by {}mm (loop: {looped})",
                kind.as_str(),
                axis.map_or("None", |a| AXES[a]),
                format_mm(conflict.mismatch_mm.unwrap_or(0.0).abs())
            ),
        };
        problems.push(json!({
            "kind": "conflict",
            "message": message,
            "connection": [conflict.base_id, conflict.target_id],
            "constraint": conflict.kind.as_str(),
            "axis": conflict.axis.map(|a| AXES[a]),
            "mismatch_mm": conflict.mismatch_mm.map(round_mm),
            "loop": conflict.looped,
        }));
    }
    if placement.groups.len() > 1 {
        let listed: Vec<String> = placement
            .groups
            .iter()
            .map(|group| group.join(", "))
            .collect();
        problems.push(json!({
            "kind": "unconnected",
            "message": format!(
                "Some pieces are not connected to each other, so their relative position is \
                 undefined (groups: {})",
                listed.join("; ")
            ),
            "groups": placement.groups,
        }));
    }
    for issue in &assembly.fastener_issues {
        problems.push(fastener_problem(assembly, issue, origin));
    }
    for overlap in find_overlaps(&assembly.model, placement) {
        problems.push(json!({
            "kind": "overlap",
            "message": format!(
                "Pieces '{}' and '{}' overlap ({}mm³)",
                overlap.lhs,
                overlap.rhs,
                format_mm(overlap.volume)
            ),
            "pieces": [overlap.lhs, overlap.rhs],
            "volume_mm3": round_mm(overlap.volume),
        }));
    }
    problems
}

fn positions(assembly: &Assembly, origin: [f64; 3]) -> Vec<Value> {
    let group_of = |id: &str| {
        assembly
            .placement
            .groups
            .iter()
            .position(|group| group.iter().any(|member| member == id))
            .expect("every piece is in a group")
    };
    assembly
        .model
        .pieces
        .iter()
        .map(|piece| {
            let pose = assembly.placement.pose(&piece.id);
            let shape = piece.shape();
            let (low, high) = pose.bounds(shape);
            let face = |face: Face| direction(rotate(&pose.rotation, face.normal().map(f64::from)));
            json!({
                "id": piece.id,
                "type": piece.kind.as_str(),
                "length": round_mm(shape.length),
                "group": group_of(&piece.id),
                "min": vector(minus(low, origin)),
                "max": vector(minus(high, origin)),
                "faces": {"top": face(Face::Top), "right": face(Face::Right), "front": face(Face::Front)},
            })
        })
        .collect()
}

/// What `validate --json` prints for a model that assembles.
pub fn validation_report(assembly: &Assembly) -> Value {
    let problems = collect_problems(assembly);
    let (overall_size, size_reference) = if assembly.placement.groups.len() == 1 {
        let (low, high) = overall_bounds(&assembly.model, &assembly.placement);
        (
            vector(minus(high, low)),
            json!(assembly.placement.groups[0][0]),
        )
    } else {
        (Value::Null, Value::Null)
    };
    json!({
        "valid": problems.is_empty(),
        "error": null,
        "overall_size": overall_size,
        "size_reference": size_reference,
        "pieces": positions(assembly, origin(assembly)),
        "problems": problems,
    })
}

/// What `validate --json` prints when validation stops: `kind` is file,
/// syntax, semantic, validation, assembly or unexpected.
pub fn failure_report(
    kind: &str,
    message: &str,
    line: Option<usize>,
    column: Option<usize>,
) -> Value {
    json!({
        "valid": false,
        "error": {"kind": kind, "message": message, "line": line, "column": column},
        "overall_size": null,
        "size_reference": null,
        "pieces": [],
        "problems": [],
    })
}

/// Every piece's holes (by face, then centre, in the piece's coordinates) and
/// each connection's fasteners, counted.
pub fn holes_report(assembly: &Assembly) -> Value {
    let mut pieces = serde_json::Map::new();
    for (piece_id, entries) in &assembly.pilot_holes {
        let shape = assembly
            .model
            .piece(piece_id)
            .expect("a hole is in a piece")
            .shape();
        let mut listed: Vec<(&str, [f64; 3], Hole)> = entries
            .iter()
            .map(|(at, hole)| (at.face.as_str(), at.to_point(shape).map(round_mm), *hole))
            .collect();
        listed.sort_by(|a, b| {
            a.0.cmp(b.0)
                .then_with(|| a.1.partial_cmp(&b.1).expect("hole centres are numbers"))
        });
        let listed: Vec<Value> = listed
            .into_iter()
            .map(|(face, center, hole)| {
                json!({
                    "face": face,
                    "center": center,
                    "diameter": round_mm(hole.diameter),
                    "depth": hole.depth.map(round_mm),
                })
            })
            .collect();
        pieces.insert(piece_id.clone(), Value::Array(listed));
    }
    let mut fasteners: Vec<Value> = Vec::new();
    for fastener in &assembly.fasteners {
        let key = json!({
            "base": fastener.base_id,
            "target": fastener.target_id,
            "kind": fastener.kind.as_str(),
            "diameter": round_mm(fastener.diameter),
        });
        let same = fasteners.last().is_some_and(|last| {
            ["base", "target", "kind", "diameter"]
                .iter()
                .all(|k| last[k] == key[k])
        });
        if same {
            let last = fasteners.last_mut().expect("checked above");
            last["count"] = json!(last["count"].as_u64().expect("a count") + 1);
        } else {
            let mut entry = key;
            entry["count"] = json!(1);
            fasteners.push(entry);
        }
    }
    json!({"pieces": pieces, "fasteners": fasteners})
}

#[cfg(test)]
mod tests {
    use crate::{holes, validate};
    use serde_json::json;

    #[test]
    fn conflicts_are_problems_with_their_loop() {
        let report = validate(
            "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\na -[FL<100 DF<0]- b\na -[FL<200 DF<0]- c\nb -[FT<0 BT<0]- c\n",
        );
        assert_eq!(report["valid"], false);
        assert_eq!(report["overall_size"], json!([89.0, 338.0, 500.0]));
        assert_eq!(
            report["problems"][0],
            json!({"kind": "conflict", "message": "Connection b -> c: contact (x) is off by 38mm (loop: b -> a -> c)",
                "connection": ["b", "c"], "constraint": "contact", "axis": "x", "mismatch_mm": -38.0, "loop": ["b", "a", "c"]})
        );
    }

    #[test]
    fn unconnected_pieces_have_no_overall_size() {
        let report = validate("(a:2x4 =500)\n(b:2x4 =300)\n");
        assert_eq!(report["overall_size"], json!(null));
        assert_eq!(
            report["problems"][0]["message"],
            "Some pieces are not connected to each other, so their relative position is undefined (groups: a; b)"
        );
    }

    #[test]
    fn overlaps_and_piece_faces() {
        let report = validate(
            "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\na -[FL<100 DF<0]- b\na -[FL<150 DF<0]- c\n",
        );
        assert_eq!(
            report["problems"][0]["message"],
            "Pieces 'b' and 'c' overlap (444600mm³)"
        );
        assert_eq!(
            report["pieces"][1]["faces"],
            json!({"top": "+y", "right": "-z", "front": "-x"})
        );
        assert_eq!(report["size_reference"], "a");
    }

    #[test]
    fn errors_stop_validation() {
        let report = validate("(a:2x4 =100");
        assert_eq!(report["error"]["kind"], "syntax");
        assert_eq!(
            (
                report["error"]["line"].clone(),
                report["error"]["column"].clone()
            ),
            (json!(1), json!(9))
        );
        assert_eq!(report["pieces"], json!([]));
        assert_eq!(holes("(a:2x4 =100"), None);
    }
}
