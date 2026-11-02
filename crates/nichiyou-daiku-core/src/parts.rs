//! The parts to make before assembling: pieces grouped when they are made
//! the same (parts.py: part_groups). A piece's axes: x across its width, y
//! across its thickness, z along its length, from 0 at one corner.

use crate::assembly::Assembly;
use crate::dimensioning::{Side, chain_from_stops};
use crate::geometry::Face;
use crate::model::Model;
use crate::pyfmt::format_mm;

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
    /// The mouth of a countersink for a screw head, if any
    pub countersink: Option<f64>,
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
                    countersink: hole.countersink,
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
                && close_depth(hole.countersink, other.countersink)
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
            // A countersunk hole is drilled from its own face
            if hole.depth.is_some() || hole.countersink.is_some() || index % 2 == 0 {
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

/// The faces a drill reaches along the board's length.
pub const LONG_FACES: [Face; 4] = [Face::Front, Face::Back, Face::Left, Face::Right];

/// The 8 diagonal views of the isometric, in the order ties are broken.
pub const VIEW_ORDER: [[i32; 3]; 8] = [
    [1, 1, 1],
    [1, -1, 1],
    [-1, 1, 1],
    [-1, -1, 1],
    [1, 1, -1],
    [1, -1, -1],
    [-1, 1, -1],
    [-1, -1, -1],
];

fn cross(a: [f64; 3], b: [f64; 3]) -> [f64; 3] {
    [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]
}

fn dot(a: [f64; 3], b: [f64; 3]) -> f64 {
    (0..3).map(|i| a[i] * b[i]).sum()
}

/// Right and up of a face seen from outside (right × up points out): a long
/// face has its length to the right, the top end its width, the down end
/// its width the other way.
pub fn face_frame(face: Face) -> ([f64; 3], [f64; 3]) {
    let right = match face {
        Face::Top => [1.0, 0.0, 0.0],
        Face::Down => [-1.0, 0.0, 0.0],
        _ => [0.0, 0.0, 1.0],
    };
    let up = cross(face.normal().map(f64::from), right).map(|x| x + 0.0);
    (right, up)
}

/// Width and height of a face seen from outside.
pub fn face_size(face: Face, size: [f64; 3]) -> (f64, f64) {
    let (right, up) = face_frame(face);
    (dot(right, size).abs(), dot(up, size).abs())
}

/// A point of the face from its lower-left corner seen from outside.
pub fn face_point(face: Face, point: [f64; 3], size: [f64; 3]) -> (f64, f64) {
    let (right, up) = face_frame(face);
    // The face spans 0..size on each axis, so the corner is at the minimum
    let from_corner = |axis: [f64; 3]| {
        dot(point, axis) - (0..3).map(|i| (axis[i] * size[i]).min(0.0)).sum::<f64>()
    };
    (from_corner(right), from_corner(up))
}

/// The faces across each edge of a face seen from outside.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Neighbours {
    pub top: Face,
    pub bottom: Face,
    pub left: Face,
    pub right: Face,
}

pub fn edge_neighbours(face: Face) -> Neighbours {
    let (right, up) = face_frame(face);
    let minus = |v: [f64; 3]| v.map(|x| -x);
    Neighbours {
        top: face_along(up),
        bottom: face_along(minus(up)),
        left: face_along(minus(right)),
        right: face_along(right),
    }
}

/// Whether the ends' turns about z are tied without a reference: one end's
/// holes look the same after every turn about z that brings the section
/// onto itself, so that end can be drilled turned any way.
fn end_turns_free(holes: &[LocalHole], size: [f64; 3]) -> bool {
    let about_z: Vec<Turn> = turns(size)
        .into_iter()
        .filter(|turn| turn[2][2] == 1.0)
        .collect();
    [Face::Top, Face::Down].iter().any(|&end| {
        let on_end: Vec<LocalHole> = holes.iter().filter(|h| h.face == end).copied().collect();
        about_z
            .iter()
            .all(|turn| same_holes(&on_end, &turned(&on_end, turn, size)))
    })
}

/// A, B, ... for the drilled faces in FACE_ORDER. A face without holes gets
/// one only when nothing else ties the two ends' turn together: both ends
/// drilled, no long face drilled and neither end's holes the same after
/// every turn about the length; then the front is lettered too.
pub fn face_letters(holes: &[LocalHole], size: [f64; 3]) -> Vec<(Face, char)> {
    let drilled: Vec<Face> = FACE_ORDER
        .into_iter()
        .filter(|f| holes.iter().any(|h| h.face == *f))
        .collect();
    let mut lettered = drilled.clone();
    if drilled.contains(&Face::Top)
        && drilled.contains(&Face::Down)
        && !drilled.iter().any(|f| LONG_FACES.contains(f))
        && !end_turns_free(holes, size)
    {
        lettered.push(Face::Front);
    }
    lettered.into_iter().zip('A'..).collect()
}

