//! The 3D shape of a design for other tools: each piece a box with its
//! holes, as STEP (exact faces) and STL (triangles).

pub mod bore;
pub mod mesh;
pub mod solid;
pub mod step;
pub mod stl;

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_core::parts::piece_holes;
use nichiyou_daiku_core::pyfmt::format_mm;

use crate::bore::{Left, bores, face_axis, others};
use crate::solid::{Solid, piece_solid};

/// The design's solids, one per piece in model order, and what to tell
/// about holes left out.
pub struct Model {
    pub solids: Vec<Solid>,
    pub warnings: Vec<String>,
}

pub fn model(assembly: &Assembly) -> Model {
    let mut solids = Vec::new();
    let mut warnings = Vec::new();
    for piece in &assembly.model.pieces {
        let shape = piece.shape();
        let size = [shape.width, shape.height, shape.length];
        let (kept, left) = bores(&piece_holes(assembly, &piece.id), size);
        for (hole, why) in left {
            let (axis, _) = face_axis(hole.face);
            let at: Vec<String> = others(axis)
                .iter()
                .map(|&i| format_mm(hole.point[i]))
                .collect();
            let what = format!(
                "{}: the φ{} hole at {} ({})",
                piece.id,
                format_mm(hole.diameter),
                hole.face.as_str(),
                at.join(", ")
            );
            warnings.push(match why {
                Left::RunsIntoAnother => format!(
                    "{what} runs into another hole; it is left out of the 3D. Fix the collision validate reports"
                ),
                Left::BreaksOut { radius } => format!(
                    "{what} breaks out of the piece's side; it is left out of the 3D. Move the joint so the hole's centre is more than {}mm from the piece's edge",
                    format_mm(radius)
                ),
            });
        }
        solids.push(piece_solid(
            &piece.id,
            size,
            &kept,
            assembly.placement.pose(&piece.id),
        ));
    }
    Model { solids, warnings }
}
