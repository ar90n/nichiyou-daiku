//! Unknown lengths (`=?`) and offsets (`?`): solved from the connections, so
//! that everything downstream works on a model of numbers only.

use std::collections::HashMap;

use crate::anchor::{Anchor, BoundAnchor, anchor_edge, anchor_point};
use crate::connection::Connection;
use crate::geometry::{Offset, edge_length};
use crate::model::Model;
use crate::piece::Piece;
use crate::placement::{
    End, PositionSolution, TOLERANCE_MM, edge_axis, node, rotate, solve_positions,
};
use crate::pyfmt::{format_g, round_mm};

const AXES: [&str; 3] = ["x", "y", "z"];

#[derive(Clone, Debug, PartialEq)]
pub struct ResolutionError {
    pub message: String,
    pub piece_id: Option<String>,
    pub connection: Option<(String, String)>,
}

fn on_piece(message: String, piece: &str) -> ResolutionError {
    ResolutionError {
        message,
        piece_id: Some(piece.to_string()),
        connection: None,
    }
}

fn on_connection(message: String, connection: &Connection) -> ResolutionError {
    ResolutionError {
        message,
        piece_id: None,
        connection: Some((
            connection.base_id().to_string(),
            connection.target_id().to_string(),
        )),
    }
}

/// The model with its unknowns solved, checked again with the numbers
/// (resolve.py: resolve_model).
pub fn resolve_model(model: Model) -> Result<Model, ResolutionError> {
    if !model.has_unknowns() {
        return Ok(model);
    }
    let mut solution = solve_positions(&model);
    let mut pieces = Vec::with_capacity(model.pieces.len());
    for (i, piece) in model.pieces.iter().enumerate() {
        let length = match piece.length {
            Some(length) => length,
            None => solved_length(i, piece, &mut solution)?,
        };
        pieces.push(Piece {
            length: Some(length),
            ..piece.clone()
        });
    }
    check_positions_fixed(&model, &mut solution)?;
    let index: HashMap<&str, usize> = model
        .pieces
        .iter()
        .enumerate()
        .map(|(i, piece)| (piece.id.as_str(), i))
        .collect();
    // Later conflicts on the same connection win, as in Python's dict
    let conflicted: HashMap<(String, String), &str> = solution
        .conflicts
        .iter()
        .map(|c| ((c.base_id.clone(), c.target_id.clone()), c.kind.as_str()))
        .collect();
    let mut connections = Vec::with_capacity(model.connections.len());
    for connection in &model.connections {
        let key = (connection.base_id(), connection.target_id());
        let owned = (key.0.to_string(), key.1.to_string());
        let (mut base, mut target) = (connection.base.anchor, connection.target.anchor);
        if base.offset.is_none() {
            let (base_offset, target_offset) = if conflicted.get(&owned) == Some(&"rotation") {
                (Offset::FromMin(0.0), Offset::FromMin(0.0))
            } else {
                sliding_offsets(
                    connection,
                    (&pieces[index[key.0]], index[key.0]),
                    (&pieces[index[key.1]], index[key.1]),
                    &mut solution,
                    !conflicted.contains_key(&owned),
                )?
            };
            base = Anchor {
                offset: Some(base_offset),
                ..base
            };
            target = Anchor {
                offset: Some(target_offset),
                ..target
            };
        }
        let rebuilt = BoundAnchor::new(pieces[index[key.0]].clone(), base)
            .and_then(|base| {
                BoundAnchor::new(pieces[index[key.1]].clone(), target).map(|target| (base, target))
            })
            .and_then(|(base, target)| Connection::new(base, target, connection.kind))
            .map_err(|message| on_connection(message, connection))?;
        connections.push(rebuilt);
    }
    Model::new(pieces, connections, model.steps).map_err(|message| ResolutionError {
        message,
        piece_id: None,
        connection: None,
    })
}

fn solved_length(
    i: usize,
    piece: &Piece,
    solution: &mut PositionSolution,
) -> Result<f64, ResolutionError> {
    let (axis, sign) = solution.length_axis[i];
    let (down_root, down) = solution.offsets[axis].find(node(i, End::Down));
    let (top_root, top) = solution.offsets[axis].find(node(i, End::Top));
    if down_root != top_root {
        return Err(on_piece(
            format!(
                "The length of '{}' is not fixed by its connections",
                piece.id
            ),
            &piece.id,
        ));
    }
    let length = round_mm(f64::from(sign) * (top - down));
    if length <= TOLERANCE_MM {
        return Err(on_piece(
            format!(
                "The connections make '{}' {}mm long; a piece needs a positive length",
                piece.id,
                format_g(length, 6)
            ),
            &piece.id,
        ));
    }
    Ok(length)
}

