//! The placement solver: every connection at once, exactly. Rotations are
//! quarter turns; positions are differences along each world axis, kept in a
//! weighted union-find per axis. Contradictions are reported, never averaged.

use std::collections::{HashMap, VecDeque};

use crate::anchor::{Anchor, BoundAnchor, anchor_edge, anchor_point};
use crate::geometry::{Face, Offset, SurfacePoint, edge_point};
use crate::model::Model;
use crate::piece::Shape3D;
use crate::pyfmt::round_mm;

/// A rotation by quarter turns: rows of a matrix of 0 and ±1.
pub type Mat3 = [[i32; 3]; 3];

/// The smallest and the largest corner of a box.
pub type Bounds = ([f64; 3], [f64; 3]);

pub const TOLERANCE_MM: f64 = 1e-6;
/// The gap between groups of pieces not connected to each other.
pub const GROUP_GAP_MM: f64 = 100.0;
/// Pieces overlap only when they go this deep into each other on every axis.
pub const OVERLAP_DEPTH_MM: f64 = 1e-5;
pub const IDENTITY: Mat3 = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];

fn matmul(a: &Mat3, b: &Mat3) -> Mat3 {
    std::array::from_fn(|r| std::array::from_fn(|c| (0..3).map(|k| a[r][k] * b[k][c]).sum()))
}

fn transpose(a: &Mat3) -> Mat3 {
    std::array::from_fn(|r| std::array::from_fn(|c| a[c][r]))
}

pub fn rotate(m: &Mat3, v: [f64; 3]) -> [f64; 3] {
    std::array::from_fn(|r| (0..3).map(|k| f64::from(m[r][k]) * v[k]).sum())
}

fn rotate_int(m: &Mat3, v: [i32; 3]) -> [i32; 3] {
    std::array::from_fn(|r| (0..3).map(|k| m[r][k] * v[k]).sum())
}

fn cross(a: [i32; 3], b: [i32; 3]) -> [i32; 3] {
    [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]
}

fn neg(a: [i32; 3]) -> [i32; 3] {
    a.map(|x| -x)
}

/// Columns: first, second and their cross product.
fn frame(first: [i32; 3], second: [i32; 3]) -> Mat3 {
    let third = cross(first, second);
    std::array::from_fn(|r| [first[r], second[r], third[r]])
}

/// The index of the largest absolute value, the first on a tie.
pub fn axis_index(direction: [f64; 3]) -> usize {
    let mut best = 0;
    for i in 1..3 {
        if direction[i].abs() > direction[best].abs() {
            best = i;
        }
    }
    best
}

