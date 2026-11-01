//! Where a piece's name goes in a view (views.py: label_at): at its centre,
//! or along its longest side where its centre is hidden.

use nichiyou_daiku_core::placement::Bounds;

use crate::solid::Projection;
use crate::svg::Point;

/// A ray that only grazes a face or an edge of a box is not hidden by it
const TOLERANCE_MM: f64 = 1e-6;
/// Where along its longest side a piece is named when its centre is hidden
const FALLBACK: [f64; 4] = [0.25, 0.75, 0.125, 0.875];

/// Whether the ray from `start` along `direction` passes through the inside
/// of the box `low`..`high`.
pub fn blocks(start: [f64; 3], direction: [f64; 3], low: [f64; 3], high: [f64; 3]) -> bool {
    let (mut near, mut far) = (0.0_f64, f64::INFINITY);
    for axis in 0..3 {
        if direction[axis].abs() < 1e-12 {
            if !(low[axis] + TOLERANCE_MM < start[axis] && start[axis] < high[axis] - TOLERANCE_MM)
            {
                return false;
            }
            continue;
        }
        let t1 = (low[axis] - start[axis]) / direction[axis];
        let t2 = (high[axis] - start[axis]) / direction[axis];
        near = near.max(t1.min(t2));
        far = far.min(t1.max(t2));
    }
    far - near > TOLERANCE_MM
}

/// The point to name `piece` at, projected: its centre or, when another of
/// `boxes` hides that from the viewer, the first point along its longest
/// side that shows; None when none does.
pub fn label_at(boxes: &[(String, Bounds)], piece: &str, view: &Projection) -> Option<Point> {
    let (_, (low, high)) = boxes.iter().find(|(id, _)| id == piece)?;
    let centre: [f64; 3] = std::array::from_fn(|i| (low[i] + high[i]) / 2.0);
    // The first longest, as numpy's argmax
    let longest = (1..3).fold(0, |best, a| {
        if high[a] - low[a] > high[best] - low[best] {
            a
        } else {
            best
        }
    });
    let mut points = vec![centre];
    for fraction in FALLBACK {
        let mut point = centre;
        point[longest] = low[longest] + fraction * (high[longest] - low[longest]);
        points.push(point);
    }
    let toward = view.toward();
    points
        .into_iter()
        .find(|&point| {
            !boxes
                .iter()
                .any(|(id, (l, h))| id != piece && blocks(point, toward, *l, *h))
        })
        .map(|point| view.project(point))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::views::axis_view;

    fn boxes(blocker: Bounds) -> Vec<(String, Bounds)> {
        vec![
            ("long".to_string(), ([0.0, 0.0, 0.0], [100.0, 10.0, 10.0])),
            ("front".to_string(), blocker),
        ]
    }

    #[test]
    fn a_piece_is_named_at_its_centre_when_nothing_hides_it() {
        let view = axis_view(1, 1);
        let at = label_at(
            &boxes(([200.0, 20.0, 0.0], [210.0, 30.0, 10.0])),
            "long",
            &view,
        )
        .unwrap();
        assert!((at.0 + 50.0).abs() < 1e-9 && (at.1 - 5.0).abs() < 1e-9);
    }

    #[test]
    fn a_hidden_centre_moves_the_name_along_the_longest_side() {
        let view = axis_view(1, 1);
        let at = label_at(
            &boxes(([40.0, 20.0, 0.0], [60.0, 30.0, 10.0])),
            "long",
            &view,
        )
        .unwrap();
        // A quarter of the way along x: (25, 5, 5), seen from the front at (-25, 5)
        assert!((at.0 + 25.0).abs() < 1e-9 && (at.1 - 5.0).abs() < 1e-9);
    }

    #[test]
    fn a_piece_hidden_everywhere_has_no_name() {
        let view = axis_view(1, 1);
        assert_eq!(
            label_at(
                &boxes(([-10.0, 20.0, -10.0], [110.0, 30.0, 20.0])),
                "long",
                &view
            ),
            None
        );
    }
}
