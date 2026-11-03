//! The solid as triangles for the STL: circles in straight pieces, each
//! circle's points shared by every face along it, so the mesh closes up.

use crate::solid::{Curve, P3, Solid, Surface, Use};

pub struct Mesh {
    pub vertices: Vec<P3>,
    pub triangles: Vec<[usize; 3]>,
}

fn cross(a: P3, b: P3) -> P3 {
    [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]
}

fn dot(a: P3, b: P3) -> f64 {
    a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
}

fn cross2(o: [f64; 2], a: [f64; 2], b: [f64; 2]) -> f64 {
    (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
}

fn inside_triangle(p: [f64; 2], a: [f64; 2], b: [f64; 2], c: [f64; 2]) -> bool {
    cross2(a, b, p) > 1e-12 && cross2(b, c, p) > 1e-12 && cross2(c, a, p) > 1e-12
}

fn covers(p: [f64; 2], a: [f64; 2], b: [f64; 2], c: [f64; 2]) -> bool {
    const ON: f64 = -1e-9;
    cross2(a, b, p) >= ON && cross2(b, c, p) >= ON && cross2(c, a, p) >= ON
}

/// Joins a hole (clockwise) into the polygon (counter-clockwise) by a
/// bridge from its rightmost point to a point of the polygon it can see
/// (Eberly, "Triangulation by Ear Clipping").
fn bridge(points: &[[f64; 2]], polygon: &mut Vec<usize>, hole: &[usize]) {
    let (m_at, &m) = hole
        .iter()
        .enumerate()
        .max_by(|a, b| points[*a.1][0].total_cmp(&points[*b.1][0]))
        .expect("a hole has points");
    let mp = points[m];
    // The nearest polygon edge a ray to +x from M crosses. The ray leaves
    // the inside only through upward edges; a bridge's downward twin lies
    // on the same line but faces away
    let mut best: Option<(f64, usize)> = None;
    for k in 0..polygon.len() {
        let (a, b) = (points[polygon[k]], points[polygon[(k + 1) % polygon.len()]]);
        if (a[1] - mp[1]) * (b[1] - mp[1]) > 0.0 || a[1] >= b[1] {
            continue;
        }
        let x = a[0] + (mp[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1]);
        if x >= mp[0] && best.is_none_or(|(bx, _)| x < bx) {
            best = Some((x, k));
        }
    }
    let (ix, k) = best.expect("a hole lies inside its polygon");
    let next = (k + 1) % polygon.len();
    let mut p_at = if points[polygon[k]][0] > points[polygon[next]][0] {
        k
    } else {
        next
    };
    let i = [ix, mp[1]];
    // A point inside M-I-P would hide P: take the one at the smallest angle
    let p = points[polygon[p_at]];
    let mut best_angle = f64::MAX;
    for (q_at, &q) in polygon.iter().enumerate() {
        let qp = points[q];
        if q_at == p_at || !(inside_triangle(qp, mp, i, p) || inside_triangle(qp, mp, p, i)) {
            continue;
        }
        let angle = (qp[1] - mp[1]).abs().atan2(qp[0] - mp[0]);
        if angle < best_angle {
            best_angle = angle;
            p_at = q_at;
        }
    }
    let p = polygon[p_at];
    let mut joined: Vec<usize> = Vec::with_capacity(polygon.len() + hole.len() + 2);
    joined.extend_from_slice(&polygon[..=p_at]);
    joined.extend(hole[m_at..].iter().chain(&hole[..m_at]));
    joined.push(m);
    joined.push(p);
    joined.extend_from_slice(&polygon[p_at + 1..]);
    *polygon = joined;
}

/// Triangles over a polygon with holes: `outer` counter-clockwise, `holes`
/// clockwise, all as indices into `points`.
pub fn triangulate(points: &[[f64; 2]], outer: &[usize], holes: &[Vec<usize>]) -> Vec<[usize; 3]> {
    let mut polygon = outer.to_vec();
    let right = |h: &Vec<usize>| h.iter().map(|&i| points[i][0]).fold(f64::MIN, f64::max);
    let mut order: Vec<&Vec<usize>> = holes.iter().collect();
    order.sort_by(|a, b| right(b).total_cmp(&right(a)));
    for hole in order {
        bridge(points, &mut polygon, hole);
    }
    let mut triangles = Vec::new();
    while polygon.len() > 3 {
        let n = polygon.len();
        let corner = |k: usize| (polygon[(k + n - 1) % n], polygon[k], polygon[(k + 1) % n]);
        let ear = (0..n).find(|&k| {
            let (a, b, c) = corner(k);
            let (pa, pb, pc) = (points[a], points[b], points[c]);
            // A vertex on the cut would pinch the rest of the polygon there;
            // a bridge's copies of the corners are the corners themselves
            cross2(pa, pb, pc) > 1e-12
                && !polygon.iter().any(|&q| {
                    let pq = points[q];
                    pq != pa && pq != pb && pq != pc && covers(pq, pa, pb, pc)
                })
        });
        // Rounding can hide every ear: clip the most convex corner then
        let k = ear.unwrap_or_else(|| {
            let turn = |k: usize| {
                let (a, b, c) = corner(k);
                cross2(points[a], points[b], points[c])
            };
            (0..n)
                .max_by(|&x, &y| turn(x).total_cmp(&turn(y)))
                .expect("a polygon has corners")
        });
        let (a, b, c) = corner(k);
        triangles.push([a, b, c]);
        polygon.remove(k);
    }
    triangles.push([polygon[0], polygon[1], polygon[2]]);
    triangles
}

struct Builder<'a> {
    solid: &'a Solid,
    vertices: Vec<P3>,
    /// Each circle edge's points as mesh indices, its vertex first, in its
    /// own direction
    circles: Vec<Option<Vec<usize>>>,
    triangles: Vec<[usize; 3]>,
}

