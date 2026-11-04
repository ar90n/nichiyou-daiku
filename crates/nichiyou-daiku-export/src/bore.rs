//! The holes of a piece as cavities: holes on one axis line make one stepped
//! hole (a counterbore and the pilot drilled from the other face; a
//! countersink and its pilot), and a hole that runs into another line's is
//! left out (validate reports such holes as colliding).

use nichiyou_daiku_core::geometry::Face;
use nichiyou_daiku_core::parts::LocalHole;

/// Touching at a point or along a line is not running into each other
const EPSILON: f64 = 1e-6;

/// The axis a face's holes run along, and whether the face is at its high
/// end (left/back/down are at 0).
pub fn face_axis(face: Face) -> (usize, bool) {
    match face {
        Face::Left => (0, false),
        Face::Right => (0, true),
        Face::Back => (1, false),
        Face::Front => (1, true),
        Face::Down => (2, false),
        Face::Top => (2, true),
    }
}

/// A stretch of a cavity along its axis, `t` from the piece's low face on
/// that axis; the radius goes from `r0` at `t0` to `r1` at `t1`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Span {
    pub t0: f64,
    pub t1: f64,
    pub r0: f64,
    pub r1: f64,
}

impl Span {
    pub fn at(&self, t: f64) -> f64 {
        self.r0 + (self.r1 - self.r0) * (t - self.t0) / (self.t1 - self.t0)
    }

    /// A frustum's volume
    pub fn volume(&self) -> f64 {
        std::f64::consts::PI
            * (self.t1 - self.t0)
            * (self.r0 * self.r0 + self.r0 * self.r1 + self.r1 * self.r1)
            / 3.0
    }

    fn widest(&self) -> f64 {
        self.r0.max(self.r1)
    }
}

/// The cavities on one axis line of a piece.
#[derive(Clone, Debug, PartialEq)]
pub struct Bore {
    pub axis: usize,
    /// The line's other two coordinates, in axis order
    pub at: [f64; 2],
    pub cavities: Vec<Vec<Span>>,
}

type Line = (usize, [f64; 2]);

pub fn others(axis: usize) -> [usize; 2] {
    match axis {
        0 => [1, 2],
        1 => [0, 2],
        _ => [0, 1],
    }
}

/// A hole as stretches along its line, low `t` first.
fn hole_spans(hole: &LocalHole, size: [f64; 3]) -> (Line, Vec<Span>) {
    let (axis, high) = face_axis(hole.face);
    let length = size[axis];
    let depth = hole.depth.unwrap_or(length).min(length);
    let r = hole.diameter / 2.0;
    // Measured from the mouth inward: (depth from, depth to, r there, r there)
    let mut inward = Vec::new();
    match hole.countersink {
        Some(mouth) if mouth > hole.diameter => {
            // 90°: the radius narrows 1mm for each mm deeper
            let sink = ((mouth - hole.diameter) / 2.0).min(depth);
            inward.push((0.0, sink, mouth / 2.0, mouth / 2.0 - sink));
            if depth > sink {
                inward.push((sink, depth, r, r));
            }
        }
        _ => inward.push((0.0, depth, r, r)),
    }
    let mut spans: Vec<Span> = inward
        .into_iter()
        .map(|(d0, d1, r0, r1)| {
            if high {
                Span {
                    t0: length - d1,
                    t1: length - d0,
                    r0: r1,
                    r1: r0,
                }
            } else {
                Span {
                    t0: d0,
                    t1: d1,
                    r0,
                    r1,
                }
            }
        })
        .collect();
    spans.sort_by(|a, b| a.t0.total_cmp(&b.t0));
    let [i, j] = others(axis);
    ((axis, [hole.point[i], hole.point[j]]), spans)
}

fn same_line(a: &Line, b: &Line) -> bool {
    a.0 == b.0 && (a.1[0] - b.1[0]).abs() < EPSILON && (a.1[1] - b.1[1]).abs() < EPSILON
}

/// The point of a line at t = 0.
fn line_point((axis, at): &Line) -> [f64; 3] {
    let mut p = [0.0; 3];
    let [i, j] = others(*axis);
    p[i] = at[0];
    p[j] = at[1];
    p
}

