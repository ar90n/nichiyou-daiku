//! Faces, edges, offsets and points on a piece of lumber.

use crate::field::{FieldError, non_negative};
use crate::piece::Shape3D;
use crate::pyfmt::repr_f64;

/// The six faces of a piece: top/down are the ends (z), left/right the
/// narrow faces (x), front/back the wide faces (y).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum Face {
    Top,
    Down,
    Left,
    Right,
    Front,
    Back,
}

impl Face {
    pub const ALL: [Face; 6] = [
        Face::Top,
        Face::Down,
        Face::Left,
        Face::Right,
        Face::Front,
        Face::Back,
    ];

    pub fn as_str(self) -> &'static str {
        match self {
            Face::Top => "top",
            Face::Down => "down",
            Face::Left => "left",
            Face::Right => "right",
            Face::Front => "front",
            Face::Back => "back",
        }
    }

    pub fn parse(text: &str) -> Option<Face> {
        Face::ALL.into_iter().find(|face| face.as_str() == text)
    }

    pub fn opposite(self) -> Face {
        match self {
            Face::Top => Face::Down,
            Face::Down => Face::Top,
            Face::Left => Face::Right,
            Face::Right => Face::Left,
            Face::Front => Face::Back,
            Face::Back => Face::Front,
        }
    }

    pub fn is_positive(self) -> bool {
        matches!(self, Face::Top | Face::Right | Face::Front)
    }

    /// 0 for left/right (x), 1 for back/front (y), 2 for down/top (z).
    pub fn axis(self) -> usize {
        match self {
            Face::Left | Face::Right => 0,
            Face::Back | Face::Front => 1,
            Face::Down | Face::Top => 2,
        }
    }

    pub fn is_adjacent(self, other: Face) -> bool {
        self != other && self.axis() != other.axis()
    }

    pub fn normal(self) -> [i32; 3] {
        let mut normal = [0; 3];
        normal[self.axis()] = if self.is_positive() { 1 } else { -1 };
        normal
    }

    /// The face the cross product of the two faces' normals points to
    /// (face.py: cross).
    pub fn cross(lhs: Face, rhs: Face) -> Result<Face, String> {
        let (mut lhs, mut rhs) = (lhs, rhs);
        if !lhs.is_positive() {
            (lhs, rhs) = (rhs, lhs.opposite());
        }
        if !lhs.is_positive() {
            (lhs, rhs) = (rhs, lhs.opposite());
        }
        if !rhs.is_positive() {
            (lhs, rhs) = (rhs.opposite(), lhs);
        }
        match (lhs, rhs) {
            (Face::Top, Face::Front) => Ok(Face::Left),
            (Face::Front, Face::Top) => Ok(Face::Right),
            (Face::Right, Face::Top) => Ok(Face::Back),
            (Face::Top, Face::Right) => Ok(Face::Front),
            (Face::Front, Face::Right) => Ok(Face::Down),
            (Face::Right, Face::Front) => Ok(Face::Top),
            _ => Err(format!(
                "Invalid face combination: {}, {}",
                lhs.as_str(),
                rhs.as_str()
            )),
        }
    }
}

/// Where along an edge a point is: from its min end or its max end.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Offset {
    FromMin(f64),
    FromMax(f64),
}

impl Offset {
    pub fn from_min(value: f64) -> Result<Offset, FieldError> {
        non_negative("value", value).map(Offset::FromMin)
    }

    pub fn from_max(value: f64) -> Result<Offset, FieldError> {
        non_negative("value", value).map(Offset::FromMax)
    }

    pub fn value(self) -> f64 {
        match self {
            Offset::FromMin(value) | Offset::FromMax(value) => value,
        }
    }

    /// The distance from the min end of an edge this long.
    pub fn evaluate(self, length: f64) -> f64 {
        match self {
            Offset::FromMax(value) => length - value,
            Offset::FromMin(value) => value,
        }
    }

    /// As the Python version's pydantic model prints itself.
    pub fn repr(self) -> String {
        match self {
            Offset::FromMin(value) => format!("FromMin(value={})", repr_f64(value)),
            Offset::FromMax(value) => format!("FromMax(value={})", repr_f64(value)),
        }
    }
}

/// The edge where two adjacent faces meet.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Edge {
    pub lhs: Face,
    pub rhs: Face,
}

fn third_face(lhs: Face, rhs: Face) -> Face {
    Face::cross(lhs, rhs).expect("an edge joins adjacent faces")
}

pub fn edge_length(shape: Shape3D, edge: Edge) -> f64 {
    match third_face(edge.lhs, edge.rhs).axis() {
        0 => shape.width,
        1 => shape.height,
        _ => shape.length,
    }
}