/// The diagonal view that shows the most of `faces`; the first on a tie.
pub fn view_direction(faces: &[Face]) -> [i32; 3] {
    let shown = |d: &[i32; 3]| {
        faces
            .iter()
            .filter(|f| (0..3).map(|i| f.normal()[i] * d[i]).sum::<i32>() > 0)
            .count()
    };
    let mut best = VIEW_ORDER[0];
    for d in &VIEW_ORDER[1..] {
        if shown(d) > shown(&best) {
            best = *d;
        }
    }
    best
}

/// The pieces, with how many when there are more than one.
pub fn part_name(group: &PartGroup) -> String {
    let count = group.pieces.len();
    let names = group.pieces.join(", ");
    if count > 1 {
        format!("{names} ×{count}")
    } else {
        names
    }
}

/// Pieces, count, lumber, length and holes per piece, e.g.
/// `shelf_1, shelf_2 ×2   2x4   300   φ8 ↧15 ×2`.
pub fn part_title(model: &Model, group: &PartGroup) -> String {
    let lumber = model
        .piece(&group.pieces[0])
        .expect("a piece of the model")
        .kind
        .as_str();
    let mut kinds: Vec<((f64, Option<f64>), usize)> = Vec::new();
    for hole in &group.holes {
        let key = (hole.diameter, hole.depth);
        match kinds.iter_mut().find(|(k, _)| *k == key) {
            Some((_, n)) => *n += 1,
            None => kinds.push((key, 1)),
        }
    }
    // By diameter; of one diameter, blind holes before through holes
    kinds.sort_by(|((d1, p1), _), ((d2, p2), _)| {
        d1.total_cmp(d2)
            .then(p1.is_none().cmp(&p2.is_none()))
            .then(p1.unwrap_or(0.0).total_cmp(&p2.unwrap_or(0.0)))
    });
    let mut fields = vec![
        part_name(group),
        lumber.to_string(),
        format_mm(group.size[2]),
    ];
    for ((diameter, depth), n) in kinds {
        let deep = depth.map_or(String::new(), |d| format!(" ↧{}", format_mm(d)));
        fields.push(format!("φ{}{deep} ×{n}", format_mm(diameter)));
    }
    fields.join("   ")
}

/// A drilled face's stops for its hole dimensions, along its right and up.
#[derive(Clone, Debug, PartialEq)]
pub struct FaceStops {
    pub face: Face,
    pub right: Vec<f64>,
    pub up: Vec<f64>,
}

/// What a part drawing says, without where it is drawn.
#[derive(Clone, Debug, PartialEq)]
pub struct PartFacts {
    pub title: String,
    pub letters: Vec<(Face, char)>,
    /// The drilled faces, in the order of their letters
    pub faces: Vec<FaceStops>,
}

