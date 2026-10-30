//! Fasteners laid out in each contact area, the holes they need, and holes
//! of two connections that run into each other inside a piece.

use std::collections::HashSet;

use crate::connection::{Connection, ConnectionType, dimension_for_face};
use crate::geometry::SurfacePoint;
use crate::model::Model;
use crate::piece::Shape3D;
use crate::placement::{Placement, axis_index, relative_pose, rotate, solve_placement};
use crate::pyfmt::format_fixed;
use crate::resolve::resolve_model;

/// Holes closer than this do not meet.
pub const CONTACT_TOLERANCE_MM: f64 = 1e-6;

/// A hole: None depth goes through the piece.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Hole {
    pub diameter: f64,
    pub depth: Option<f64>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FastenerKind {
    Dowel,
    Screw,
}

impl FastenerKind {
    pub fn as_str(self) -> &'static str {
        match self {
            FastenerKind::Dowel => "dowel",
            FastenerKind::Screw => "screw",
        }
    }
}

/// A dowel or screw joining two pieces, with the hole it needs in each.
#[derive(Clone, Debug, PartialEq)]
pub struct Fastener {
    pub base_id: String,
    pub target_id: String,
    pub kind: FastenerKind,
    /// Of the dowel or screw itself; a screw's holes are narrower pilot holes
    pub diameter: f64,
    /// Where it enters the base, on the base's contact face
    pub base_position: SurfacePoint,
    /// Where it enters the target, on the target's contact face
    pub target_position: SurfacePoint,
    pub base_hole: Hole,
    pub target_hole: Hole,
    /// For a screw through the target's narrow face, the wider hole its head
    /// sinks into, from the far face down to the target's thickness
    pub counterbore: Option<(SurfacePoint, Hole)>,
}

/// A connection whose fasteners do not fit, or whose holes run into the
/// holes of an earlier connection (then with the piece, the other
/// connection and the two holes, this one's first).
#[derive(Clone, Debug, PartialEq)]
pub struct LayoutIssue {
    pub base_id: String,
    pub target_id: String,
    pub kind: FastenerKind,
    pub message: String,
    pub piece_id: Option<String>,
    pub other: Option<(String, String)>,
    pub holes: Option<((SurfacePoint, Hole), (SurfacePoint, Hole))>,
}

/// A pilot hole: about 65% of the screw, to the nearest 0.5mm, at least 0.5mm.
pub fn pilot_diameter(screw_diameter: f64) -> f64 {
    ((screw_diameter * 0.65 * 2.0).round_ties_even() / 2.0).max(0.5)
}

/// The counterbore a screw head sinks into: 10mm, or 12mm above 4.5mm.
pub fn counterbore_diameter(screw_diameter: f64) -> f64 {
    if screw_diameter <= 4.5 { 10.0 } else { 12.0 }
}

fn positions_along(start: f64, length: f64, diameter: f64) -> Vec<f64> {
    if length / 2.0 >= 2.0 * diameter {
        vec![start + length / 4.0, start + 3.0 * length / 4.0]
    } else {
        vec![start + length / 2.0]
    }
}

fn size(shape: Shape3D) -> [f64; 3] {
    [shape.width, shape.height, shape.length]
}

