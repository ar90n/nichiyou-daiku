//! The parts to make before assembling: pieces grouped when they are made
//! the same (parts.py: part_groups). A piece's axes: x across its width, y
//! across its thickness, z along its length, from 0 at one corner.

use crate::assembly::Assembly;
use crate::geometry::Face;

/// Holes this close are the same hole when pieces are compared.
pub const TOLERANCE_MM: f64 = 0.05;

/// The faces in pairs, the first of each pair where a through hole is kept.
const FACE_ORDER: [Face; 6] = [
    Face::Front,
    Face::Back,
    Face::Left,
    Face::Right,
    Face::Top,
    Face::Down,
];

type Turn = [[f64; 3]; 3];

/// The turns that bring a board onto itself: none, and half turns about z, x, y
const TURNS: [Turn; 4] = [
    [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
    [[-1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]],
    [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]],
    [[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]],
];
const QUARTER: Turn = [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]];

/// A hole in a piece's own axes; depth None is a hole drilled through.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct LocalHole {
    pub face: Face,
    pub point: [f64; 3],
    pub diameter: f64,
    pub depth: Option<f64>,
}

/// Pieces made the same way; the holes are the first one's.
#[derive(Clone, Debug, PartialEq)]
pub struct PartGroup {
    pub pieces: Vec<String>,
    /// Width, thickness and length
    pub size: [f64; 3],
    pub holes: Vec<LocalHole>,
}

/// The piece's holes, at their centres on the faces they are drilled into.
pub fn piece_holes(assembly: &Assembly, piece_id: &str) -> Vec<LocalHole> {
    let shape = assembly
        .model
        .piece(piece_id)
        .expect("a piece of the model")
        .shape();
    assembly
        .pilot_holes
        .iter()
        .find(|(id, _)| id == piece_id)
        .map(|(_, holes)| {
            holes
                .iter()
                .map(|(at, hole)| LocalHole {
                    face: at.face,
                    point: at.to_point(shape),
                    diameter: hole.diameter,
                    depth: hole.depth,
                })
                .collect()
        })
        .unwrap_or_default()
}

fn apply(turn: &Turn, v: [f64; 3]) -> [f64; 3] {
    std::array::from_fn(|r| (0..3).map(|k| turn[r][k] * v[k]).sum())
}

fn compose(a: &Turn, b: &Turn) -> Turn {
    std::array::from_fn(|r| std::array::from_fn(|c| (0..3).map(|k| a[r][k] * b[k][c]).sum()))
}

fn face_along(direction: [f64; 3]) -> Face {
    *FACE_ORDER
        .iter()
        .find(|face| {
            face.normal()
                .iter()
                .zip(direction)
                .all(|(&n, d)| (f64::from(n) - d).abs() < 1e-9)
        })
        .expect("a turn keeps a face's normal on an axis")
}

fn turned(holes: &[LocalHole], turn: &Turn, size: [f64; 3]) -> Vec<LocalHole> {
    let centre = size.map(|s| s / 2.0);
    holes
        .iter()
        .map(|hole| {
            let moved = apply(turn, std::array::from_fn(|i| hole.point[i] - centre[i]));
            LocalHole {
                face: face_along(apply(turn, hole.face.normal().map(f64::from))),
                point: std::array::from_fn(|i| moved[i] + centre[i]),
                ..*hole
            }
        })
        .collect()
}

/// The turns that bring a board of `size` onto itself; a square section
/// (2x2) also turns onto itself a quarter turn about its length.
fn turns(size: [f64; 3]) -> Vec<Turn> {
    if (size[0] - size[1]).abs() > TOLERANCE_MM {
        return TURNS.to_vec();
    }
    TURNS
        .iter()
        .flat_map(|turn| [*turn, compose(turn, &QUARTER)])
        .collect()
}

fn close(a: f64, b: f64) -> bool {
    (a - b).abs() <= TOLERANCE_MM
}

fn close_depth(a: Option<f64>, b: Option<f64>) -> bool {
    match (a, b) {
        (Some(a), Some(b)) => close(a, b),
        (None, None) => true,
        _ => false,
    }
}

fn same_holes(a: &[LocalHole], b: &[LocalHole]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    let mut left: Vec<&LocalHole> = b.iter().collect();
    for hole in a {
        let found = left.iter().position(|other| {
            other.face == hole.face
                && (0..3).all(|k| close(hole.point[k], other.point[k]))
                && close(hole.diameter, other.diameter)
                && close_depth(hole.depth, other.depth)
        });
        match found {
            Some(i) => {
                left.remove(i);
            }
            None => return false,
        }
    }
    true
}