fn corner_point(shape: Shape3D, faces: [Face; 3]) -> [f64; 3] {
    let size = [shape.width, shape.height, shape.length];
    let mut point = [0.0; 3];
    for face in faces {
        if face.is_positive() {
            point[face.axis()] = size[face.axis()];
        }
    }
    point
}

/// The point at `offset` along the edge, from the corner it starts at
/// (Point3D._of_edge_point).
pub fn edge_point(shape: Shape3D, edge: Edge, offset: Offset) -> [f64; 3] {
    let origin = corner_point(shape, [edge.lhs, edge.rhs, third_face(edge.rhs, edge.lhs)]);
    let direction = third_face(edge.lhs, edge.rhs).normal();
    let along = offset.evaluate(edge_length(shape, edge));
    std::array::from_fn(|i| origin[i] + f64::from(direction[i]) * along)
}

/// A point on a face, measured from the face's centre (coordinates.py).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct SurfacePoint {
    pub face: Face,
    pub u: f64,
    pub v: f64,
}

impl SurfacePoint {
    pub fn from_point(shape: Shape3D, face: Face, point: [f64; 3]) -> SurfacePoint {
        let (w, h, l) = (shape.width, shape.height, shape.length);
        let [x, y, z] = point;
        let (u, v) = match face {
            Face::Top => (x - w / 2.0, y - h / 2.0),
            Face::Down => (w / 2.0 - x, y - h / 2.0),
            Face::Left => (h / 2.0 - y, z - l / 2.0),
            Face::Right => (y - h / 2.0, z - l / 2.0),
            Face::Front => (w / 2.0 - x, z - l / 2.0),
            Face::Back => (x - w / 2.0, z - l / 2.0),
        };
        SurfacePoint { face, u, v }
    }

    pub fn to_point(self, shape: Shape3D) -> [f64; 3] {
        let (w, h, l) = (shape.width, shape.height, shape.length);
        let (u, v) = (self.u, self.v);
        match self.face {
            Face::Top => [u + w / 2.0, v + h / 2.0, l],
            Face::Down => [-u + w / 2.0, v + h / 2.0, 0.0],
            Face::Left => [0.0, -u + h / 2.0, v + l / 2.0],
            Face::Right => [w, u + h / 2.0, v + l / 2.0],
            Face::Front => [-u + w / 2.0, h, v + l / 2.0],
            Face::Back => [u + w / 2.0, 0.0, v + l / 2.0],
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::piece::Shape3D;
    use Face::*;

    #[test]
    fn cross_is_the_python_table() {
        assert_eq!(Face::cross(Top, Front), Ok(Left));
        assert_eq!(Face::cross(Front, Top), Ok(Right));
        assert_eq!(Face::cross(Right, Top), Ok(Back));
        assert_eq!(Face::cross(Top, Right), Ok(Front));
        assert_eq!(Face::cross(Front, Right), Ok(Down));
        assert_eq!(Face::cross(Right, Front), Ok(Top));
        assert_eq!(Face::cross(Down, Front), Ok(Right));
        assert!(Face::cross(Top, Down).is_err());
    }

    #[test]
    fn an_edge_point_lies_on_its_edge() {
        let shape = Shape3D {
            width: 89.0,
            height: 38.0,
            length: 700.0,
        };
        // The worked example of the DSL spec: leg -[FL<100 ...]: front/left edge
        let edge = Edge {
            lhs: Front,
            rhs: Left,
        };
        let edge = if Face::cross(edge.lhs, edge.rhs).unwrap().is_positive() {
            edge
        } else {
            Edge {
                lhs: edge.rhs,
                rhs: edge.lhs,
            }
        };
        assert_eq!(edge_length(shape, edge), 700.0);
        assert_eq!(
            edge_point(shape, edge, Offset::FromMin(100.0)),
            [0.0, 38.0, 100.0]
        );
        assert_eq!(
            edge_point(shape, edge, Offset::FromMax(100.0)),
            [0.0, 38.0, 600.0]
        );
    }

    #[test]
    fn surface_points_round_trip() {
        let shape = Shape3D {
            width: 89.0,
            height: 38.0,
            length: 600.0,
        };
        for face in Face::ALL {
            let mut point = [44.5, 19.0, 300.0];
            point[face.axis()] = if face.is_positive() {
                [89.0, 38.0, 600.0][face.axis()]
            } else {
                0.0
            };
            let surface = SurfacePoint::from_point(shape, face, point);
            assert_eq!(surface.to_point(shape), point, "{face:?}");
        }
    }

    #[test]
    fn offsets_cannot_be_negative() {
        assert_eq!(
            Offset::from_min(-5.0).unwrap_err().to_string(),
            "value: Input should be greater than or equal to 0 (got -5.0)"
        );
        assert_eq!(Offset::FromMin(5.0).repr(), "FromMin(value=5.0)");
    }
}
