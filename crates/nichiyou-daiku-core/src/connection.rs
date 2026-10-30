//! Connections between two pieces and the checks on their fasteners.

use crate::anchor::BoundAnchor;
use crate::field::non_negative;
use crate::geometry::Face;
use crate::piece::Shape3D;
use crate::presets::ScrewType;
use crate::pyfmt::repr_f64;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum ConnectionType {
    Vanilla,
    /// A dowel `depth` long, half in each piece
    Dowel {
        radius: f64,
        depth: f64,
    },
    /// A screw through the target into the base
    Screw {
        diameter: f64,
        length: f64,
        screw_type: Option<ScrewType>,
    },
}

/// Every field error, joined as pydantic joins them.
fn fields(checks: [Result<f64, crate::field::FieldError>; 2]) -> Result<(), String> {
    let errors: Vec<String> = checks
        .into_iter()
        .filter_map(|check| check.err().map(|e| e.to_string()))
        .collect();
    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors.join("; "))
    }
}

impl ConnectionType {
    pub fn dowel(radius: f64, depth: f64) -> Result<ConnectionType, String> {
        fields([non_negative("radius", radius), non_negative("depth", depth)])?;
        Ok(ConnectionType::Dowel { radius, depth })
    }

    pub fn screw(
        diameter: f64,
        length: f64,
        screw_type: Option<ScrewType>,
    ) -> Result<ConnectionType, String> {
        fields([
            non_negative("diameter", diameter),
            non_negative("length", length),
        ])?;
        Ok(ConnectionType::Screw {
            diameter,
            length,
            screw_type,
        })
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Connection {
    pub base: BoundAnchor,
    pub target: BoundAnchor,
    pub kind: ConnectionType,
}

impl Connection {
    pub fn new(
        base: BoundAnchor,
        target: BoundAnchor,
        kind: ConnectionType,
    ) -> Result<Connection, String> {
        if base.piece.id == target.piece.id {
            return Err(format!(
                "Piece '{}' cannot be connected to itself",
                base.piece.id
            ));
        }
        if base.anchor.offset.is_none() != target.anchor.offset.is_none() {
            return Err(
                "An unknown offset (None; ? in the DSL) lets the pieces slide along the \
                shared edge, so use it on both anchors of a connection or on neither"
                    .into(),
            );
        }
        match kind {
            ConnectionType::Dowel { radius, depth } => {
                validate_dowel(&base, &target, radius * 2.0, depth)?
            }
            ConnectionType::Screw {
                diameter, length, ..
            } => validate_screw(&base, &target, diameter, length)?,
            ConnectionType::Vanilla => {}
        }
        Ok(Connection { base, target, kind })
    }

    pub fn base_id(&self) -> &str {
        &self.base.piece.id
    }

    pub fn target_id(&self) -> &str {
        &self.target.piece.id
    }
}

/// How deep a piece is behind a face: its length behind an end, its width
/// behind a narrow face, its thickness behind a wide face.
pub fn dimension_for_face(shape: Shape3D, face: Face) -> f64 {
    match face.axis() {
        2 => shape.length,
        0 => shape.width,
        _ => shape.height,
    }
}

fn min_cross_section(shape: Shape3D, face: Face) -> f64 {
    match face.axis() {
        2 => shape.width.min(shape.height),
        0 => shape.height.min(shape.length),
        _ => shape.width.min(shape.length),
    }
}

fn validate_dowel(
    base: &BoundAnchor,
    target: &BoundAnchor,
    diameter: f64,
    length: f64,
) -> Result<(), String> {
    // A dowel goes half its length into each piece; as deep as the piece is
    // thick, the hole would come out on the far face
    let per_piece_depth = length / 2.0;
    for (role, bound) in [("base", base), ("target", target)] {
        let limit = dimension_for_face(bound.piece.shape_for_checks(), bound.anchor.contact);
        if per_piece_depth >= limit {
            return Err(format!(
                "Dowel depth {}mm (half of {}mm) would go through the {role} piece ({}mm); \
                 use a dowel shorter than {}mm",
                repr_f64(per_piece_depth),
                repr_f64(length),
                repr_f64(limit),
                repr_f64(2.0 * limit)
            ));
        }
    }
    validate_fastener_diameter(base, target, diameter, "Dowel")
}

fn validate_screw(
    base: &BoundAnchor,
    target: &BoundAnchor,
    diameter: f64,
    length: f64,
) -> Result<(), String> {
    // Through an end the screw would run along the piece. Through a narrow
    // face it is counterbored down to the thickness, as through a wide face:
    // a long screw straight through a piece's width is hard to drive.
    let contact = target.anchor.contact;
    if contact.axis() == 2 {
        return Err(format!(
            "ScrewConnection target contact_face must be a side face ('front', 'back', 'left' \
             or 'right'), got '{}': the screw would run along the target's length. Make the \
             piece the screw goes through the target, touching the base with a side face",
            contact.as_str()
        ));
    }
    let base_depth = dimension_for_face(base.piece.shape_for_checks(), base.anchor.contact);
    let target_depth = target.piece.shape_for_checks().height;
    let max_length = base_depth + target_depth;
    if length >= max_length {
        return Err(format!(
            "Screw length {}mm would go through the base piece; use a screw shorter than the \
             combined depth {}mm",
            repr_f64(length),
            repr_f64(max_length)
        ));
    }
    if length <= target_depth {
        return Err(format!(
            "Screw length {}mm does not reach base piece (it goes {}mm through the target); \
             use a screw longer than {}mm",
            repr_f64(length),
            repr_f64(target_depth),
            repr_f64(target_depth)
        ));
    }
    validate_fastener_diameter(base, target, diameter, "Screw")
}

fn validate_fastener_diameter(
    base: &BoundAnchor,
    target: &BoundAnchor,
    diameter: f64,
    fastener: &str,
) -> Result<(), String> {
    let base_min = min_cross_section(base.piece.shape_for_checks(), base.anchor.contact);
    let target_min = min_cross_section(target.piece.shape_for_checks(), target.anchor.contact);
    if diameter > base_min {
        return Err(format!(
            "{fastener} diameter {}mm exceeds base piece cross-section {}mm",
            repr_f64(diameter),
            repr_f64(base_min)
        ));
    }
    if diameter > target_min {
        return Err(format!(
            "{fastener} diameter {}mm exceeds target piece cross-section {}mm",
            repr_f64(diameter),
            repr_f64(target_min)
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::anchor::{Anchor, BoundAnchor};
    use crate::geometry::{Face, Face::*, Offset};
    use crate::piece::{Piece, PieceType};

    fn bound(id: &str, length: f64, contact: Face, edge: Face) -> BoundAnchor {
        let piece = Piece::new(id.into(), PieceType::P2x4, Some(length)).unwrap();
        let anchor = Anchor::new(contact, edge, Some(Offset::FromMin(0.0))).unwrap();
        BoundAnchor::new(piece, anchor).unwrap()
    }

    #[test]
    fn screws_through_a_narrow_face_are_counterbored_to_the_thickness() {
        let base = bound("base", 1000.0, Top, Front);
        let target = bound("target", 800.0, Left, Top);
        let screw = |l| ConnectionType::screw(3.8, l, None).unwrap();
        assert!(Connection::new(base.clone(), target.clone(), screw(65.0)).is_ok());
        assert_eq!(
            Connection::new(base, target, screw(38.0)).unwrap_err(),
            "Screw length 38.0mm does not reach base piece (it goes 38.0mm through the target); use a screw longer than 38.0mm"
        );
    }

    #[test]
    fn a_screw_cannot_run_along_the_target() {
        let err = Connection::new(
            bound("b", 1000.0, Front, Top),
            bound("t", 800.0, Top, Front),
            ConnectionType::screw(4.0, 850.0, None).unwrap(),
        )
        .unwrap_err();
        assert!(
            err.starts_with("ScrewConnection target contact_face must be a side face ('front', 'back', 'left' or 'right'), got 'top'"),
            "{err}"
        );
    }

    #[test]
    fn a_dowel_must_not_go_through() {
        let err = Connection::new(
            bound("a", 500.0, Front, Left),
            bound("b", 500.0, Back, Left),
            ConnectionType::dowel(4.0, 80.0).unwrap(),
        )
        .unwrap_err();
        assert_eq!(
            err,
            "Dowel depth 40.0mm (half of 80.0mm) would go through the base piece (38.0mm); use a dowel shorter than 76.0mm"
        );
    }

    #[test]
    fn a_piece_cannot_connect_to_itself() {
        let err = Connection::new(
            bound("a", 500.0, Front, Left),
            bound("a", 500.0, Back, Left),
            ConnectionType::Vanilla,
        )
        .unwrap_err();
        assert_eq!(err, "Piece 'a' cannot be connected to itself");
    }

    #[test]
    fn negative_sizes_name_every_field() {
        assert_eq!(
            ConnectionType::dowel(-1.0, -2.0).unwrap_err(),
            "radius: Input should be greater than or equal to 0 (got -1.0); depth: Input should be greater than or equal to 0 (got -2.0)"
        );
    }
}