/// The fasteners of one connection, or the reason they do not fit: across the
/// middle of the contact rectangle's short side, at 1/4 and 3/4 of its long
/// side (one in the middle when there is no room for two).
pub fn layout_fasteners(connection: &Connection) -> (Vec<Fastener>, Option<LayoutIssue>) {
    let (base, target) = (&connection.base, &connection.target);
    let target_shape = target.piece.shape();
    let (kind, diameter, base_hole, target_hole, sunk) = match connection.kind {
        ConnectionType::Vanilla => return (Vec::new(), None),
        ConnectionType::Dowel { radius, depth } => {
            let hole = Hole {
                diameter: radius * 2.0,
                depth: Some(depth / 2.0),
            };
            (FastenerKind::Dowel, radius * 2.0, hole, hole, 0.0)
        }
        ConnectionType::Screw {
            diameter, length, ..
        } => {
            // Through a narrow face the head sinks into a counterbore, so the
            // screw crosses the target's thickness either way
            let thickness = target_shape.height;
            let sunk = dimension_for_face(target_shape, target.anchor.contact) - thickness;
            let pilot = pilot_diameter(diameter);
            (
                FastenerKind::Screw,
                diameter,
                Hole {
                    diameter: pilot,
                    depth: Some(length - thickness),
                },
                Hole {
                    diameter: pilot,
                    depth: None,
                },
                sunk,
            )
        }
    };
    let issue = |message: String| LayoutIssue {
        base_id: base.piece.id.clone(),
        target_id: target.piece.id.clone(),
        kind,
        message,
        piece_id: None,
        other: None,
        holes: None,
    };
    let base_shape = base.piece.shape();
    let base_high = size(base_shape);
    let relative = relative_pose(base, target);
    let (target_low, target_high) = relative.bounds(target_shape);
    let low: [f64; 3] = std::array::from_fn(|i| target_low[i].max(0.0));
    let high: [f64; 3] = std::array::from_fn(|i| base_high[i].min(target_high[i]));
    let normal = base.anchor.contact.normal();
    let plane_axis = axis_index(normal.map(f64::from));
    let plane = if normal[plane_axis] > 0 {
        base_high[plane_axis]
    } else {
        0.0
    };
    let (first, second) = match plane_axis {
        0 => (1, 2),
        1 => (0, 2),
        _ => (0, 1),
    };
    let sizes = [high[first] - low[first], high[second] - low[second]];
    if sizes[0].min(sizes[1]) <= CONTACT_TOLERANCE_MM {
        return (
            Vec::new(),
            Some(issue("pieces do not share a contact area".into())),
        );
    }
    let (long_axis, short_axis, long_size, short_size) = if sizes[0] >= sizes[1] {
        (first, second, sizes[0], sizes[1])
    } else {
        (second, first, sizes[1], sizes[0])
    };
    if short_size < 2.0 * diameter {
        return (
            Vec::new(),
            Some(issue(format!(
                "contact area {} x {}mm is too narrow for a {}mm {} (needs {}mm)",
                format_fixed(short_size, 1),
                format_fixed(long_size, 1),
                format_fixed(diameter, 1),
                kind.as_str(),
                format_fixed(2.0 * diameter, 1)
            ))),
        );
    }
    let target_size = size(target_shape);
    let to_target = transpose(&relative.rotation);
    let mut fasteners = Vec::new();
    for along in positions_along(low[long_axis], long_size, diameter) {
        let mut point = [0.0; 3];
        point[plane_axis] = plane;
        point[long_axis] = along;
        point[short_axis] = low[short_axis] + short_size / 2.0;
        let shifted: [f64; 3] = std::array::from_fn(|i| point[i] - relative.translation[i]);
        let target_point = rotate(&to_target, shifted);
        let counterbore = (sunk > 0.0).then(|| {
            let far = target.anchor.contact.opposite();
            let far_axis = far.axis();
            let mut far_point = target_point;
            far_point[far_axis] = if far.is_positive() {
                target_size[far_axis]
            } else {
                0.0
            };
            (
                SurfacePoint::from_point(target_shape, far, far_point),
                Hole {
                    diameter: counterbore_diameter(diameter),
                    depth: Some(sunk),
                },
            )
        });
        fasteners.push(Fastener {
            base_id: base.piece.id.clone(),
            target_id: target.piece.id.clone(),
            kind,
            diameter,
            base_position: SurfacePoint::from_point(base_shape, base.anchor.contact, point),
            target_position: SurfacePoint::from_point(
                target_shape,
                target.anchor.contact,
                target_point,
            ),
            base_hole,
            target_hole,
            counterbore,
        });
    }
    (fasteners, None)
}

fn transpose(a: &crate::placement::Mat3) -> crate::placement::Mat3 {
    std::array::from_fn(|r| std::array::from_fn(|c| a[c][r]))
}

/// A drilled hole in piece coordinates: a cylinder along one axis.
#[derive(Clone, Copy, Debug)]
struct Bore {
    axis: usize,
    low: f64,
    high: f64,
    center: [f64; 3],
    radius: f64,
}

fn bore(shape: Shape3D, position: SurfacePoint, hole: Hole) -> Bore {
    let center = position.to_point(shape);
    let normal = position.face.normal();
    let axis = position.face.axis();
    let depth = hole.depth.unwrap_or(size(shape)[axis]);
    let end = center[axis] - f64::from(normal[axis]) * depth;
    let (low, high) = if center[axis] <= end {
        (center[axis], end)
    } else {
        (end, center[axis])
    };
    Bore {
        axis,
        low,
        high,
        center,
        radius: hole.diameter / 2.0,
    }
}

fn gap(value: f64, low: f64, high: f64) -> f64 {
    (low - value).max(0.0).max(value - high)
}

