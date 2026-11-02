//! What a design takes to build, for the report (resources.py:
//! extract_resources): the pieces, the fasteners, the drill sizes, where each
//! connection meets a piece and where each hole is drilled.

use crate::assembly::{Assembly, Hole};
use crate::diagnostics::describe_assembly_issues;
use crate::geometry::{Face, Offset, SurfacePoint};
use crate::hardware::{HardwareItem, count_hardware, tenth};
use crate::piece::{PieceType, Shape3D};
use crate::placement::overall_bounds;
use crate::pyfmt::round_mm;

/// Where a connection meets a piece, as the report's anchor table gives it.
#[derive(Clone, Debug, PartialEq)]
pub struct AnchorInfo {
    pub contact_face: &'static str,
    pub edge_face: &'static str,
    pub offset_type: &'static str,
    pub offset_value: f64,
}

/// A hole measured from the edges of the face it is drilled into.
#[derive(Clone, Debug, PartialEq)]
pub struct PilotHoleInfo {
    pub face: &'static str,
    pub from_length_edge: f64,
    pub from_width_edge: f64,
    pub diameter: f64,
    pub depth: Option<f64>,
    pub countersink: Option<f64>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct PieceResource {
    pub id: String,
    pub kind: PieceType,
    pub length: f64,
    pub width: f64,
    pub height: f64,
    pub volume: f64,
    pub anchors: Vec<AnchorInfo>,
    pub pilot_holes: Vec<PilotHoleInfo>,
}

/// A drill size: how many holes, and the deepest (None when one goes through).
#[derive(Clone, Debug, PartialEq)]
pub struct DrillBit {
    pub diameter: f64,
    pub holes: usize,
    pub deepest: Option<f64>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct ResourceSummary {
    pub pieces: Vec<PieceResource>,
    /// Each lumber type in the order it first comes: its count and total length
    pub by_type: Vec<(PieceType, usize, f64)>,
    pub total_volume: f64,
    pub overall_size: Option<[f64; 3]>,
    pub size_reference: Option<String>,
    /// Every problem but overlaps: what the other commands warn about
    pub issues: Vec<String>,
    pub hardware: Vec<HardwareItem>,
    pub drill_bits: Vec<DrillBit>,
    /// Countersinks by the width of their mouth, narrowest first, with how many
    pub countersinks: Vec<(f64, usize)>,
}

fn pilot_hole_info(position: SurfacePoint, hole: Hole, shape: Shape3D) -> PilotHoleInfo {
    let point = position.to_point(shape);
    // Side faces all measure along the length, so they read alike
    let (along, across) = match position.face {
        Face::Top | Face::Down => (point[0], point[1]),
        Face::Left | Face::Right => (point[2], point[1]),
        Face::Front | Face::Back => (point[2], point[0]),
    };
    PilotHoleInfo {
        face: position.face.as_str(),
        from_length_edge: along,
        from_width_edge: across,
        diameter: hole.diameter,
        depth: hole.depth,
        countersink: hole.countersink,
    }
}

fn drill_bits(assembly: &Assembly) -> Vec<DrillBit> {
    let mut depths: Vec<(f64, Vec<Option<f64>>)> = Vec::new();
    for (_, holes) in &assembly.pilot_holes {
        for (_, hole) in holes {
            let size = tenth(hole.diameter);
            match depths.iter_mut().find(|(d, _)| *d == size) {
                Some((_, found)) => found.push(hole.depth),
                None => depths.push((size, vec![hole.depth])),
            }
        }
    }
    depths.sort_by(|a, b| a.0.total_cmp(&b.0));
    depths
        .into_iter()
        .map(|(diameter, found)| {
            let blind: Vec<f64> = found.iter().flatten().copied().collect();
            let deepest = (blind.len() == found.len())
                .then(|| blind.iter().copied().fold(f64::NEG_INFINITY, f64::max));
            DrillBit {
                diameter,
                holes: found.len(),
                deepest,
            }
        })
        .collect()
}

pub fn extract_resources(assembly: &Assembly) -> ResourceSummary {
    let model = &assembly.model;
    let mut anchors: Vec<(String, Vec<AnchorInfo>)> = Vec::new();
    for connection in &model.connections {
        for bound in [&connection.base, &connection.target] {
            let offset = bound
                .anchor
                .offset
                .expect("a resolved model knows every offset");
            let info = AnchorInfo {
                contact_face: bound.anchor.contact.as_str(),
                edge_face: bound.anchor.edge.as_str(),
                offset_type: match offset {
                    Offset::FromMin(_) => "FromMin",
                    Offset::FromMax(_) => "FromMax",
                },
                offset_value: offset.value(),
            };
            match anchors.iter_mut().find(|(id, _)| *id == bound.piece.id) {
                Some((_, list)) => list.push(info),
                None => anchors.push((bound.piece.id.clone(), vec![info])),
            }
        }
    }
    let mut pieces = Vec::new();
    let mut by_type: Vec<(PieceType, usize, f64)> = Vec::new();
    let mut total_volume = 0.0;
    for piece in &model.pieces {
        let shape = piece.shape();
        let volume = shape.width * shape.height * shape.length;
        let pilot_holes = assembly
            .pilot_holes
            .iter()
            .find(|(id, _)| *id == piece.id)
            .map(|(_, holes)| {
                holes
                    .iter()
                    .map(|(at, hole)| pilot_hole_info(*at, *hole, shape))
                    .collect()
            })
            .unwrap_or_default();
        pieces.push(PieceResource {
            id: piece.id.clone(),
            kind: piece.kind,
            length: shape.length,
            width: shape.width,
            height: shape.height,
            volume,
            anchors: anchors
                .iter()
                .find(|(id, _)| *id == piece.id)
                .map(|(_, a)| a.clone())
                .unwrap_or_default(),
            pilot_holes,
        });
        match by_type.iter_mut().find(|(kind, _, _)| *kind == piece.kind) {
            Some((_, count, total)) => {
                *count += 1;
                *total += shape.length;
            }
            None => by_type.push((piece.kind, 1, shape.length)),
        }
        total_volume += volume;
    }
    let mut countersinks: Vec<(f64, usize)> = Vec::new();
    for (_, holes) in &assembly.pilot_holes {
        for (_, hole) in holes {
            if let Some(sink) = hole.countersink.map(tenth) {
                match countersinks.iter_mut().find(|(d, _)| *d == sink) {
                    Some((_, n)) => *n += 1,
                    None => countersinks.push((sink, 1)),
                }
            }
        }
    }
    countersinks.sort_by(|a, b| a.0.total_cmp(&b.0));
    let (overall_size, size_reference) = if assembly.placement.groups.len() == 1 {
        let (low, high) = overall_bounds(model, &assembly.placement);
        (
            Some(std::array::from_fn(|i| round_mm(high[i] - low[i]))),
            Some(assembly.placement.groups[0][0].clone()),
        )
    } else {
        (None, None)
    };
    let issues = describe_assembly_issues(assembly);
    ResourceSummary {
        pieces,
        by_type,
        total_volume,
        overall_size,
        size_reference,
        issues,
        hardware: count_hardware(assembly, None),
        drill_bits: drill_bits(assembly),
        countersinks,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::dsl::parse;

    fn summary(source: &str) -> ResourceSummary {
        extract_resources(&Assembly::of(parse(source).unwrap()).unwrap())
    }

    #[test]
    fn pieces_are_counted_by_type_in_the_order_they_come() {
        let s = summary("(p1:2x4 =1000)\n(p2:2x4 =800)\n(p3:1x4 =600)\n");
        assert_eq!(s.pieces.len(), 3);
        assert_eq!(
            s.by_type,
            [(PieceType::P2x4, 2, 1800.0), (PieceType::P1x4, 1, 600.0)]
        );
        assert_eq!(s.pieces[0].volume, 89.0 * 38.0 * 1000.0);
        // Three unconnected pieces: no overall size, and a problem to report
        assert_eq!(s.overall_size, None);
        assert!(!s.issues.is_empty());
    }

    #[test]
    fn a_connection_gives_both_pieces_an_anchor() {
        let s = summary("(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n");
        let a = &s.pieces[0];
        assert_eq!(a.anchors.len(), 1);
        assert_eq!(
            (
                a.anchors[0].contact_face,
                a.anchors[0].edge_face,
                a.anchors[0].offset_type
            ),
            ("top", "front", "FromMin")
        );
        assert_eq!(
            (
                s.pieces[1].anchors[0].contact_face,
                s.pieces[1].anchors[0].edge_face
            ),
            ("back", "down")
        );
        assert_eq!(s.overall_size, Some([89.0, 400.0, 438.0]));
        assert_eq!(s.size_reference.as_deref(), Some("a"));
        assert!(s.issues.is_empty());
    }

    #[test]
    fn holes_are_measured_on_their_face_and_their_bits_listed() {
        let s = summary("(left:2x4 =800)\n(shelf:2x4 =600)\nleft -[BL<300 DL<0 D(:8x30)]- shelf\n");
        let holes: Vec<&PilotHoleInfo> = s.pieces.iter().flat_map(|p| &p.pilot_holes).collect();
        assert!(!holes.is_empty());
        assert!(holes.iter().all(|h| h.diameter == 8.0));
        assert_eq!(s.drill_bits.len(), 1);
        assert_eq!(
            (s.drill_bits[0].diameter, s.drill_bits[0].holes),
            (8.0, holes.len())
        );
        assert_eq!(s.hardware[0].name, "Dowel 8x30");
    }

    #[test]
    fn countersinks_are_counted_by_their_mouth() {
        let s = summary(
            "(base:2x4 =500)\n(target:1x4 =300)\nbase -[FL<100 BL<0 S(Slim:3.3x25)]- target\n",
        );
        assert_eq!(s.countersinks, [(6.5, 2)]);
        let target = s.pieces.iter().find(|p| p.id == "target").unwrap();
        assert!(
            target
                .pilot_holes
                .iter()
                .all(|h| h.face == "front" && h.countersink == Some(6.5))
        );
        let dowels =
            summary("(left:2x4 =800)\n(shelf:2x4 =600)\nleft -[BL<300 DL<0 D(:8x30)]- shelf\n");
        assert!(dowels.countersinks.is_empty());
    }
}