/// Every piece must be fixed against its group's first piece on every axis.
fn check_positions_fixed(
    model: &Model,
    solution: &mut PositionSolution,
) -> Result<(), ResolutionError> {
    for group in solution.groups.clone() {
        let root = group[0];
        for &member in &group[1..] {
            for (axis, name) in AXES.iter().enumerate() {
                let member_root = solution.offsets[axis].find(node(member, End::Down)).0;
                let root_root = solution.offsets[axis].find(node(root, End::Down)).0;
                if member_root != root_root {
                    let id = &model.pieces[member].id;
                    let sliding: Vec<String> = model
                        .connections
                        .iter()
                        .filter(|c| {
                            (c.base_id() == id || c.target_id() == id)
                                && c.base.anchor.offset.is_none()
                        })
                        .map(|c| format!("{} -> {}", c.base_id(), c.target_id()))
                        .collect();
                    let held_by = if sliding.is_empty() {
                        "connections with unknown offsets (?)".to_string()
                    } else {
                        format!(
                            "its connections with unknown offsets ({})",
                            sliding.join(", ")
                        )
                    };
                    return Err(on_piece(
                        format!(
                            "'{id}' can slide along {name} (axes of '{}'): {held_by} leave its \
                             position open",
                            model.pieces[root].id
                        ),
                        id,
                    ));
                }
            }
        }
    }
    Ok(())
}

/// Where along the shared edge two sliding anchors meet: the near end of the
/// overlap of their edges, measured from each edge's start.
fn sliding_offsets(
    connection: &Connection,
    base: (&Piece, usize),
    target: (&Piece, usize),
    solution: &mut PositionSolution,
    must_meet: bool,
) -> Result<(Offset, Offset), ResolutionError> {
    let axis = edge_axis(&solution.rotation[base.1], &connection.base);
    let spans = [
        edge_span(base, &connection.base.anchor, solution, axis),
        edge_span(target, &connection.target.anchor, solution, axis),
    ];
    let low = spans
        .iter()
        .map(|&(start, direction, length)| start.min(start + f64::from(direction) * length))
        .fold(f64::NEG_INFINITY, f64::max);
    let high = spans
        .iter()
        .map(|&(start, direction, length)| start.max(start + f64::from(direction) * length))
        .fold(f64::INFINITY, f64::min);
    if must_meet && high < low - TOLERANCE_MM {
        return Err(on_connection(
            format!(
                "'{}' and '{}' slide along a shared edge (?) but their edges do not meet",
                connection.base_id(),
                connection.target_id()
            ),
            connection,
        ));
    }
    let point = if spans[0].1 > 0 { low } else { high };
    let offset = |(start, direction, length): (f64, i32, f64)| {
        Offset::FromMin(
            round_mm((point - start) * f64::from(direction))
                .max(0.0)
                .min(length),
        )
    };
    Ok((offset(spans[0]), offset(spans[1])))
}

/// Where the anchor's edge starts on the axis, which way it runs, and how long it is.
fn edge_span(
    (piece, i): (&Piece, usize),
    anchor: &Anchor,
    solution: &mut PositionSolution,
    axis: usize,
) -> (f64, i32, f64) {
    let rotation = solution.rotation[i];
    let start_anchor = Anchor {
        offset: Some(Offset::FromMin(0.0)),
        ..*anchor
    };
    let bound = BoundAnchor {
        piece: piece.clone(),
        anchor: start_anchor,
    };
    let point = anchor_point(&bound);
    let position = solution.offsets[axis].find(node(i, End::Down)).1;
    let start = position + rotate(&rotation, point)[axis];
    let along = crate::geometry::Face::cross(anchor.contact, anchor.edge)
        .expect("anchor faces are adjacent")
        .normal()
        .map(i32::abs);
    let direction = (0..3).map(|k| rotation[axis][k] * along[k]).sum();
    (
        start,
        direction,
        edge_length(piece.shape(), anchor_edge(&start_anchor)),
    )
}

#[cfg(test)]
mod tests {
    use crate::dsl::parse;

    #[test]
    fn unknown_lengths_are_solved_from_the_connections() {
        let source = include_str!("../../../examples/nd_files/simple_table_unknowns.nd");
        let model = parse(source).unwrap();
        assert_eq!(model.piece("apron_front").unwrap().length, Some(622.0));
        assert!(!model.has_unknowns());
    }

    #[test]
    fn a_length_nothing_fixes_is_reported_on_its_piece() {
        let error =
            parse("(a:2x4 =?)\n(b:2x4 =100)\n(c:2x4 =100)\nb -[FT<0 DF<0]- a\nc -[FT<0 TF<0]- a")
                .unwrap_err();
        assert_eq!(
            error.to_string(),
            "line 1, column 1: The length of 'a' is not fixed by its connections"
        );
    }
}