fn bores_meet(a: &Bore, b: &Bore) -> bool {
    if a.axis == b.axis {
        let across: Vec<f64> = (0..3)
            .filter(|&i| i != a.axis)
            .map(|i| a.center[i] - b.center[i])
            .collect();
        return a.high.min(b.high) - a.low.max(b.low) > CONTACT_TOLERANCE_MM
            && across[0].hypot(across[1]) < a.radius + b.radius - CONTACT_TOLERANCE_MM;
    }
    // Perpendicular bores come closest where each is nearest the other's axis
    let gap_a = gap(b.center[a.axis], a.low, a.high);
    let gap_b = gap(a.center[b.axis], b.low, b.high);
    if gap_a >= b.radius - CONTACT_TOLERANCE_MM || gap_b >= a.radius - CONTACT_TOLERANCE_MM {
        return false;
    }
    let third = 3 - a.axis - b.axis;
    let reach =
        (a.radius.powi(2) - gap_b.powi(2)).sqrt() + (b.radius.powi(2) - gap_a.powi(2)).sqrt();
    (a.center[third] - b.center[third]).abs() < reach - CONTACT_TOLERANCE_MM
}

type Drilled<'a> = (&'a Fastener, SurfacePoint, Hole, Bore);

/// Holes of two connections that run into each other inside a piece, judged
/// on the space each fastener takes (a screw is wider than its pilot hole, a
/// counterbore takes its own width); reported once on the later connection.
pub fn find_hole_collisions(fasteners: &[Fastener], model: &Model) -> Vec<LayoutIssue> {
    let shape = |id: &str| {
        model
            .piece(id)
            .expect("a fastener joins the model's pieces")
            .shape()
    };
    let mut bores: Vec<(String, Vec<Drilled>)> = Vec::new();
    for fastener in fasteners {
        let mut drilled = vec![
            (
                &fastener.base_id,
                fastener.base_position,
                Hole {
                    diameter: fastener.diameter,
                    depth: fastener.base_hole.depth,
                },
            ),
            (
                &fastener.target_id,
                fastener.target_position,
                Hole {
                    diameter: fastener.diameter,
                    depth: fastener.target_hole.depth,
                },
            ),
        ];
        if let Some((at, hole)) = fastener.counterbore {
            drilled.push((&fastener.target_id, at, hole));
        }
        for (piece_id, position, space) in drilled {
            let entry = (
                fastener,
                position,
                space,
                bore(shape(piece_id), position, space),
            );
            match bores.iter_mut().find(|(id, _)| id == piece_id) {
                Some((_, list)) => list.push(entry),
                None => bores.push((piece_id.clone(), vec![entry])),
            }
        }
    }
    let mut seen = HashSet::new();
    let mut issues = Vec::new();
    for (piece_id, drilled) in &bores {
        for (i, (earlier, earlier_at, earlier_hole, a)) in drilled.iter().enumerate() {
            for (later, later_at, later_hole, b) in &drilled[i + 1..] {
                let same =
                    (&earlier.base_id, &earlier.target_id) == (&later.base_id, &later.target_id);
                if same || !bores_meet(a, b) {
                    continue;
                }
                let key = (
                    later.base_id.clone(),
                    later.target_id.clone(),
                    earlier.base_id.clone(),
                    earlier.target_id.clone(),
                );
                if !seen.insert(key) {
                    continue;
                }
                issues.push(LayoutIssue {
                    base_id: later.base_id.clone(),
                    target_id: later.target_id.clone(),
                    kind: later.kind,
                    message: format!(
                        "{} hole in '{piece_id}' runs into a {} hole of connection {} -> {}",
                        later.kind.as_str(),
                        earlier.kind.as_str(),
                        earlier.base_id,
                        earlier.target_id
                    ),
                    piece_id: Some(piece_id.clone()),
                    other: Some((earlier.base_id.clone(), earlier.target_id.clone())),
                    holes: Some(((*later_at, *later_hole), (*earlier_at, *earlier_hole))),
                });
            }
        }
    }
    issues
}

/// The placed model with its fasteners and holes.
#[derive(Clone, Debug)]
pub struct Assembly {
    pub model: Model,
    pub placement: Placement,
    pub fasteners: Vec<Fastener>,
    pub fastener_issues: Vec<LayoutIssue>,
    /// By piece, in the order the pieces first get a hole
    pub pilot_holes: Vec<(String, Vec<(SurfacePoint, Hole)>)>,
}