impl Builder<'_> {
    fn points(&mut self, edge: usize) -> Vec<usize> {
        if let Some(points) = &self.circles[edge] {
            return points.clone();
        }
        let e = self.solid.edges[edge];
        let Curve::Circle {
            centre,
            axis,
            x,
            radius,
            segments,
        } = e.curve
        else {
            return vec![e.start];
        };
        let y = cross(axis, x);
        let mut points = vec![e.start];
        for k in 1..segments {
            let a = k as f64 * std::f64::consts::TAU / segments as f64;
            let p = [0, 1, 2].map(|i| centre[i] + radius * (a.cos() * x[i] + a.sin() * y[i]));
            self.vertices.push(p);
            points.push(self.vertices.len() - 1);
        }
        self.circles[edge] = Some(points.clone());
        points
    }

    /// A loop's points in order: each edge's points but its last, which
    /// begins the next edge.
    fn walk(&mut self, uses: &[Use]) -> Vec<usize> {
        let mut out = Vec::new();
        for &(edge, along) in uses {
            let e = self.solid.edges[edge];
            match e.curve {
                Curve::Line { .. } => out.push(if along { e.start } else { e.end }),
                Curve::Circle { .. } => {
                    let mut points = self.points(edge);
                    if !along {
                        points[1..].reverse();
                    }
                    out.extend(points);
                }
            }
        }
        out
    }

    fn plane(&mut self, normal: P3, x: P3, loops: &[Vec<Use>]) {
        let y = cross(normal, x);
        let walks: Vec<Vec<usize>> = loops.iter().map(|l| self.walk(l)).collect();
        // Only this face's points are laid flat; the rest stay unused
        let mut flat = vec![[0.0, 0.0]; self.vertices.len()];
        for &i in walks.iter().flatten() {
            flat[i] = [dot(self.vertices[i], x), dot(self.vertices[i], y)];
        }
        let triangles = triangulate(&flat, &walks[0], &walks[1..]);
        self.triangles.extend(triangles);
    }

    /// A wall's loop: [start circle reversed, seam, end circle, seam back].
    fn wall(&mut self, uses: &[Use]) {
        let start = self.points(uses[0].0);
        let end = self.points(uses[2].0);
        let n = start.len();
        for k in 0..n {
            let (s0, s1, e0, e1) = (start[k], start[(k + 1) % n], end[k], end[(k + 1) % n]);
            // Facing the axis: out of the solid
            self.triangles.push([s0, e0, e1]);
            self.triangles.push([s0, e1, s1]);
        }
    }
}

pub fn mesh(solid: &Solid) -> Mesh {
    let mut b = Builder {
        solid,
        vertices: solid.vertices.clone(),
        circles: vec![None; solid.edges.len()],
        triangles: Vec::new(),
    };
    for face in &solid.faces {
        match face.surface {
            Surface::Plane { normal, x, .. } => {
                let out = if face.same_sense {
                    normal
                } else {
                    normal.map(|v| -v)
                };
                b.plane(out, x, &face.loops);
            }
            Surface::Cone { .. } => b.wall(&face.loops[0]),
        }
    }
    Mesh {
        vertices: b.vertices,
        triangles: b.triangles,
    }
}