fn distance_to(value: f64, low: f64, high: f64) -> f64 {
    if value < low {
        low - value
    } else if value > high {
        value - high
    } else {
        0.0
    }
}

/// Whether two stretches on different lines share more than a point, each
/// taken as a cylinder of its widest radius. Parallel ones touching along a
/// line meet: their mouths would touch on the face.
fn spans_meet(a: &Line, sa: &Span, b: &Line, sb: &Span) -> bool {
    let (pa, pb) = (line_point(a), line_point(b));
    let (ra, rb) = (sa.widest(), sb.widest());
    if a.0 == b.0 {
        let overlap = sa.t1.min(sb.t1) - sa.t0.max(sb.t0);
        let [i, j] = others(a.0);
        let apart = ((pa[i] - pb[i]).powi(2) + (pa[j] - pb[j]).powi(2)).sqrt();
        return overlap > EPSILON && apart < ra + rb + EPSILON;
    }
    let (i, j) = (a.0, b.0);
    let k = 3 - i - j;
    // How near each comes to the other's line, along the other's axis
    let di = distance_to(pb[i], sa.t0, sa.t1);
    let dj = distance_to(pa[j], sb.t0, sb.t1);
    if di >= rb - EPSILON || dj >= ra - EPSILON {
        return false;
    }
    (pa[k] - pb[k]).abs() < (ra * ra - dj * dj).sqrt() + (rb * rb - di * di).sqrt() - EPSILON
}

/// Where two stretches' radii cross inside both, if they do.
fn crossing(a: &Span, b: &Span) -> Option<f64> {
    let (low, high) = (a.t0.max(b.t0), a.t1.min(b.t1));
    if high - low <= EPSILON {
        return None;
    }
    let (fa, fb) = (a.at(low) - b.at(low), a.at(high) - b.at(high));
    if fa * fb >= 0.0 {
        return None;
    }
    Some(low + (high - low) * fa / (fa - fb))
}

fn slope(s: &Span) -> f64 {
    (s.r1 - s.r0) / (s.t1 - s.t0)
}

/// The cavities stretches on one line leave: where they overlap, the wider.
fn union(spans: &[Span]) -> Vec<Vec<Span>> {
    let mut cuts: Vec<f64> = spans.iter().flat_map(|s| [s.t0, s.t1]).collect();
    for (n, a) in spans.iter().enumerate() {
        for b in &spans[n + 1..] {
            cuts.extend(crossing(a, b));
        }
    }
    cuts.sort_by(f64::total_cmp);
    cuts.dedup_by(|a, b| (*a - *b).abs() < EPSILON);
    let mut cavities: Vec<Vec<Span>> = Vec::new();
    let mut open = false;
    for pair in cuts.windows(2) {
        let (c0, c1) = (pair[0], pair[1]);
        let middle = (c0 + c1) / 2.0;
        let widest = spans
            .iter()
            .filter(|s| s.t0 < middle && middle < s.t1)
            .max_by(|a, b| a.at(middle).total_cmp(&b.at(middle)));
        let Some(s) = widest else {
            open = false;
            continue;
        };
        let piece = Span {
            t0: c0,
            t1: c1,
            r0: s.at(c0),
            r1: s.at(c1),
        };
        if !open {
            cavities.push(vec![piece]);
            open = true;
            continue;
        }
        let cavity = cavities.last_mut().expect("an open cavity");
        let last = cavity.last_mut().expect("a stretch");
        if (last.r1 - piece.r0).abs() < EPSILON && (slope(last) - slope(&piece)).abs() < EPSILON {
            last.t1 = piece.t1;
            last.r1 = piece.r1;
        } else {
            cavity.push(piece);
        }
    }
    cavities
}

/// Why a hole is left out of the 3D.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Left {
    /// It runs into an earlier hole on another line
    RunsIntoAnother,
    /// Its widest part, of this radius, reaches a side of the piece: a box
    /// with holes cannot show the notch it would cut
    BreaksOut { radius: f64 },
}