fn int_axis_index(direction: [i32; 3]) -> usize {
    axis_index(direction.map(f64::from))
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Pose {
    pub rotation: Mat3,
    pub translation: [f64; 3],
}

impl Pose {
    pub fn apply(&self, point: [f64; 3]) -> [f64; 3] {
        let turned = rotate(&self.rotation, point);
        std::array::from_fn(|i| turned[i] + self.translation[i])
    }

    /// The smallest and the largest corner of the piece's box in the world.
    pub fn bounds(&self, shape: Shape3D) -> Bounds {
        let mut low = [f64::INFINITY; 3];
        let mut high = [f64::NEG_INFINITY; 3];
        for x in [0.0, shape.width] {
            for y in [0.0, shape.height] {
                for z in [0.0, shape.length] {
                    let world = self.apply([x, y, z]);
                    for i in 0..3 {
                        low[i] = low[i].min(world[i]);
                        high[i] = high[i].max(world[i]);
                    }
                }
            }
        }
        (low, high)
    }
}

/// How the target turns and moves against the base for the anchors to meet:
/// contact faces face each other, edge faces point the same way, anchor
/// points coincide.
pub fn relative_rotation(base: &BoundAnchor, target: &BoundAnchor) -> Mat3 {
    let (b, t) = (&base.anchor, &target.anchor);
    matmul(
        &frame(neg(b.contact.normal()), b.edge.normal()),
        &transpose(&frame(t.contact.normal(), t.edge.normal())),
    )
}

pub fn relative_pose(base: &BoundAnchor, target: &BoundAnchor) -> Pose {
    let rotation = relative_rotation(base, target);
    let (b, t) = (anchor_point(base), rotate(&rotation, anchor_point(target)));
    Pose {
        rotation,
        translation: std::array::from_fn(|i| b[i] - t[i]),
    }
}

/// The world axis along which the anchor's edge runs.
pub fn edge_axis(rotation: &Mat3, bound: &BoundAnchor) -> usize {
    let direction = cross(bound.anchor.contact.normal(), bound.anchor.edge.normal());
    int_axis_index(rotate_int(rotation, direction))
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum End {
    Down,
    Top,
}

/// A piece's end as a node of the union-find: piece index × 2 + end.
pub fn node(piece: usize, end: End) -> usize {
    piece * 2 + usize::from(end == End::Top)
}

/// The weighted union-find of one axis: each node's offset from its parent.
#[derive(Clone, Debug)]
pub struct AxisOffsets {
    parent: Vec<usize>,
    offset: Vec<f64>,
}

impl AxisOffsets {
    fn new(nodes: usize) -> AxisOffsets {
        AxisOffsets {
            parent: (0..nodes).collect(),
            offset: vec![0.0; nodes],
        }
    }

    /// The node's root and its position relative to the root.
    pub fn find(&mut self, mut node: usize) -> (usize, f64) {
        let mut path = Vec::new();
        while self.parent[node] != node {
            path.push(node);
            node = self.parent[node];
        }
        let root = node;
        let mut total = 0.0;
        for &item in path.iter().rev() {
            total += self.offset[item];
            self.offset[item] = total;
            self.parent[item] = root;
        }
        (root, path.first().map_or(0.0, |&first| self.offset[first]))
    }

    /// Require target - base = difference; the mismatch when it contradicts
    /// what is known already.
    pub fn require(&mut self, base: usize, target: usize, difference: f64) -> Option<f64> {
        let (base_root, base_offset) = self.find(base);
        let (target_root, target_offset) = self.find(target);
        if base_root == target_root {
            let mismatch = difference - (target_offset - base_offset);
            return (mismatch.abs() > TOLERANCE_MM).then_some(mismatch);
        }
        self.parent[target_root] = base_root;
        self.offset[target_root] = difference + base_offset - target_offset;
        None
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ConstraintKind {
    Rotation,
    Contact,
    Flush,
    Edge,
}

impl ConstraintKind {
    pub fn as_str(self) -> &'static str {
        match self {
            ConstraintKind::Rotation => "rotation",
            ConstraintKind::Contact => "contact",
            ConstraintKind::Flush => "flush",
            ConstraintKind::Edge => "edge",
        }
    }
}

/// A connection that contradicts the ones before it, and the loop of
/// connections it closes.
#[derive(Clone, Debug, PartialEq)]
pub struct Conflict {
    pub base_id: String,
    pub target_id: String,
    pub kind: ConstraintKind,
    pub axis: Option<usize>,
    pub mismatch_mm: Option<f64>,
    pub looped: Vec<String>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Placement {
    /// In the order of the model's pieces
    pub poses: Vec<(String, Pose)>,
    pub groups: Vec<Vec<String>>,
    pub conflicts: Vec<Conflict>,
}

impl Placement {
    pub fn pose(&self, id: &str) -> &Pose {
        &self
            .poses
            .iter()
            .find(|(piece, _)| piece == id)
            .expect("every piece has a pose")
            .1
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Overlap {
    pub lhs: String,
    pub rhs: String,
    pub volume: f64,
}

/// The shortest path from start to goal, by breadth first in the order the
/// links were made.
fn path(adjacency: &HashMap<usize, Vec<usize>>, start: usize, goal: usize) -> Vec<usize> {
    let mut previous: HashMap<usize, Option<usize>> = HashMap::from([(start, None)]);
    let mut queue = VecDeque::from([start]);
    while let Some(here) = queue.pop_front() {
        if here == goal {
            break;
        }
        for &next in adjacency.get(&here).map(Vec::as_slice).unwrap_or(&[]) {
            if let std::collections::hash_map::Entry::Vacant(entry) = previous.entry(next) {
                entry.insert(Some(here));
                queue.push_back(next);
            }
        }
    }
    let mut steps = vec![goal];
    while let Some(Some(step)) = previous.get(steps.last().expect("not empty")) {
        steps.push(*step);
    }
    steps.reverse();
    steps
}

/// The anchor point in the piece's cross section, and the end of the piece
/// it is measured from along the length (_local_anchor).
fn local_anchor(bound: &BoundAnchor) -> ([f64; 3], End) {
    let anchor = bound.anchor;
    let faces = [anchor.contact, anchor.edge];
    let along_length = !faces.contains(&Face::Top) && !faces.contains(&Face::Down);
    let end = if faces.contains(&Face::Top)
        || (along_length && matches!(anchor.offset, Some(Offset::FromMax(_))))
    {
        End::Top
    } else {
        End::Down
    };
    let offset = anchor.offset.unwrap_or(Offset::FromMin(0.0));
    let (width, height) = bound.piece.kind.cross_section();
    let shape = Shape3D {
        width,
        height,
        length: 0.0,
    };
    let fixed = Anchor {
        offset: Some(offset),
        ..anchor
    };
    let point = edge_point(shape, anchor_edge(&fixed), offset);
    (
        SurfacePoint::from_point(shape, anchor.contact, point).to_point(shape),
        end,
    )
}

pub struct PositionSolution {
    /// By piece index, relative to each group's first piece
    pub rotation: Vec<Mat3>,
    /// Piece indices, each group in declaration order, groups by their first piece
    pub groups: Vec<Vec<usize>>,
    pub offsets: [AxisOffsets; 3],
    /// Each piece's length axis and which way its length runs on it
    pub length_axis: Vec<(usize, i32)>,
    pub conflicts: Vec<Conflict>,
}

/// Solve rotations, then positions, from every connection at once
/// (placement.py: solve_positions).
pub fn solve_positions(model: &Model) -> PositionSolution {
    let count = model.pieces.len();
    let index: HashMap<&str, usize> = model
        .pieces
        .iter()
        .enumerate()
        .map(|(i, piece)| (piece.id.as_str(), i))
        .collect();
    let ids: Vec<String> = model.pieces.iter().map(|piece| piece.id.clone()).collect();
    let mut rotation = vec![IDENTITY; count];
    let mut group_of: Vec<usize> = (0..count).collect();
    let mut members: Vec<Vec<usize>> = (0..count).map(|i| vec![i]).collect();
    let mut conflicts = Vec::new();
    let mut accepted = Vec::new();
    let mut rotation_graph: HashMap<usize, Vec<usize>> = HashMap::new();
    for connection in &model.connections {
        let (base, target) = (index[connection.base_id()], index[connection.target_id()]);
        let required = matmul(
            &rotation[base],
            &relative_rotation(&connection.base, &connection.target),
        );
        if group_of[base] == group_of[target] {
            if rotation[target] != required {
                conflicts.push(Conflict {
                    base_id: ids[base].clone(),
                    target_id: ids[target].clone(),
                    kind: ConstraintKind::Rotation,
                    axis: None,
                    mismatch_mm: None,
                    looped: path(&rotation_graph, base, target)
                        .into_iter()
                        .map(|i| ids[i].clone())
                        .collect(),
                });
                continue;
            }
        } else {
            let correction = matmul(&required, &transpose(&rotation[target]));
            let (moved, into) = (group_of[target], group_of[base]);
            for &member in &members[moved] {
                rotation[member] = matmul(&correction, &rotation[member]);
            }
            let taken = std::mem::take(&mut members[moved]);
            for &member in &taken {
                group_of[member] = into;
            }
            members[into].extend(taken);
        }
        accepted.push(connection);
        rotation_graph.entry(base).or_default().push(target);
        rotation_graph.entry(target).or_default().push(base);
    }
    let mut groups: Vec<Vec<usize>> = members.into_iter().filter(|g| !g.is_empty()).collect();
    for group in &mut groups {
        group.sort_unstable();
    }
    groups.sort_by_key(|group| group[0]);
    for group in &groups {
        let to_root = transpose(&rotation[group[0]]);
        for &member in group {
            rotation[member] = matmul(&to_root, &rotation[member]);
        }
    }

    let mut offsets: [AxisOffsets; 3] = std::array::from_fn(|_| AxisOffsets::new(count * 2));
    let mut length_axis = Vec::with_capacity(count);
    for (i, piece) in model.pieces.iter().enumerate() {
        let column = [rotation[i][0][2], rotation[i][1][2], rotation[i][2][2]];
        let axis = int_axis_index(column);
        length_axis.push((axis, column[axis]));
        if let Some(length) = piece.length {
            offsets[axis].require(
                node(i, End::Down),
                node(i, End::Top),
                f64::from(column[axis]) * length,
            );
        }
    }

    let mut axis_graph: [HashMap<usize, Vec<usize>>; 3] = Default::default();
    for connection in accepted {
        let (base, target) = (index[connection.base_id()], index[connection.target_id()]);
        let (base_rot, target_rot) = (rotation[base], rotation[target]);
        let (base_point, base_end) = local_anchor(&connection.base);
        let (target_point, target_end) = local_anchor(&connection.target);
        let (b, t) = (
            rotate(&base_rot, base_point),
            rotate(&target_rot, target_point),
        );
        let difference: [f64; 3] = std::array::from_fn(|i| b[i] - t[i]);
        let sliding = connection
            .base
            .anchor
            .offset
            .is_none()
            .then(|| edge_axis(&base_rot, &connection.base));
        let contact_axis = int_axis_index(rotate_int(
            &base_rot,
            connection.base.anchor.contact.normal(),
        ));
        let flush_axis =
            int_axis_index(rotate_int(&base_rot, connection.base.anchor.edge.normal()));
        for axis in 0..3 {
            if Some(axis) == sliding {
                continue;
            }
            let base_node = node(
                base,
                if axis == length_axis[base].0 {
                    base_end
                } else {
                    End::Down
                },
            );
            let target_node = node(
                target,
                if axis == length_axis[target].0 {
                    target_end
                } else {
                    End::Down
                },
            );
            match offsets[axis].require(base_node, target_node, difference[axis]) {
                None => {
                    axis_graph[axis].entry(base).or_default().push(target);
                    axis_graph[axis].entry(target).or_default().push(base);
                }
                Some(mismatch) => {
                    let kind = if axis == contact_axis {
                        ConstraintKind::Contact
                    } else if axis == flush_axis {
                        ConstraintKind::Flush
                    } else {
                        ConstraintKind::Edge
                    };
                    conflicts.push(Conflict {
                        base_id: ids[base].clone(),
                        target_id: ids[target].clone(),
                        kind,
                        axis: Some(axis),
                        mismatch_mm: Some(round_mm(mismatch)),
                        looped: path(&axis_graph[axis], base, target)
                            .into_iter()
                            .map(|i| ids[i].clone())
                            .collect(),
                    });
                }
            }
        }
    }
    PositionSolution {
        rotation,
        groups,
        offsets,
        length_axis,
        conflicts,
    }
}

/// Every piece's pose, with groups of pieces not connected to each other laid
/// side by side along x. The model must have no unknowns.
pub fn solve_placement(model: &Model) -> Placement {
    let mut solution = solve_positions(model);
    let count = model.pieces.len();
    let mut poses: Vec<Option<Pose>> = vec![None; count];
    for group in &solution.groups {
        let root = group[0];
        let root_position: [f64; 3] =
            std::array::from_fn(|axis| solution.offsets[axis].find(node(root, End::Down)).1);
        for &member in group {
            let position: [f64; 3] =
                std::array::from_fn(|axis| solution.offsets[axis].find(node(member, End::Down)).1);
            poses[member] = Some(Pose {
                rotation: solution.rotation[member],
                translation: std::array::from_fn(|i| round_mm(position[i] - root_position[i])),
            });
        }
    }
    let mut poses: Vec<Pose> = poses
        .into_iter()
        .map(|p| p.expect("every piece is in a group"))
        .collect();
    let mut right_edge: Option<f64> = None;
    for group in &solution.groups {
        let bounds = |pose: &Pose, i: usize| pose.bounds(model.pieces[i].shape());
        let low_x = group
            .iter()
            .map(|&m| bounds(&poses[m], m).0[0])
            .fold(f64::INFINITY, f64::min);
        let high_x = group
            .iter()
            .map(|&m| bounds(&poses[m], m).1[0])
            .fold(f64::NEG_INFINITY, f64::max);
        let shift = match right_edge {
            None => 0.0,
            Some(edge) => edge + GROUP_GAP_MM - low_x,
        };
        if shift != 0.0 {
            for &member in group {
                poses[member].translation[0] = round_mm(poses[member].translation[0] + shift);
            }
        }
        right_edge = Some(match right_edge {
            None => high_x + shift,
            Some(edge) => edge.max(high_x + shift),
        });
    }
    let ids: Vec<String> = model.pieces.iter().map(|piece| piece.id.clone()).collect();
    Placement {
        poses: ids.iter().cloned().zip(poses).collect(),
        groups: solution
            .groups
            .iter()
            .map(|group| group.iter().map(|&i| ids[i].clone()).collect())
            .collect(),
        conflicts: solution.conflicts,
    }
}

/// Pieces that go into each other on every axis (placement.py: find_overlaps).
pub fn find_overlaps(model: &Model, placement: &Placement) -> Vec<Overlap> {
    let boxes: Vec<(&str, Bounds)> = model
        .pieces
        .iter()
        .map(|piece| {
            (
                piece.id.as_str(),
                placement.pose(&piece.id).bounds(piece.shape()),
            )
        })
        .collect();
    let mut overlaps = Vec::new();
    for (i, (lhs, (lhs_low, lhs_high))) in boxes.iter().enumerate() {
        for (rhs, (rhs_low, rhs_high)) in &boxes[i + 1..] {
            let sizes: [f64; 3] =
                std::array::from_fn(|a| lhs_high[a].min(rhs_high[a]) - lhs_low[a].max(rhs_low[a]));
            if sizes.iter().all(|&size| size > OVERLAP_DEPTH_MM) {
                overlaps.push(Overlap {
                    lhs: lhs.to_string(),
                    rhs: rhs.to_string(),
                    volume: sizes[0] * sizes[1] * sizes[2],
                });
            }
        }
    }
    overlaps
}

/// The smallest and the largest corner of all the pieces' boxes.
pub fn overall_bounds(model: &Model, placement: &Placement) -> Bounds {
    if model.pieces.is_empty() {
        return ([0.0; 3], [0.0; 3]);
    }
    let mut low = [f64::INFINITY; 3];
    let mut high = [f64::NEG_INFINITY; 3];
    for piece in &model.pieces {
        let (l, h) = placement.pose(&piece.id).bounds(piece.shape());
        for i in 0..3 {
            low[i] = low[i].min(l[i]);
            high[i] = high[i].max(h[i]);
        }
    }
    (low, high)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::dsl::parse;

    fn boxes(source: &str) -> (Vec<Bounds>, Placement) {
        let model = parse(source).unwrap();
        let placement = solve_placement(&model);
        let (origin, _) = overall_bounds(&model, &placement);
        let boxes = model
            .pieces
            .iter()
            .map(|piece| {
                let (low, high) = placement.pose(&piece.id).bounds(piece.shape());
                (
                    std::array::from_fn(|i| low[i] - origin[i]),
                    std::array::from_fn(|i| high[i] - origin[i]),
                )
            })
            .collect();
        (boxes, placement)
    }

    const OVERLAPPING: &str =
        "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\na -[FL<100 DF<0]- b\na -[FL<150 DF<0]- c\n";

    #[test]
    fn pieces_land_where_python_puts_them() {
        let (b, placement) = boxes(OVERLAPPING);
        assert_eq!(b[0], ([0.0, 0.0, 0.0], [89.0, 38.0, 500.0]));
        assert_eq!(b[1], ([0.0, 38.0, 11.0], [38.0, 338.0, 100.0]));
        assert_eq!(b[2], ([0.0, 38.0, 61.0], [38.0, 338.0, 150.0]));
        assert!(placement.conflicts.is_empty());
    }

    #[test]
    fn overlapping_pieces_are_found() {
        let model = parse(OVERLAPPING).unwrap();
        let overlaps = find_overlaps(&model, &solve_placement(&model));
        assert_eq!(
            overlaps,
            [Overlap {
                lhs: "b".into(),
                rhs: "c".into(),
                volume: 444600.0
            }]
        );
    }

    #[test]
    fn contradictions_name_the_loop() {
        let model = parse(
            "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\na -[FL<100 DF<0]- b\na -[FL<200 DF<0]- c\nb -[FT<0 BT<0]- c\n",
        )
        .unwrap();
        let conflicts = solve_placement(&model).conflicts;
        assert_eq!(conflicts.len(), 2);
        assert_eq!(
            (
                conflicts[0].kind,
                conflicts[0].axis,
                conflicts[0].mismatch_mm
            ),
            (ConstraintKind::Contact, Some(0), Some(-38.0))
        );
        assert_eq!(
            (
                conflicts[1].kind,
                conflicts[1].axis,
                conflicts[1].mismatch_mm
            ),
            (ConstraintKind::Edge, Some(2), Some(-100.0))
        );
        assert_eq!(conflicts[0].looped, ["b", "a", "c"]);
    }

    #[test]
    fn unconnected_groups_are_laid_side_by_side() {
        let model = parse("(a:2x4 =500)\n(b:2x4 =300)\n").unwrap();
        let placement = solve_placement(&model);
        assert_eq!(
            placement.groups,
            [vec!["a".to_string()], vec!["b".to_string()]]
        );
        assert_eq!(placement.pose("b").translation, [189.0, 0.0, 0.0]);
    }
}