/// The holes with each through hole moved to the first face of its pair:
/// drilled through, it is the same hole from either face.
fn through_on_one_side(holes: &[LocalHole], size: [f64; 3]) -> Vec<LocalHole> {
    holes
        .iter()
        .map(|hole| {
            let index = FACE_ORDER
                .iter()
                .position(|f| *f == hole.face)
                .expect("a face");
            if hole.depth.is_some() || index % 2 == 0 {
                return *hole;
            }
            let face = FACE_ORDER[index - 1];
            let mut point = hole.point;
            point[face.axis()] = if face.is_positive() {
                size[face.axis()]
            } else {
                0.0
            };
            LocalHole {
                face,
                point,
                ..*hole
            }
        })
        .collect()
}

/// Whether a board drilled with `b` is one drilled with `a`, turned.
pub(crate) fn same_part(a: &[LocalHole], b: &[LocalHole], size: [f64; 3]) -> bool {
    let a = through_on_one_side(a, size);
    turns(size)
        .iter()
        .any(|turn| same_holes(&a, &through_on_one_side(&turned(b, turn, size), size)))
}

/// The pieces grouped by how they are made, in declaration order: the same
/// lumber and length, and holes that match after a turn that brings the
/// board onto itself (a mirrored piece is a different part).
pub fn part_groups(assembly: &Assembly) -> Vec<PartGroup> {
    let mut groups: Vec<PartGroup> = Vec::new();
    for piece in &assembly.model.pieces {
        let shape = piece.shape();
        let size = [shape.width, shape.height, shape.length];
        let holes = piece_holes(assembly, &piece.id);
        let same = groups.iter_mut().find(|group| {
            let first = assembly
                .model
                .piece(&group.pieces[0])
                .expect("a piece of the model");
            first.kind == piece.kind
                && (0..3).all(|i| close(group.size[i], size[i]))
                && same_part(&group.holes, &holes, size)
        });
        match same {
            Some(group) => group.pieces.push(piece.id.clone()),
            None => groups.push(PartGroup {
                pieces: vec![piece.id.clone()],
                size,
                holes,
            }),
        }
    }
    groups
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::dsl::parse;

    const BOARD: [f64; 3] = [89.0, 38.0, 300.0];
    const SQUARE: [f64; 3] = [38.0, 38.0, 300.0];

    fn hole(face: Face, point: [f64; 3], depth: Option<f64>) -> LocalHole {
        LocalHole {
            face,
            point,
            diameter: 2.5,
            depth,
        }
    }

    #[test]
    fn a_board_turned_end_over_end_is_the_same_part() {
        let a = [hole(Face::Front, [20.0, 38.0, 100.0], Some(27.0))];
        let turned = [hole(Face::Back, [69.0, 0.0, 100.0], Some(27.0))];
        assert!(same_part(&a, &turned, BOARD));
    }

    #[test]
    fn a_mirrored_board_is_another_part() {
        let a = [hole(Face::Front, [20.0, 38.0, 100.0], Some(27.0))];
        let mirrored = [hole(Face::Front, [69.0, 38.0, 100.0], Some(27.0))];
        assert!(!same_part(&a, &mirrored, BOARD));
    }

    #[test]
    fn a_through_hole_is_the_same_from_either_face() {
        let a = [hole(Face::Front, [20.0, 38.0, 100.0], None)];
        let b = [hole(Face::Back, [20.0, 0.0, 100.0], None)];
        assert!(same_part(&a, &b, BOARD));
    }

    #[test]
    fn a_square_section_also_turns_a_quarter() {
        let a = [hole(Face::Front, [10.0, 38.0, 100.0], Some(27.0))];
        let quarter = [hole(Face::Left, [0.0, 10.0, 100.0], Some(27.0))];
        assert!(same_part(&a, &quarter, SQUARE));
        assert!(!same_part(&a, &quarter, [38.0, 38.5, 300.0]));
    }

    #[test]
    fn pieces_of_the_same_lumber_and_length_are_grouped_in_order() {
        let source =
            "(a:2x4 =300)\n(b:2x4 =300)\n(c:2x4 =400)\na -[TF<0 BD<0]- b\nb -[TF<0 BD<0]- c\n";
        let assembly = Assembly::of(parse(source).unwrap()).unwrap();
        let groups: Vec<(Vec<String>, [f64; 3])> = part_groups(&assembly)
            .into_iter()
            .map(|g| (g.pieces, g.size))
            .collect();
        assert_eq!(
            groups,
            [
                (vec!["a".to_string(), "b".to_string()], [89.0, 38.0, 300.0]),
                (vec!["c".to_string()], [89.0, 38.0, 400.0])
            ]
        );
    }
}
