//! One board seen along a direction (a parallel projection, z up as the
//! CLI's isometric views): its edges and holes, visible or hidden. Nothing
//! else hides a lone board, so a line is hidden only by the board itself.

use nichiyou_daiku_core::geometry::Face;
use nichiyou_daiku_core::parts::LocalHole;

use crate::svg::Point;

const CIRCLE_SIDES: usize = 32;

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

fn unit(v: [f64; 3]) -> [f64; 3] {
    let length = dot(v, v).sqrt();
    v.map(|x| x / length)
}

fn add(a: [f64; 3], b: [f64; 3], k: f64) -> [f64; 3] {
    std::array::from_fn(|i| a[i] + b[i] * k)
}

pub struct Projection {
    toward: [f64; 3],
    up: [f64; 3],
    right: [f64; 3],
    centre: [f64; 3],
}

impl Projection {
    /// Looking from `direction` at `centre`, with z up.
    pub fn new(direction: [f64; 3], centre: [f64; 3]) -> Projection {
        Projection::looking(direction, [0.0, 0.0, 1.0], centre)
    }

    /// Looking from `direction` at `centre`, `up` (made square to the
    /// direction) up the page.
    pub fn looking(direction: [f64; 3], up: [f64; 3], centre: [f64; 3]) -> Projection {
        let toward = unit(direction);
        let up = unit(add(up, toward, -dot(up, toward)));
        Projection {
            toward,
            up,
            right: cross(up, toward),
            centre,
        }
    }

    pub fn project(&self, point: [f64; 3]) -> Point {
        let q = add(point, self.centre, -1.0);
        (dot(q, self.right), dot(q, self.up))
    }

    pub fn toward(&self) -> [f64; 3] {
        self.toward
    }

    pub fn faces_viewer(&self, normal: [f64; 3]) -> bool {
        dot(normal, self.toward) > 1e-9
    }
}

#[derive(Debug, Default)]
pub struct Lines {
    pub visible: Vec<Vec<Point>>,
    pub hidden: Vec<Vec<Point>>,
}

fn normal(face: Face) -> [f64; 3] {
    face.normal().map(f64::from)
}

/// A circle across `axis`, closed: its first point again at the end.
pub(crate) fn ring(centre: [f64; 3], axis: usize, radius: f64) -> Vec<[f64; 3]> {
    let (u, v) = match axis {
        0 => (1, 2),
        1 => (0, 2),
        _ => (0, 1),
    };
    (0..=CIRCLE_SIDES)
        .map(|k| {
            let angle = std::f64::consts::TAU * k as f64 / CIRCLE_SIDES as f64;
            let mut p = centre;
            p[u] += radius * angle.cos();
            p[v] += radius * angle.sin();
            p
        })
        .collect()
}

fn circle(view: &Projection, centre: [f64; 3], axis: usize, radius: f64) -> Vec<Point> {
    ring(centre, axis, radius)
        .into_iter()
        .map(|p| view.project(p))
        .collect()
}

pub fn board_lines(size: [f64; 3], holes: &[LocalHole], view: &Projection) -> Lines {
    let mut lines = Lines::default();
    let mut put = |points: Vec<Point>, visible: bool| {
        if visible {
            lines.visible.push(points)
        } else {
            lines.hidden.push(points)
        }
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
            let shown = view.faces_viewer(side(b, hb)) || view.faces_viewer(side(c, hc));
            put(vec![view.project(from), view.project(to)], shown);
        }
    }
    for hole in holes {
        let n = normal(hole.face);
        let axis = hole.face.axis();
        let depth = hole.depth.unwrap_or(size[axis]);
        let radius = hole.diameter / 2.0;
        let bottom = add(hole.point, n, -depth);
        put(circle(view, hole.point, axis, radius), view.faces_viewer(n));
        let out_back = hole.depth.is_none() && view.faces_viewer(n.map(|x| -x));
        put(circle(view, bottom, axis, radius), out_back);
        let across = cross(n, view.toward());
        if dot(across, across) > 1e-12 {
            let s = unit(across);
            for k in [1.0, -1.0] {
                let start = add(hole.point, s, k * radius);
                put(
                    vec![view.project(start), view.project(add(start, n, -depth))],
                    false,
                );
            }
        }
    }
    lines
}

#[cfg(test)]
mod tests {
    use super::*;

    const SIZE: [f64; 3] = [89.0, 38.0, 300.0];

    fn view(d: [f64; 3]) -> Projection {
        Projection::new(d, [44.5, 19.0, 150.0])
    }

    fn hole(face: Face, point: [f64; 3], depth: Option<f64>) -> LocalHole {
        LocalHole {
            face,
            point,
            diameter: 8.0,
            depth,
        }
    }

    #[test]
    fn a_box_from_a_corner_shows_nine_edges_and_hides_three() {
        let lines = board_lines(SIZE, &[], &view([1.0, 1.0, 1.0]));
        assert_eq!((lines.visible.len(), lines.hidden.len()), (9, 3));
    }

    #[test]
    fn a_hole_on_a_face_toward_the_viewer_shows_its_mouth() {
        let lines = board_lines(
            SIZE,
            &[hole(Face::Front, [44.5, 38.0, 150.0], Some(15.0))],
            &view([1.0, 1.0, 1.0]),
        );
        // + the mouth; the bottom and two sides of the bore are inside
        assert_eq!((lines.visible.len(), lines.hidden.len()), (10, 6));
        assert_eq!(lines.visible[9].len(), 33);
    }

    #[test]
    fn a_hole_on_a_face_away_is_hidden() {
        let lines = board_lines(
            SIZE,
            &[hole(Face::Back, [44.5, 0.0, 150.0], Some(15.0))],
            &view([1.0, 1.0, 1.0]),
        );
        assert_eq!((lines.visible.len(), lines.hidden.len()), (9, 7));
    }

    #[test]
    fn a_through_hole_shows_where_it_comes_out() {
        let lines = board_lines(
            SIZE,
            &[hole(Face::Front, [44.5, 38.0, 150.0], None)],
            &view([1.0, -1.0, 1.0]),
        );
        assert_eq!((lines.visible.len(), lines.hidden.len()), (10, 6));
    }

    #[test]
    fn the_view_keeps_z_up() {
        let p = view([1.0, 1.0, 1.0]);
        let (top, bottom) = (p.project([44.5, 19.0, 300.0]), p.project([44.5, 19.0, 0.0]));
        assert!(top.1 > bottom.1 && (top.0 - bottom.0).abs() < 1e-9);
        assert!(p.faces_viewer([0.0, 1.0, 0.0]) && !p.faces_viewer([0.0, -1.0, 0.0]));
    }
}