/// The piece's cavities by line, in the order the holes come, and the holes
/// left out.
pub fn bores(holes: &[LocalHole], size: [f64; 3]) -> (Vec<Bore>, Vec<(LocalHole, Left)>) {
    let mut kept: Vec<(Line, Vec<Span>)> = Vec::new();
    let mut left = Vec::new();
    for hole in holes {
        let (line, spans) = hole_spans(hole, size);
        let radius = spans.iter().map(Span::widest).fold(0.0, f64::max);
        let (axis, at) = line;
        let [i, j] = others(axis);
        let room = at[0].min(size[i] - at[0]).min(at[1]).min(size[j] - at[1]);
        if radius >= room - EPSILON {
            left.push((*hole, Left::BreaksOut { radius }));
            continue;
        }
        let meets = kept.iter().any(|(other, theirs)| {
            !same_line(&line, other)
                && spans
                    .iter()
                    .any(|s| theirs.iter().any(|t| spans_meet(&line, s, other, t)))
        });
        if meets {
            left.push((*hole, Left::RunsIntoAnother));
        } else {
            kept.push((line, spans));
        }
    }
    let mut lines: Vec<(Line, Vec<Span>)> = Vec::new();
    for (line, spans) in kept {
        match lines.iter_mut().find(|(l, _)| same_line(l, &line)) {
            Some((_, all)) => all.extend(spans),
            None => lines.push((line, spans)),
        }
    }
    let bores = lines
        .into_iter()
        .map(|((axis, at), spans)| Bore {
            axis,
            at,
            cavities: union(&spans),
        })
        .collect();
    (bores, left)
}

#[cfg(test)]
mod tests {
    use super::*;

    const TWO_BY_FOUR: [f64; 3] = [89.0, 38.0, 400.0];

    fn hole(face: Face, point: [f64; 3], diameter: f64, depth: Option<f64>) -> LocalHole {
        LocalHole {
            face,
            point,
            diameter,
            depth,
            countersink: None,
        }
    }

    #[test]
    fn a_counterbore_and_its_pilot_from_the_other_face_make_one_stepped_hole() {
        let holes = [
            hole(Face::Left, [0.0, 19.0, 200.0], 10.0, Some(51.0)),
            hole(Face::Right, [89.0, 19.0, 200.0], 2.5, None),
        ];
        let (bores, left) = bores(&holes, TWO_BY_FOUR);
        assert!(left.is_empty());
        assert_eq!(bores.len(), 1);
        assert_eq!((bores[0].axis, bores[0].at), (0, [19.0, 200.0]));
        assert_eq!(
            bores[0].cavities,
            [vec![
                Span {
                    t0: 0.0,
                    t1: 51.0,
                    r0: 5.0,
                    r1: 5.0
                },
                Span {
                    t0: 51.0,
                    t1: 89.0,
                    r0: 1.25,
                    r1: 1.25
                },
            ]]
        );
    }

    #[test]
    fn a_countersink_narrows_to_its_pilot() {
        let mut sunk = hole(Face::Top, [44.5, 19.0, 400.0], 2.5, None);
        sunk.countersink = Some(7.5);
        let (bores, _) = bores(&[sunk], TWO_BY_FOUR);
        assert_eq!(
            bores[0].cavities,
            [vec![
                Span {
                    t0: 0.0,
                    t1: 397.5,
                    r0: 1.25,
                    r1: 1.25
                },
                Span {
                    t0: 397.5,
                    t1: 400.0,
                    r0: 1.25,
                    r1: 3.75
                },
            ]]
        );
    }

    #[test]
    fn blind_holes_from_both_faces_that_meet_make_one_cavity() {
        let holes = [
            hole(Face::Back, [44.5, 0.0, 100.0], 8.0, Some(20.0)),
            hole(Face::Front, [44.5, 38.0, 100.0], 8.0, Some(20.0)),
        ];
        let (bores, _) = bores(&holes, TWO_BY_FOUR);
        assert_eq!(
            bores[0].cavities,
            [vec![Span {
                t0: 0.0,
                t1: 38.0,
                r0: 4.0,
                r1: 4.0
            }]]
        );
    }

