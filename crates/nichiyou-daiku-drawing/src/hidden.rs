//! Hidden lines among boxes lined up with the world's axes, as every placed
//! piece is (quarter turns only). A line is hidden where its own box turns
//! the faces it lies on away, or where the ray from it toward the viewer
//! passes through another box.

use nichiyou_daiku_core::parts::LocalHole;
use nichiyou_daiku_core::piece::Shape3D;
use nichiyou_daiku_core::placement::{Pose, rotate};

use crate::solid::{Projection, ring};
use crate::svg::Point;

/// Other boxes hide only this far inside, so that a line on the face of a
/// box it touches is not hidden by it (views.py: _blocks).
const TOLERANCE_MM: f64 = 1e-6;
const FAR_MM: f64 = 1e7;
/// Fractions of a line closer than this are the same point
const SAME: f64 = 1e-9;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Segment3 {
    pub from: [f64; 3],
    pub to: [f64; 3],
    /// Whether its own box shows it
    pub shown: bool,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Body {
    pub low: [f64; 3],
    pub high: [f64; 3],
    pub segments: Vec<Segment3>,
}

#[derive(Debug, Default)]
pub struct Sorted {
    pub visible: Vec<(Point, Point)>,
    pub hidden: Vec<(Point, Point)>,
}

fn dot(a: [f64; 3], b: [f64; 3]) -> f64 {
    (0..3).map(|i| a[i] * b[i]).sum()
}

fn cross(a: [f64; 3], b: [f64; 3]) -> [f64; 3] {
    [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]
}

fn add(a: [f64; 3], b: [f64; 3], k: f64) -> [f64; 3] {
    std::array::from_fn(|i| a[i] + b[i] * k)
}

/// The polygon's part where a·s + b·t <= c (Sutherland-Hodgman, one edge).
fn clip(polygon: &[(f64, f64)], a: f64, b: f64, c: f64) -> Vec<(f64, f64)> {
    let mut out = Vec::new();
    for i in 0..polygon.len() {
        let (p, q) = (polygon[i], polygon[(i + 1) % polygon.len()]);
        let (fp, fq) = (a * p.0 + b * p.1 - c, a * q.0 + b * q.1 - c);
        if fp <= 0.0 {
            out.push(p);
        }
        if (fp < 0.0 && fq > 0.0) || (fp > 0.0 && fq < 0.0) {
            let k = fp / (fp - fq);
            out.push((p.0 + (q.0 - p.0) * k, p.1 + (q.1 - p.1) * k));
        }
    }
    out
}

/// The fractions of the line from `from` to `to` whose ray toward the viewer
/// passes through the box: the s of the points (s, t) with
/// from + s·(to − from) + t·toward inside it, t > 0.
pub fn shadow(
    from: [f64; 3],
    to: [f64; 3],
    toward: [f64; 3],
    low: [f64; 3],
    high: [f64; 3],
) -> Option<(f64, f64)> {
    let d: [f64; 3] = std::array::from_fn(|i| to[i] - from[i]);
    let mut region = vec![
        (0.0, TOLERANCE_MM),
        (1.0, TOLERANCE_MM),
        (1.0, FAR_MM),
        (0.0, FAR_MM),
    ];
    for i in 0..3 {
        let (lo, hi) = (low[i] + TOLERANCE_MM, high[i] - TOLERANCE_MM);
        region = clip(&region, -d[i], -toward[i], from[i] - lo);
        region = clip(&region, d[i], toward[i], hi - from[i]);
        if region.len() < 3 {
            return None;
        }
    }
    let start = region
        .iter()
        .map(|p| p.0)
        .fold(f64::INFINITY, f64::min)
        .max(0.0);
    let end = region
        .iter()
        .map(|p| p.0)
        .fold(f64::NEG_INFINITY, f64::max)
        .min(1.0);
    (end - start > SAME).then_some((start, end))
}

/// A placed board's box and its lines in the world, each shown or not by the
/// board itself as solid::board_lines decides.
pub fn board_body(shape: Shape3D, holes: &[LocalHole], pose: &Pose, view: &Projection) -> Body {
    let size = [shape.width, shape.height, shape.length];
    let toward = view.toward();
    let faces = |normal: [f64; 3]| view.faces_viewer(rotate(&pose.rotation, normal));
    let mut segments = Vec::new();
    let mut push = |from: [f64; 3], to: [f64; 3], shown: bool| {
        segments.push(Segment3 {
            from: pose.apply(from),
            to: pose.apply(to),
            shown,
        });
    };
    for a in 0..3 {
        let (b, c) = ((a + 1) % 3, (a + 2) % 3);
        for (hb, hc) in [(false, false), (true, false), (false, true), (true, true)] {
            let mut from = [0.0; 3];
            from[b] = if hb { size[b] } else { 0.0 };
            from[c] = if hc { size[c] } else { 0.0 };
            let mut to = from;
            to[a] = size[a];
            let side = |axis: usize, high: bool| {
                let mut n = [0.0; 3];
                n[axis] = if high { 1.0 } else { -1.0 };
                n
            };
            push(from, to, faces(side(b, hb)) || faces(side(c, hc)));
        }
    }
    // The view in the board's own axes, for the sides of its bores
    let local_toward: [f64; 3] = std::array::from_fn(|k| {
        (0..3)
            .map(|r| f64::from(pose.rotation[r][k]) * toward[r])
            .sum()
    });
    for hole in holes {
        let n = hole.face.normal().map(f64::from);
        let axis = hole.face.axis();
        let depth = hole.depth.unwrap_or(size[axis]);
        let radius = hole.diameter / 2.0;
        let bottom = add(hole.point, n, -depth);
        let mouth_shown = faces(n);
        let exit_shown = hole.depth.is_none() && faces(n.map(|x| -x));
        for (centre, shown) in [(hole.point, mouth_shown), (bottom, exit_shown)] {
            let points = ring(centre, axis, radius);
            for pair in points.windows(2) {
                push(pair[0], pair[1], shown);
            }
        }
        let across = cross(n, local_toward);
        if dot(across, across) > 1e-12 {
            let length = dot(across, across).sqrt();
            let s = across.map(|x| x / length);
            for k in [1.0, -1.0] {
                let start = add(hole.point, s, k * radius);
                push(start, add(start, n, -depth), false);
            }
        }
    }
    let (low, high) = pose.bounds(shape);
    Body {
        low,
        high,
        segments,
    }
}

fn merged(mut spans: Vec<(f64, f64)>) -> Vec<(f64, f64)> {
    spans.sort_by(|a, b| a.0.total_cmp(&b.0));
    let mut out: Vec<(f64, f64)> = Vec::new();
    for (start, end) in spans {
        match out.last_mut() {
            Some(last) if start <= last.1 + SAME => last.1 = last.1.max(end),
            _ => out.push((start, end)),
        }
    }
    out
}

pub fn sort_lines(bodies: &[Body], view: &Projection) -> Vec<Sorted> {
    let toward = view.toward();
    bodies
        .iter()
        .enumerate()
        .map(|(i, body)| {
            let mut sorted = Sorted::default();
            for segment in &body.segments {
                let at = |s: f64| {
                    view.project(add(segment.from, add(segment.to, segment.from, -1.0), s))
                };
                if !segment.shown {
                    sorted.hidden.push((at(0.0), at(1.0)));
                    continue;
                }
                let shadows = bodies
                    .iter()
                    .enumerate()
                    .filter(|(j, _)| *j != i)
                    .filter_map(|(_, other)| {
                        shadow(segment.from, segment.to, toward, other.low, other.high)
                    })
                    .collect();
                let mut cursor = 0.0;
                for (start, end) in merged(shadows) {
                    if start - cursor > SAME {
                        sorted.visible.push((at(cursor), at(start)));
                    }
                    sorted.hidden.push((at(start), at(end)));
                    cursor = f64::max(cursor, end);
                }
                if 1.0 - cursor > SAME {
                    sorted.visible.push((at(cursor), at(1.0)));
                }
            }
            sorted
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::views::{axis_view, isometric};
    use nichiyou_daiku_core::geometry::Face;

    const FRONT: [f64; 3] = [0.0, 1.0, 0.0];
    const STILL: Pose = Pose {
        rotation: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        translation: [0.0, 0.0, 0.0],
    };
    const BOARD: Shape3D = Shape3D {
        width: 89.0,
        height: 38.0,
        length: 300.0,
    };

    #[test]
    fn a_box_in_front_hides_the_part_of_a_line_behind_it() {
        let (start, end) = shadow(
            [5.0, 10.0, 5.0],
            [15.0, 10.0, 5.0],
            FRONT,
            [0.0, 50.0, 0.0],
            [10.0, 60.0, 10.0],
        )
        .unwrap();
        assert!(start == 0.0 && (end - 0.5).abs() < 1e-6);
    }

    #[test]
    fn a_box_behind_hides_nothing() {
        assert_eq!(
            shadow(
                [5.0, 70.0, 5.0],
                [15.0, 70.0, 5.0],
                FRONT,
                [0.0, 50.0, 0.0],
                [10.0, 60.0, 10.0]
            ),
            None
        );
    }

    #[test]
    fn a_line_on_the_face_of_a_box_it_touches_stays_visible() {
        // The edge runs up x = 10, where the box beside it begins
        assert_eq!(
            shadow(
                [10.0, 10.0, 0.0],
                [10.0, 10.0, 10.0],
                FRONT,
                [10.0, 0.0, 0.0],
                [20.0, 20.0, 10.0]
            ),
            None
        );
    }

    #[test]
    fn a_board_alone_hides_its_three_back_edges() {
        let view = isometric();
        let sorted = sort_lines(&[board_body(BOARD, &[], &STILL, &view)], &view);
        assert_eq!((sorted[0].visible.len(), sorted[0].hidden.len()), (9, 3));
    }

    #[test]
    fn a_box_in_front_hides_a_hole_but_not_the_edges_it_misses() {
        let view = axis_view(1, 1);
        let hole = LocalHole {
            face: Face::Front,
            point: [44.5, 38.0, 150.0],
            diameter: 8.0,
            depth: Some(15.0),
        };
        let board = board_body(BOARD, &[hole], &STILL, &view);
        let blocker = Body {
            low: [30.0, 50.0, 130.0],
            high: [60.0, 60.0, 170.0],
            segments: Vec::new(),
        };
        let sorted = sort_lines(&[board, blocker], &view);
        // The front face's 4 edges show; the other 8, the mouth and the bottom (32 each) are hidden
        assert_eq!((sorted[0].visible.len(), sorted[0].hidden.len()), (4, 72));
    }
}