/// The volume the triangles enclose (positive when they face out).
pub fn volume(mesh: &Mesh) -> f64 {
    mesh.triangles
        .iter()
        .map(|t| {
            let [a, b, c] = t.map(|i| mesh.vertices[i]);
            dot(a, cross(b, c)) / 6.0
        })
        .sum()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::bore::{Bore, Span};
    use crate::solid::piece_solid;
    use nichiyou_daiku_core::placement::Pose;

    fn still() -> Pose {
        Pose {
            rotation: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            translation: [0.0; 3],
        }
    }

    fn area(points: &[[f64; 2]], t: [usize; 3]) -> f64 {
        let [a, b, c] = t.map(|i| points[i]);
        ((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2.0
    }

    #[test]
    fn a_square_with_two_holes_is_covered_exactly() {
        let mut points = vec![[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]];
        let mut holes = Vec::new();
        for centre in [[3.0, 3.0], [7.0, 6.0]] {
            let start = points.len();
            // Clockwise
            for k in 0..16 {
                let a = -(k as f64) * std::f64::consts::TAU / 16.0;
                points.push([centre[0] + a.cos(), centre[1] + a.sin()]);
            }
            holes.push((start..start + 16).collect::<Vec<_>>());
        }
        let triangles = triangulate(&points, &[0, 1, 2, 3], &holes);
        assert!(triangles.iter().all(|&t| area(&points, t) > 0.0));
        let polygon = 16.0 / 2.0 * (std::f64::consts::TAU / 16.0).sin();
        let total: f64 = triangles.iter().map(|&t| area(&points, t)).sum();
        assert!((total - (100.0 - 2.0 * polygon)).abs() < 1e-9, "{total}");
    }

    #[test]
    fn holes_bridging_to_the_same_corner_still_cover_the_face() {
        // Two holes level with each other: both bridge to the top right corner
        let mut points = vec![[0.0, 0.0], [89.0, 0.0], [89.0, 701.0], [0.0, 701.0]];
        let mut holes = Vec::new();
        for z in [634.25, 678.75] {
            let start = points.len();
            for k in 0..16 {
                let a = -(k as f64) * std::f64::consts::TAU / 16.0;
                points.push([70.0 + 4.0 * a.cos(), z + 4.0 * a.sin()]);
            }
            holes.push((start..start + 16).collect::<Vec<_>>());
        }
        let triangles = triangulate(&points, &[0, 1, 2, 3], &holes);
        assert!(triangles.iter().all(|&t| area(&points, t) > 0.0));
        let polygon = 16.0 / 2.0 * 16.0 * (std::f64::consts::TAU / 16.0).sin();
        let total: f64 = triangles.iter().map(|&t| area(&points, t)).sum();
        assert!(
            (total - (89.0 * 701.0 - 2.0 * polygon)).abs() < 1e-6,
            "{total}"
        );
    }

    #[test]
    fn rows_of_holes_side_by_side_still_cover_the_face() {
        // A 2x2 leg's face with dowel holes in pairs across it
        let mut points = vec![[0.0, 0.0], [38.0, 0.0], [38.0, 500.0], [0.0, 500.0]];
        let mut holes = Vec::new();
        for z in [443.0, 276.3333333333333, 109.66666666666666] {
            for x in [9.5, 28.5] {
                let start = points.len();
                for k in 0..20 {
                    let a = k as f64 * std::f64::consts::TAU / 20.0;
                    points.push([x + 4.0 * a.cos(), z - 4.0 * a.sin()]);
                }
                holes.push((start..start + 20).collect::<Vec<_>>());
            }
        }
        let triangles = triangulate(&points, &[0, 1, 2, 3], &holes);
        assert!(triangles.iter().all(|&t| area(&points, t) > 0.0));
        let polygon = 20.0 / 2.0 * 16.0 * (std::f64::consts::TAU / 20.0).sin();
        let total: f64 = triangles.iter().map(|&t| area(&points, t)).sum();
        assert!(
            (total - (38.0 * 500.0 - 6.0 * polygon)).abs() < 1e-6,
            "{total}"
        );
    }

    /// Every edge of the mesh is used by two triangles, once each way.
    fn watertight(mesh: &Mesh) -> bool {
        let mut seen = std::collections::HashMap::new();
        for t in &mesh.triangles {
            for k in 0..3 {
                *seen.entry((t[k], t[(k + 1) % 3])).or_insert(0) += 1;
            }
        }
        seen.iter()
            .all(|(&(a, b), &n)| n == 1 && seen.get(&(b, a)) == Some(&1))
    }

    #[test]
    fn a_box_with_stepped_and_blind_holes_is_watertight() {
        let bores = [
            Bore {
                axis: 0,
                at: [19.0, 200.0],
                cavities: vec![vec![
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
            },
            Bore {
                axis: 1,
                at: [44.5, 100.0],
                cavities: vec![vec![Span {
                    t0: 0.0,
                    t1: 15.0,
                    r0: 4.0,
                    r1: 4.0,
                }]],
            },
            Bore {
                axis: 2,
                at: [44.5, 19.0],
                cavities: vec![vec![
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
            },
        ];
        let solid = piece_solid("a", [89.0, 38.0, 400.0], &bores, &still());
        let mesh = mesh(&solid);
        assert!(watertight(&mesh));
        let v = volume(&mesh);
        // Polygons inside circles: a little more solid than the exact shape
        let removed = 89.0 * 38.0 * 400.0 - solid.volume;
        assert!(
            v > solid.volume && v - solid.volume < 0.03 * removed,
            "{v} {}",
            solid.volume
        );
    }

    #[test]
    fn an_stl_is_binary_with_every_triangle() {
        let solid = piece_solid("a", [89.0, 38.0, 400.0], &[], &still());
        let bytes = crate::stl::stl(&[mesh(&solid)]);
        assert!(!bytes.starts_with(b"solid"));
        assert_eq!(u32::from_le_bytes(bytes[80..84].try_into().unwrap()), 12);
        assert_eq!(bytes.len(), 84 + 12 * 50);
    }
}