pub fn part_facts(model: &Model, group: &PartGroup) -> PartFacts {
    let letters = face_letters(&group.holes, group.size);
    let faces = letters
        .iter()
        .filter(|(face, _)| group.holes.iter().any(|h| h.face == *face))
        .map(|&(face, _)| {
            let (width, height) = face_size(face, group.size);
            let (mut us, mut vs) = (vec![0.0, width], vec![0.0, height]);
            for hole in group.holes.iter().filter(|h| h.face == face) {
                let (u, v) = face_point(face, hole.point, group.size);
                us.push(u);
                vs.push(v);
            }
            FaceStops {
                face,
                right: chain_from_stops(0, Side::Below, &us).stops,
                up: chain_from_stops(2, Side::Left, &vs).stops,
            }
        })
        .collect();
    PartFacts {
        title: part_title(model, group),
        letters,
        faces,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::dsl::parse;

    fn drilled(face: Face, point: [f64; 3]) -> LocalHole {
        LocalHole {
            face,
            point,
            diameter: 2.5,
            depth: Some(27.0),
            countersink: None,
        }
    }

    #[test]
    fn faces_are_seen_from_outside() {
        assert_eq!(face_frame(Face::Front), ([0.0, 0.0, 1.0], [1.0, 0.0, 0.0]));
        assert_eq!(face_frame(Face::Down), ([-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]));
        assert_eq!(face_size(Face::Front, [89.0, 38.0, 300.0]), (300.0, 89.0));
        assert_eq!(
            face_point(Face::Back, [20.0, 0.0, 100.0], [89.0, 38.0, 300.0]),
            (100.0, 69.0)
        );
        assert_eq!(
            face_point(Face::Down, [20.0, 0.0, 100.0], [89.0, 38.0, 300.0]),
            (69.0, 0.0)
        );
        let n = edge_neighbours(Face::Front);
        assert_eq!(
            (n.top, n.bottom, n.left, n.right),
            (Face::Right, Face::Left, Face::Down, Face::Top)
        );
    }

    #[test]
    fn drilled_faces_are_lettered_and_a_tied_end_also_letters_the_front() {
        let size = [89.0, 38.0, 300.0];
        assert_eq!(
            face_letters(
                &[
                    drilled(Face::Back, [20.0, 0.0, 100.0]),
                    drilled(Face::Front, [20.0, 38.0, 100.0])
                ],
                size
            ),
            [(Face::Front, 'A'), (Face::Back, 'B')]
        );
        assert_eq!(
            face_letters(
                &[
                    drilled(Face::Top, [20.0, 19.0, 300.0]),
                    drilled(Face::Down, [20.0, 19.0, 0.0])
                ],
                size
            ),
            [(Face::Top, 'A'), (Face::Down, 'B'), (Face::Front, 'C')]
        );
        // A centred hole looks the same turned: that end turns freely
        assert_eq!(
            face_letters(
                &[
                    drilled(Face::Top, [44.5, 19.0, 300.0]),
                    drilled(Face::Down, [20.0, 19.0, 0.0])
                ],
                size
            ),
            [(Face::Top, 'A'), (Face::Down, 'B')]
        );
    }

    #[test]
    fn the_isometric_shows_the_most_lettered_faces() {
        assert_eq!(view_direction(&[Face::Front, Face::Top]), [1, 1, 1]);
        assert_eq!(view_direction(&[Face::Back, Face::Down]), [1, -1, -1]);
        assert_eq!(view_direction(&[Face::Left]), [-1, 1, 1]);
        assert_eq!(view_direction(&[]), [1, 1, 1]);
    }

    #[test]
    fn titles_name_the_pieces_lumber_length_and_holes() {
        let source = "(post:2x4 =600)\n(rail:2x4 =400)\n(rail_low:2x4 =400)\n(cleat:2x4 =400)\n(shelf:2x4 =400)\n\
            post -[FL<300 BT<0 S(Slim:3.3x50)]- rail\npost -[FL<100 BT<0 S(3.5, 50)]- rail_low\n\
            post -[BT<0 FT<0 S(Coarse:3.8x57)]- cleat\npost -[BL<300 DL<0 D(:8x30)]- shelf\n";
        let assembly = Assembly::of(parse(source).unwrap()).unwrap();
        let groups = part_groups(&assembly);
        assert_eq!(
            part_title(&assembly.model, &groups[0]),
            "post   2x4   600   φ2 ↧12 ×2   φ2.5 ↧12 ×2   φ2.5 ↧19 ×2   φ8 ↧15 ×2"
        );
        assert_eq!(
            part_title(&assembly.model, &groups[1]),
            "rail   2x4   400   φ2 ×2"
        );
        let shelf = "(left_side:2x4 =800)\n(right_side:2x4 =800)\n(shelf:2x4 =600)\n\
            left_side -[BL<300 DL<0 D(:8x30)]- shelf\nright_side -[FL<300 TL<0 D(:8x30)]- shelf\n";
        let assembly = Assembly::of(parse(shelf).unwrap()).unwrap();
        let groups = part_groups(&assembly);
        assert_eq!(
            part_title(&assembly.model, &groups[0]),
            "left_side, right_side ×2   2x4   800   φ8 ↧15 ×2"
        );
        let facts = part_facts(&assembly.model, &groups[0]);
        assert_eq!(facts.letters, [(Face::Back, 'A')]);
        assert_eq!(facts.faces.len(), 1);
        assert_eq!(
            (
                facts.faces[0].face,
                facts.faces[0].right[0],
                *facts.faces[0].right.last().unwrap()
            ),
            (Face::Back, 0.0, 800.0)
        );
    }

    const BOARD: [f64; 3] = [89.0, 38.0, 300.0];
    const SQUARE: [f64; 3] = [38.0, 38.0, 300.0];

    fn hole(face: Face, point: [f64; 3], depth: Option<f64>) -> LocalHole {
        LocalHole {
            face,
            point,
            diameter: 2.5,
            depth,
            countersink: None,
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

    #[test]
    fn a_countersunk_hole_stays_on_its_face_when_parts_are_compared() {
        let sunk = |face: Face, y: f64| LocalHole {
            face,
            point: [44.5, y, 100.0],
            diameter: 2.5,
            depth: None,
            countersink: Some(7.5),
        };
        // Countersunk from the front or from the back: a half turn about the
        // length brings one onto the other
        assert!(same_part(
            &[sunk(Face::Front, 38.0)],
            &[sunk(Face::Back, 0.0)],
            BOARD
        ));
        // A plain through hole is the same from either face, a countersunk one is not
        let plain = LocalHole {
            countersink: None,
            ..sunk(Face::Back, 0.0)
        };
        assert!(!same_part(&[sunk(Face::Front, 38.0)], &[plain], BOARD));
    }
}
