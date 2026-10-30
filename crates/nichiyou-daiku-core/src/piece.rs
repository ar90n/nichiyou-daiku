//! Lumber types, their cross sections and pieces.

use crate::field::{FieldError, positive_finite};

/// The kinds of lumber a piece can be.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum PieceType {
    P1x4,
    P1x6,
    P1x8,
    P2x2,
    P2x4,
    P2x6,
}

/// The only table of lumber: name, width and thickness in mm.
const CROSS_SECTIONS: [(PieceType, &str, f64, f64); 6] = [
    (PieceType::P1x4, "1x4", 89.0, 19.0),
    (PieceType::P1x6, "1x6", 140.0, 19.0),
    (PieceType::P1x8, "1x8", 184.0, 19.0),
    (PieceType::P2x2, "2x2", 38.0, 38.0),
    (PieceType::P2x4, "2x4", 89.0, 38.0),
    (PieceType::P2x6, "2x6", 140.0, 38.0),
];

impl PieceType {
    pub const ALL: [PieceType; 6] = [
        PieceType::P1x4,
        PieceType::P1x6,
        PieceType::P1x8,
        PieceType::P2x2,
        PieceType::P2x4,
        PieceType::P2x6,
    ];

    fn entry(self) -> &'static (PieceType, &'static str, f64, f64) {
        CROSS_SECTIONS
            .iter()
            .find(|entry| entry.0 == self)
            .expect("every type is in the table")
    }

    pub fn as_str(self) -> &'static str {
        self.entry().1
    }

    pub fn parse(text: &str) -> Option<PieceType> {
        CROSS_SECTIONS
            .iter()
            .find(|entry| entry.1 == text)
            .map(|entry| entry.0)
    }

    /// Width and thickness in mm.
    pub fn cross_section(self) -> (f64, f64) {
        (self.entry().2, self.entry().3)
    }
}

/// A box of lumber: width (x), thickness (y) and length (z) in mm.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Shape3D {
    pub width: f64,
    pub height: f64,
    pub length: f64,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Piece {
    pub id: String,
    pub kind: PieceType,
    /// None while the connections have yet to fix it
    pub length: Option<f64>,
}

impl Piece {
    pub fn new(id: String, kind: PieceType, length: Option<f64>) -> Result<Piece, FieldError> {
        if let Some(length) = length {
            positive_finite("length", length)?;
        }
        Ok(Piece { id, kind, length })
    }

    /// The piece's box; only for resolved models, where every length is known.
    pub fn shape(&self) -> Shape3D {
        let length = self
            .length
            .expect("a resolved model has every length; resolve it first");
        let (width, height) = self.kind.cross_section();
        Shape3D {
            width,
            height,
            length,
        }
    }

    /// The box for checks before the model is resolved: an unknown length is
    /// unbounded, and resolving runs the checks again with the solved one.
    pub fn shape_for_checks(&self) -> Shape3D {
        let (width, height) = self.kind.cross_section();
        Shape3D {
            width,
            height,
            length: self.length.unwrap_or(f64::INFINITY),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_table_holds_every_lumber_type() {
        assert_eq!(
            PieceType::parse("2x4").unwrap().cross_section(),
            (89.0, 38.0)
        );
        assert_eq!(PieceType::P1x8.cross_section(), (184.0, 19.0));
        assert_eq!(
            PieceType::ALL.map(PieceType::as_str),
            ["1x4", "1x6", "1x8", "2x2", "2x4", "2x6"]
        );
    }

    #[test]
    fn lengths_must_be_positive_and_finite() {
        let err = |l| {
            Piece::new("a".into(), PieceType::P2x4, Some(l))
                .unwrap_err()
                .to_string()
        };
        assert_eq!(err(0.0), "length: Input should be greater than 0 (got 0.0)");
        assert_eq!(
            err(-5.0),
            "length: Input should be greater than 0 (got -5.0)"
        );
        assert_eq!(
            err(f64::INFINITY),
            "length: Input should be a finite number (got inf)"
        );
        let unknown = Piece::new("a".into(), PieceType::P2x4, None).unwrap();
        assert_eq!(unknown.shape_for_checks().length, f64::INFINITY);
    }
}