impl Assembly {
    /// Solve the unknowns, place the pieces, lay out the fasteners (not for
    /// connections that contradict the placement: their holes would never
    /// meet) and drill the holes.
    pub fn of(model: Model) -> Result<Assembly, String> {
        let model = resolve_model(model).map_err(|error| error.message)?;
        let placement = solve_placement(&model);
        let rejected: HashSet<(&str, &str)> = placement
            .conflicts
            .iter()
            .map(|c| (c.base_id.as_str(), c.target_id.as_str()))
            .collect();
        let mut fasteners = Vec::new();
        let mut issues = Vec::new();
        for connection in &model.connections {
            if rejected.contains(&(connection.base_id(), connection.target_id())) {
                continue;
            }
            let (laid_out, issue) = layout_fasteners(connection);
            fasteners.extend(laid_out);
            issues.extend(issue);
        }
        issues.extend(find_hole_collisions(&fasteners, &model));
        let mut pilot_holes: Vec<(String, Vec<(SurfacePoint, Hole)>)> = Vec::new();
        let mut add = |piece: &str, hole: (SurfacePoint, Hole)| match pilot_holes
            .iter_mut()
            .find(|(id, _)| id == piece)
        {
            Some((_, list)) => list.push(hole),
            None => pilot_holes.push((piece.to_string(), vec![hole])),
        };
        for fastener in &fasteners {
            add(
                &fastener.base_id,
                (fastener.base_position, fastener.base_hole),
            );
            add(
                &fastener.target_id,
                (fastener.target_position, fastener.target_hole),
            );
            if let Some(counterbore) = fastener.counterbore {
                add(&fastener.target_id, counterbore);
            }
        }
        Ok(Assembly {
            model,
            placement,
            fasteners,
            fastener_issues: issues,
            pilot_holes,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::dsl::parse;

    fn layout(source: &str) -> (Vec<Fastener>, Option<LayoutIssue>) {
        layout_fasteners(&parse(source).unwrap().connections[0])
    }

    fn issues(source: &str) -> Vec<(String, String, String)> {
        Assembly::of(parse(source).unwrap())
            .unwrap()
            .fastener_issues
            .into_iter()
            .map(|i| (i.base_id, i.target_id, i.message))
            .collect()
    }

    const CORNER: &str = "(post:2x4 =600)\n(rail_a:2x4 =300)\n(rail_b:2x4 =300)\n\
        rail_a -[DF>0 BL<300 S(Slim:3.8x65)]- post\nrail_b -[DF<0 RF<{h} S(Slim:3.8x65)]- post\n";

    #[test]
    fn pilot_holes_are_two_thirds_of_the_screw() {
        assert_eq!(
            [3.3, 3.8, 4.2, 5.2].map(pilot_diameter),
            [2.0, 2.5, 2.5, 3.5]
        );
        assert_eq!(
            [3.8, 4.5, 5.2].map(counterbore_diameter),
            [10.0, 10.0, 12.0]
        );
    }

    #[test]
    fn screws_pass_through_the_target_into_the_base() {
        let (fasteners, issue) = layout(
            "(base:2x4 =500)\n(target:1x4 =300)\nbase -[FL<100 BL<0 S(Slim:3.3x25)]- target\n",
        );
        assert!(issue.is_none());
        assert_eq!(fasteners.len(), 2);
        for f in &fasteners {
            assert_eq!(
                (f.target_hole, f.base_hole),
                (
                    Hole {
                        diameter: 2.0,
                        depth: None
                    },
                    Hole {
                        diameter: 2.0,
                        depth: Some(6.0)
                    }
                )
            );
            assert!(f.counterbore.is_none());
        }
    }

    #[test]
    fn a_screw_through_a_narrow_face_is_counterbored() {
        let (fasteners, _) =
            layout("(post:2x4 =600)\n(rail:2x4 =300)\nrail -[DF<0 RF<300 S(Slim:3.8x65)]- post\n");
        assert_eq!(fasteners.len(), 2);
        for f in &fasteners {
            assert_eq!(
                f.base_hole,
                Hole {
                    diameter: 2.5,
                    depth: Some(27.0)
                }
            );
            let (at, hole) = f.counterbore.unwrap();
            assert_eq!(
                (at.face, hole),
                (
                    crate::geometry::Face::Left,
                    Hole {
                        diameter: 10.0,
                        depth: Some(51.0)
                    }
                )
            );
        }
    }

    #[test]
    fn screws_crossing_in_a_corner_post_are_reported() {
        let message = "screw hole in 'post' runs into a screw hole of connection rail_a -> post";
        let expected = vec![(
            "rail_b".to_string(),
            "post".to_string(),
            message.to_string(),
        )];
        assert_eq!(issues(&CORNER.replace("{h}", "300")), expected);
        assert!(issues(&CORNER.replace("{h}", "400")).is_empty());
        // 5mm apart the screws pass, but rail_b's 10mm counterbore reaches rail_a's screw
        assert_eq!(issues(&CORNER.replace("{h}", "305")), expected);
    }
}