    #[test]
    fn blind_holes_that_do_not_meet_stay_apart() {
        let holes = [
            hole(Face::Back, [44.5, 0.0, 100.0], 8.0, Some(10.0)),
            hole(Face::Front, [44.5, 38.0, 100.0], 8.0, Some(10.0)),
        ];
        let (bores, _) = bores(&holes, TWO_BY_FOUR);
        assert_eq!(
            bores[0].cavities,
            [
                vec![Span {
                    t0: 0.0,
                    t1: 10.0,
                    r0: 4.0,
                    r1: 4.0
                }],
                vec![Span {
                    t0: 28.0,
                    t1: 38.0,
                    r0: 4.0,
                    r1: 4.0
                }],
            ]
        );
    }

    #[test]
    fn a_hole_running_into_another_line_is_left_out() {
        // A screw across the board through the end-grain dowel's path
        let dowel = hole(Face::Top, [44.5, 19.0, 400.0], 8.0, Some(30.0));
        let screw = hole(Face::Back, [44.5, 0.0, 385.0], 3.0, None);
        let (bores, left) = bores(&[dowel, screw], TWO_BY_FOUR);
        assert_eq!(bores.len(), 1);
        assert_eq!(left, [(screw, Left::RunsIntoAnother)]);
    }

    #[test]
    fn parallel_holes_touching_along_a_line_meet() {
        // Their mouths would touch on the face, which no face can hold
        let first = hole(Face::Back, [30.0, 0.0, 200.0], 8.0, Some(15.0));
        let second = hole(Face::Back, [38.0, 0.0, 200.0], 8.0, Some(15.0));
        let (bores, left) = bores(&[first, second], TWO_BY_FOUR);
        assert_eq!(bores.len(), 1);
        assert_eq!(left, [(second, Left::RunsIntoAnother)]);
    }

    #[test]
    fn a_hole_breaking_out_of_a_side_is_left_out() {
        // A φ10 counterbore 4mm from the back of a 2x4, one touching the
        // front, and a countersink's φ8.5 mouth 4.2mm from the left side
        let out = hole(Face::Left, [0.0, 4.0, 200.0], 10.0, Some(20.0));
        let touching = hole(Face::Left, [0.0, 33.0, 300.0], 10.0, Some(20.0));
        let sunk = LocalHole {
            countersink: Some(8.5),
            ..hole(Face::Back, [4.2, 0.0, 50.0], 2.5, None)
        };
        let inside = hole(Face::Left, [0.0, 19.0, 100.0], 10.0, Some(20.0));
        let (bores, left) = bores(&[out, touching, sunk, inside], TWO_BY_FOUR);
        assert_eq!(bores.len(), 1);
        assert_eq!(
            left,
            [
                (out, Left::BreaksOut { radius: 5.0 }),
                (touching, Left::BreaksOut { radius: 5.0 }),
                (sunk, Left::BreaksOut { radius: 4.25 }),
            ]
        );
    }

    #[test]
    fn holes_touching_at_a_point_both_stay() {
        // Two dowel holes whose ends meet at one corner point (eval designs)
        let holes = [
            hole(Face::Back, [70.0, 0.0, 95.25], 8.0, Some(15.0)),
            hole(Face::Right, [89.0, 19.0, 95.25], 8.0, Some(15.0)),
        ];
        let (bores, left) = bores(&holes, TWO_BY_FOUR);
        assert!(left.is_empty());
        assert_eq!(bores.len(), 2);
    }

    #[test]
    fn a_span_knows_its_volume() {
        let cylinder = Span {
            t0: 0.0,
            t1: 10.0,
            r0: 1.0,
            r1: 1.0,
        };
        assert!((cylinder.volume() - 10.0 * std::f64::consts::PI).abs() < 1e-9);
        let cone = Span {
            t0: 0.0,
            t1: 3.0,
            r0: 0.0,
            r1: 3.0,
        };
        assert!((cone.volume() - 9.0 * std::f64::consts::PI).abs() < 1e-9);
    }
}
