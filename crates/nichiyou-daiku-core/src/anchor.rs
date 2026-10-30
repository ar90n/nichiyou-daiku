//! Where on a piece a connection attaches.

use crate::geometry::{Edge, Face, Offset, SurfacePoint, edge_length, edge_point};
use crate::piece::Piece;
use crate::pyfmt::repr_f64;

/// How far an offset may pass the end of its edge before it is an error.
pub const OFFSET_TOLERANCE_MM: f64 = 1e-6;

/// The face that touches the other piece, an adjacent face that shares the
/// edge, and where along that edge the anchor point is (None: unknown).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Anchor {
    pub contact: Face,
    pub edge: Face,
    pub offset: Option<Offset>,
}

impl Anchor {
    pub fn new(contact: Face, edge: Face, offset: Option<Offset>) -> Result<Anchor, String> {
        if !contact.is_adjacent(edge) {
            return Err(format!(
                "contact_face '{}' and edge_shared_face '{}' must be adjacent faces",
                contact.as_str(),
                edge.as_str()
            ));
        }
        Ok(Anchor {
            contact,
            edge,
            offset,
        })
    }
}

/// The anchor's edge, ordered so that it runs the positive way (_get_pos_dir_edge).
pub fn anchor_edge(anchor: &Anchor) -> Edge {
    let third = Face::cross(anchor.contact, anchor.edge).expect("anchor faces are adjacent");
    if third.is_positive() {
        Edge {
            lhs: anchor.contact,
            rhs: anchor.edge,
        }
    } else {
        Edge {
            lhs: anchor.edge,
            rhs: anchor.contact,
        }
    }
}

/// An anchor on a particular piece.
#[derive(Clone, Debug, PartialEq)]
pub struct BoundAnchor {
    pub piece: Piece,
    pub anchor: Anchor,
}

impl BoundAnchor {
    pub fn new(piece: Piece, anchor: Anchor) -> Result<BoundAnchor, String> {
        if let Some(offset) = anchor.offset {
            let longest = edge_length(piece.shape_for_checks(), anchor_edge(&anchor));
            if offset.value() > longest + OFFSET_TOLERANCE_MM {
                return Err(format!(
                    "Offset {}mm exceeds piece dimension {}mm (piece '{}', edge {}/{})",
                    repr_f64(offset.value()),
                    repr_f64(longest),
                    piece.id,
                    anchor.contact.as_str(),
                    anchor.edge.as_str()
                ));
            }
        }
        Ok(BoundAnchor { piece, anchor })
    }
}

/// The anchor point in the piece's coordinates (as_point_3d); the offset and
/// the length must be known.
pub fn anchor_point(bound: &BoundAnchor) -> [f64; 3] {
    let shape = bound.piece.shape();
    let offset = bound
        .anchor
        .offset
        .expect("a resolved model has every offset; resolve it first");
    let point = edge_point(shape, anchor_edge(&bound.anchor), offset);
    // Through the contact face, as the Python version goes, for the same rounding
    SurfacePoint::from_point(shape, bound.anchor.contact, point).to_point(shape)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::geometry::{Face::*, Offset};
    use crate::piece::{Piece, PieceType};

    #[test]
    fn faces_must_be_adjacent_and_offsets_on_the_edge() {
        assert_eq!(
            Anchor::new(Front, Back, None).unwrap_err(),
            "contact_face 'front' and edge_shared_face 'back' must be adjacent faces"
        );
        let piece = Piece::new("a".into(), PieceType::P2x4, Some(500.0)).unwrap();
        let anchor = Anchor::new(Top, Left, Some(Offset::FromMin(50.0))).unwrap();
        assert_eq!(
            BoundAnchor::new(piece, anchor).unwrap_err(),
            "Offset 50.0mm exceeds piece dimension 38.0mm (piece 'a', edge top/left)"
        );
    }

    #[test]
    fn the_anchor_point_of_the_worked_example() {
        let leg = Piece::new("leg".into(), PieceType::P2x4, Some(700.0)).unwrap();
        let anchor = Anchor::new(Front, Left, Some(Offset::FromMin(100.0))).unwrap();
        let bound = BoundAnchor::new(leg, anchor).unwrap();
        assert_eq!(anchor_point(&bound), [0.0, 38.0, 100.0]);
    }
}
