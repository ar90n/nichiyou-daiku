//! A piece's solid: its box with the cavities its holes leave, as faces
//! bounded by loops of edges (B-rep), in world mm. Faces face out of the
//! solid; outer loops run counter-clockwise seen from outside.

use nichiyou_daiku_core::placement::{Pose, rotate};

use crate::bore::{Bore, Span, others};

pub type P3 = [f64; 3];

/// Chord error a circle's segments keep within, for the STL
const CHORD_MM: f64 = 0.05;
const MIN_SEGMENTS: usize = 16;
/// Ends of a cavity this close to a face are on it
const ON_FACE: f64 = 1e-9;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Surface {
    Plane {
        origin: P3,
        normal: P3,
        x: P3,
    },
    /// `radius` at `origin`, widening by `slope` per mm along `axis`: a
    /// cylinder when the slope is 0
    Cone {
        origin: P3,
        axis: P3,
        x: P3,
        radius: f64,
        slope: f64,
    },
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Curve {
    Line {
        origin: P3,
        direction: P3,
    },
    /// Counter-clockwise about `axis` from `centre + radius * x`, drawn in
    /// `segments` straight pieces for the STL
    Circle {
        centre: P3,
        axis: P3,
        x: P3,
        radius: f64,
        segments: usize,
    },
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Edge {
    pub curve: Curve,
    pub start: usize,
    pub end: usize,
}

/// An edge in a loop, and whether the loop runs along the edge's direction
pub type Use = (usize, bool);

#[derive(Clone, Debug, PartialEq)]
pub struct Face {
    pub surface: Surface,
    /// Whether the surface's own normal points out of the solid
    pub same_sense: bool,
    /// The outer loop first, then the holes in it
    pub loops: Vec<Vec<Use>>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Solid {
    pub name: String,
    pub vertices: Vec<P3>,
    pub edges: Vec<Edge>,
    pub faces: Vec<Face>,
    pub volume: f64,
    /// Cavities open at both ends: each a handle through the solid
    pub through: usize,
}

fn unit(axis: usize, sign: f64) -> P3 {
    let mut v = [0.0; 3];
    v[axis] = sign;
    v
}

fn dot(a: P3, b: P3) -> f64 {
    a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
}

/// Straight pieces enough to keep a circle within CHORD_MM.
pub fn segments(radius: f64) -> usize {
    if radius <= CHORD_MM {
        return MIN_SEGMENTS;
    }
    let n = (std::f64::consts::PI / (1.0 - CHORD_MM / radius).acos()).ceil() as usize;
    n.max(MIN_SEGMENTS)
}

fn centre_of(bore: &Bore, t: f64) -> P3 {
    let mut c = [0.0; 3];
    let [i, j] = others(bore.axis);
    c[i] = bore.at[0];
    c[j] = bore.at[1];
    c[bore.axis] = t;
    c
}

/// Builds a solid in the piece's own axes; `finish` moves it to the world.
struct Builder {
    vertices: Vec<P3>,
    edges: Vec<Edge>,
    faces: Vec<Face>,
}

impl Builder {
    fn vertex(&mut self, p: P3) -> usize {
        self.vertices.push(p);
        self.vertices.len() - 1
    }

    fn edge(&mut self, curve: Curve, start: usize, end: usize) -> usize {
        self.edges.push(Edge { curve, start, end });
        self.edges.len() - 1
    }

    /// A circle about the bore's +axis at `t`, starting on its x direction.
    fn circle(&mut self, bore: &Bore, t: f64, radius: f64, segments: usize) -> usize {
        let centre = centre_of(bore, t);
        let x = unit(others(bore.axis)[0], 1.0);
        let start = [0, 1, 2].map(|i| centre[i] + radius * x[i]);
        let v = self.vertex(start);
        self.edge(
            Curve::Circle {
                centre,
                axis: unit(bore.axis, 1.0),
                x,
                radius,
                segments,
            },
            v,
            v,
        )
    }

    /// How a plane face with outward normal `n` uses a circle: outer loops
    /// counter-clockwise about `n`, holes clockwise.
    fn circle_use(&self, circle: usize, n: P3, outer: bool) -> Use {
        let Curve::Circle { axis, .. } = self.edges[circle].curve else {
            unreachable!("a circle");
        };
        let ccw = dot(axis, n) > 0.0;
        (circle, if outer { ccw } else { !ccw })
    }

    fn plane(&mut self, origin: P3, normal: P3, x: P3, loops: Vec<Vec<Use>>) {
        self.faces.push(Face {
            surface: Surface::Plane { origin, normal, x },
            same_sense: true,
            loops,
        });
    }
}

/// The mouth circles each box face holds: (axis, high end) and the circle.
type Mouths = Vec<((usize, bool), usize)>;

/// Adds one cavity's faces; true when it goes through the piece.
fn cavity(b: &mut Builder, bore: &Bore, spans: &[Span], length: f64, mouths: &mut Mouths) -> bool {
    let n = segments(spans.iter().map(|s| s.r0.max(s.r1)).fold(0.0, f64::max));
    let e = unit(bore.axis, 1.0);
    let back = unit(bore.axis, -1.0);
    let x = unit(others(bore.axis)[0], 1.0);
    let first = spans[0];
    let last = *spans.last().expect("a cavity has a stretch");
    let opens_low = first.t0 <= ON_FACE;
    let opens_high = last.t1 >= length - ON_FACE;
    let mut start = b.circle(bore, first.t0, first.r0, n);
    if opens_low {
        mouths.push(((bore.axis, false), start));
    } else {
        // A bottom facing into the cavity, toward +axis
        let disk = b.circle_use(start, e, true);
        b.plane(centre_of(bore, first.t0), e, x, vec![vec![disk]]);
    }
    for (k, span) in spans.iter().enumerate() {
        let end = b.circle(bore, span.t1, span.r1, n);
        // The seam joins the two circles' first points: along a cone's slant
        let (vs, ve) = (b.edges[start].start, b.edges[end].start);
        let (ps, pe) = (b.vertices[vs], b.vertices[ve]);
        let d = [0, 1, 2].map(|i| pe[i] - ps[i]);
        let slant = dot(d, d).sqrt();
        let seam = b.edge(
            Curve::Line {
                origin: ps,
                direction: d.map(|v| v / slant),
            },
            vs,
            ve,
        );
        b.faces.push(Face {
            surface: Surface::Cone {
                origin: centre_of(bore, span.t0),
                axis: e,
                x,
                radius: span.r0,
                slope: (span.r1 - span.r0) / (span.t1 - span.t0),
            },
            // The wall faces the axis; the surface's normal points away
            same_sense: false,
            loops: vec![vec![
                (start, false),
                (seam, true),
                (end, true),
                (seam, false),
            ]],
        });
        if let Some(next) = spans.get(k + 1) {
            if (span.r1 - next.r0).abs() < 1e-9 {
                start = end;
            } else {
                // A ring where the radius steps, facing the wider side
                let following = b.circle(bore, next.t0, next.r0, n);
                let (normal, wide, narrow) = if span.r1 > next.r0 {
                    (back, end, following)
                } else {
                    (e, following, end)
                };
                let outer = b.circle_use(wide, normal, true);
                let inner = b.circle_use(narrow, normal, false);
                b.plane(
                    centre_of(bore, span.t1),
                    normal,
                    x,
                    vec![vec![outer], vec![inner]],
                );
                start = following;
            }
        } else if opens_high {
            mouths.push(((bore.axis, true), end));
        } else {
            let disk = b.circle_use(end, back, true);
            b.plane(centre_of(bore, span.t1), back, x, vec![vec![disk]]);
        }
    }
    opens_low && opens_high
}

/// The box's corner at (i, j, k) ∈ {0, 1}³.
fn corner(size: [f64; 3], bits: [usize; 3]) -> P3 {
    [
        bits[0] as f64 * size[0],
        bits[1] as f64 * size[1],
        bits[2] as f64 * size[2],
    ]
}

pub fn piece_solid(name: &str, size: [f64; 3], bores: &[Bore], pose: &Pose) -> Solid {
    let mut b = Builder {
        vertices: Vec::new(),
        edges: Vec::new(),
        faces: Vec::new(),
    };
    let corners: Vec<usize> = (0..8)
        .map(|c| b.vertex(corner(size, [c & 1, (c >> 1) & 1, (c >> 2) & 1])))
        .collect();
    // The 12 edges, each from the lower corner to the higher
    let mut lines: Vec<((usize, usize), usize)> = Vec::new();
    for c in 0..8 {
        for axis in 0..3 {
            if c & (1 << axis) == 0 {
                let d = c | (1 << axis);
                let edge = b.edge(
                    Curve::Line {
                        origin: b.vertices[corners[c]],
                        direction: unit(axis, 1.0),
                    },
                    corners[c],
                    corners[d],
                );
                lines.push(((c, d), edge));
            }
        }
    }
    let mut mouths: Mouths = Vec::new();
    let mut through = 0;
    let mut volume = size[0] * size[1] * size[2];
    for bore in bores {
        for spans in &bore.cavities {
            volume -= spans.iter().map(Span::volume).sum::<f64>();
            if cavity(&mut b, bore, spans, size[bore.axis], &mut mouths) {
                through += 1;
            }
        }
    }
    let index = |bits: [usize; 3]| bits[0] | (bits[1] << 1) | (bits[2] << 2);
    for axis in 0..3 {
        for high in [false, true] {
            // u × v = outward normal: counter-clockwise seen from outside
            let (a, c) = ((axis + 1) % 3, (axis + 2) % 3);
            let (u, v) = if high { (a, c) } else { (c, a) };
            let normal = unit(axis, if high { 1.0 } else { -1.0 });
            let at = |du: usize, dv: usize| {
                let mut bits = [0; 3];
                bits[axis] = usize::from(high);
                bits[u] = du;
                bits[v] = dv;
                index(bits)
            };
            let ring = [at(0, 0), at(1, 0), at(1, 1), at(0, 1)];
            let outer: Vec<Use> = (0..4)
                .map(|k| {
                    let (p, q) = (ring[k], ring[(k + 1) % 4]);
                    let key = (p.min(q), p.max(q));
                    let edge = lines
                        .iter()
                        .find(|(pair, _)| *pair == key)
                        .expect("a box edge")
                        .1;
                    (edge, p < q)
                })
                .collect();
            let mut loops = vec![outer];
            for &(_, circle) in mouths.iter().filter(|(side, _)| *side == (axis, high)) {
                loops.push(vec![b.circle_use(circle, normal, false)]);
            }
            let origin = b.vertices[corners[ring[0]]];
            b.plane(origin, normal, unit(u, 1.0), loops);
        }
    }
    finish(name, b, pose, volume, through)
}

/// The solid moved to where the pose puts the piece.
fn finish(name: &str, b: Builder, pose: &Pose, volume: f64, through: usize) -> Solid {
    let point = |p: P3| pose.apply(p);
    let vector = |v: P3| rotate(&pose.rotation, v);
    let edges = b
        .edges
        .into_iter()
        .map(|e| Edge {
            curve: match e.curve {
                Curve::Line { origin, direction } => Curve::Line {
                    origin: point(origin),
                    direction: vector(direction),
                },
                Curve::Circle {
                    centre,
                    axis,
                    x,
                    radius,
                    segments,
                } => Curve::Circle {
                    centre: point(centre),
                    axis: vector(axis),
                    x: vector(x),
                    radius,
                    segments,
                },
            },
            ..e
        })
        .collect();
    let faces = b
        .faces
        .into_iter()
        .map(|f| Face {
            surface: match f.surface {
                Surface::Plane { origin, normal, x } => Surface::Plane {
                    origin: point(origin),
                    normal: vector(normal),
                    x: vector(x),
                },
                Surface::Cone {
                    origin,
                    axis,
                    x,
                    radius,
                    slope,
                } => Surface::Cone {
                    origin: point(origin),
                    axis: vector(axis),
                    x: vector(x),
                    radius,
                    slope,
                },
            },
            ..f
        })
        .collect();
    Solid {
        name: name.to_string(),
        vertices: b.vertices.into_iter().map(point).collect(),
        edges,
        faces,
        volume,
        through,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::bore::Span;
    use nichiyou_daiku_core::placement::Pose;

    fn still() -> Pose {
        Pose {
            rotation: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            translation: [0.0; 3],
        }
    }

    /// V − E + F − (L − F) and 2(S − G) for one shell
    fn euler(solid: &Solid) -> (i64, i64) {
        let loops: usize = solid.faces.iter().map(|f| f.loops.len()).sum();
        let (v, e, f) = (
            solid.vertices.len() as i64,
            solid.edges.len() as i64,
            solid.faces.len() as i64,
        );
        (
            v - e + f - (loops as i64 - f),
            2 * (1 - solid.through as i64),
        )
    }

    /// Every edge is used twice, once each way: the faces close up.
    fn closed(solid: &Solid) -> bool {
        let mut uses = vec![(0, 0); solid.edges.len()];
        for face in &solid.faces {
            for &(edge, along) in face.loops.iter().flatten() {
                if along {
                    uses[edge].0 += 1
                } else {
                    uses[edge].1 += 1
                }
            }
        }
        uses.iter().all(|&u| u == (1, 1))
    }

    fn bore(axis: usize, at: [f64; 2], cavities: Vec<Vec<Span>>) -> Bore {
        Bore { axis, at, cavities }
    }

    #[test]
    fn a_plain_box_is_six_faces() {
        let solid = piece_solid("a", [89.0, 38.0, 400.0], &[], &still());
        assert_eq!(
            (solid.vertices.len(), solid.edges.len(), solid.faces.len()),
            (8, 12, 6)
        );
        assert_eq!(euler(&solid).0, euler(&solid).1);
        assert!(closed(&solid));
        assert!((solid.volume - 89.0 * 38.0 * 400.0).abs() < 1e-6);
    }

    #[test]
    fn a_blind_hole_closes_with_a_bottom() {
        let b = bore(
            1,
            [44.5, 100.0],
            vec![vec![Span {
                t0: 0.0,
                t1: 15.0,
                r0: 4.0,
                r1: 4.0,
            }]],
        );
        let solid = piece_solid("a", [89.0, 38.0, 400.0], &[b], &still());
        assert_eq!(solid.through, 0);
        assert_eq!(euler(&solid).0, euler(&solid).1);
        assert!(closed(&solid));
        let hole = std::f64::consts::PI * 16.0 * 15.0;
        assert!((solid.volume - (89.0 * 38.0 * 400.0 - hole)).abs() < 1e-6);
    }

    #[test]
    fn a_counterbored_through_hole_is_one_handle() {
        let b = bore(
            0,
            [19.0, 200.0],
            vec![vec![
                Span {
                    t0: 0.0,
                    t1: 51.0,
                    r0: 5.0,
                    r1: 5.0,
                },
                Span {
                    t0: 51.0,
                    t1: 89.0,
                    r0: 1.25,
                    r1: 1.25,
                },
            ]],
        );
        let solid = piece_solid("a", [89.0, 38.0, 400.0], &[b], &still());
        assert_eq!(solid.through, 1);
        assert_eq!(euler(&solid).0, euler(&solid).1);
        assert!(closed(&solid));
    }

    #[test]
    fn a_countersink_joins_its_pilot_without_a_step() {
        let b = bore(
            2,
            [44.5, 19.0],
            vec![vec![
                Span {
                    t0: 0.0,
                    t1: 397.5,
                    r0: 1.25,
                    r1: 1.25,
                },
                Span {
                    t0: 397.5,
                    t1: 400.0,
                    r0: 1.25,
                    r1: 3.75,
                },
            ]],
        );
        let solid = piece_solid("a", [89.0, 38.0, 400.0], &[b], &still());
        // Two walls (cylinder, cone), no ring between them
        let walls = solid
            .faces
            .iter()
            .filter(|f| matches!(f.surface, Surface::Cone { .. }))
            .count();
        assert_eq!((walls, solid.faces.len()), (2, 8));
        assert_eq!(euler(&solid).0, euler(&solid).1);
        assert!(closed(&solid));
    }

    #[test]
    fn a_turned_piece_lands_where_its_pose_puts_it() {
        // A quarter turn about z, then moved
        let pose = Pose {
            rotation: [[0, -1, 0], [1, 0, 0], [0, 0, 1]],
            translation: [100.0, 0.0, 0.0],
        };
        let solid = piece_solid("a", [89.0, 38.0, 400.0], &[], &pose);
        let (low, high) = solid
            .vertices
            .iter()
            .fold((f64::MAX, f64::MIN), |(l, h), v| (l.min(v[0]), h.max(v[0])));
        assert_eq!((low, high), (62.0, 100.0));
    }
}
