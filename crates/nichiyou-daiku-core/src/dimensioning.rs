//! The dimensions an assembly step writes: chains along a world axis that
//! stop at both ends of chosen pieces and of the whole part (dimensioning.py:
//! chain_for; instructions.py: _dimension_view picks them).

use crate::assembly::Assembly;
use crate::model::Model;
use crate::placement::Bounds;
use crate::steps::PlannedStep;

/// Stops closer than this print as the same value, so they are merged.
pub const PRECISION_MM: f64 = 0.05;

/// Where a chain goes in its view: left of it (an upright axis) or below.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Side {
    Left,
    Below,
}

impl Side {
    pub fn as_str(self) -> &'static str {
        match self {
            Side::Left => "left",
            Side::Below => "below",
        }
    }
}

/// A stretch between neighbouring stops. `lumber` marks the width or
/// thickness of a piece that fills it: readers know it from the lumber.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Segment {
    pub start: f64,
    pub end: f64,
    pub lumber: bool,
}

/// Chain dimensions along one world axis; the overall size runs from the
/// first stop to the last. No segments when nothing stops between the ends.
#[derive(Clone, Debug, PartialEq)]
pub struct Chain {
    pub axis: usize,
    pub side: Side,
    pub stops: Vec<f64>,
    pub segments: Vec<Segment>,
}

/// `low`, `high` and the ends between them, merged within PRECISION_MM.
fn merged_stops(ends: &[f64], low: f64, high: f64) -> Vec<f64> {
    let mut inner: Vec<f64> = ends
        .iter()
        .copied()
        .filter(|&e| low + PRECISION_MM <= e && e <= high - PRECISION_MM)
        .collect();
    inner.sort_by(f64::total_cmp);
    let mut stops = vec![low];
    for value in inner {
        if value - *stops.last().expect("low is a stop") >= PRECISION_MM {
            stops.push(value);
        }
    }
    stops.push(high);
    stops
}

/// (low, high, (width, thickness)) of each chosen piece along the axis.
type Extent = (f64, f64, (f64, f64));

fn is_lumber(start: f64, end: f64, extents: &[Extent]) -> bool {
    extents.iter().any(|&(low, high, (width, thickness))| {
        let length = end - start;
        (low - start).abs() < PRECISION_MM
            && (high - end).abs() < PRECISION_MM
            && (length - width).abs().min((length - thickness).abs()) < PRECISION_MM
    })
}

/// Chain dimensions along `axis` over the boxes, stopping at both ends of
/// the chosen pieces; stretches that are a chosen piece's width or
/// thickness are lumber.
pub fn chain_for(
    axis: usize,
    side: Side,
    bounds: &[(String, Bounds)],
    model: &Model,
    chosen: &[String],
) -> Chain {
    let low = bounds
        .iter()
        .map(|(_, b)| b.0[axis])
        .fold(f64::INFINITY, f64::min);
    let high = bounds
        .iter()
        .map(|(_, b)| b.1[axis])
        .fold(f64::NEG_INFINITY, f64::max);
    let extents: Vec<Extent> = chosen
        .iter()
        .map(|id| {
            let (_, b) = bounds
                .iter()
                .find(|(p, _)| p == id)
                .expect("a chosen piece has a box");
            let piece = model.piece(id).expect("a piece of the model");
            (b.0[axis], b.1[axis], piece.kind.cross_section())
        })
        .collect();
    let ends: Vec<f64> = extents.iter().flat_map(|&(l, h, _)| [l, h]).collect();
    let stops = merged_stops(&ends, low, high);
    let segments = if stops.len() > 2 {
        stops
            .windows(2)
            .map(|w| Segment {
                start: w[0],
                end: w[1],
                lumber: is_lumber(w[0], w[1], &extents),
            })
            .collect()
    } else {
        Vec::new()
    };
    Chain {
        axis,
        side,
        stops,
        segments,
    }
}

fn cross(a: [f64; 3], b: [f64; 3]) -> [f64; 3] {
    [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]
}

/// The two axes across a step's view, in order, each lying across the view
/// (below it) or standing in it (left of it). The view's up is z, or -y
/// when it looks along z (views.py: axis_view, project).
pub(crate) fn chain_sides(view: (usize, i32)) -> Vec<(usize, Side)> {
    let (axis, sign) = view;
    let mut toward = [0.0; 3];
    toward[axis] = f64::from(sign);
    let up = if axis == 2 {
        [0.0, -1.0, 0.0]
    } else {
        [0.0, 0.0, 1.0]
    };
    let right = cross(up, toward);
    (0..3)
        .filter(|&a| a != axis)
        .map(|a| {
            (
                a,
                if right[a].abs() > up[a].abs() {
                    Side::Below
                } else {
                    Side::Left
                },
            )
        })
        .collect()
}

/// The step's chains, as the CLI's step image writes them: over the part the
/// step leaves, stopping at the step's pieces and the pieces they join.
pub fn step_dimensions(assembly: &Assembly, step: &PlannedStep) -> Vec<Chain> {
    let bounds: Vec<(String, Bounds)> = step
        .shown
        .iter()
        .map(|id| {
            let shape = assembly
                .model
                .piece(id)
                .expect("a piece of the model")
                .shape();
            (id.clone(), assembly.placement.pose(id).bounds(shape))
        })
        .collect();
    let mut partners: Vec<String> = step
        .connections
        .iter()
        .flat_map(|(a, b)| [a, b])
        .filter(|p| !step.pieces.contains(p))
        .cloned()
        .collect();
    partners.sort();
    partners.dedup();
    let chosen: Vec<String> = step.pieces.iter().cloned().chain(partners).collect();
    chain_sides(step.view)
        .into_iter()
        .map(|(axis, side)| chain_for(axis, side, &bounds, &assembly.model, &chosen))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::dsl::parse;

    fn boxes() -> Vec<(String, Bounds)> {
        vec![
            ("a".to_string(), ([0.0, 0.0, 0.0], [500.0, 38.0, 300.0])),
            ("b".to_string(), ([200.0, 0.0, 0.0], [289.0, 38.0, 300.0])),
            ("c".to_string(), ([200.04, 0.0, 0.0], [219.0, 38.0, 300.0])),
        ]
    }

    fn segment(start: f64, end: f64, lumber: bool) -> Segment {
        Segment { start, end, lumber }
    }

    #[test]
    fn stops_closer_than_the_precision_merge_and_lumber_sizes_are_marked() {
        let model = parse("(a:2x4 =300)\n(b:2x4 =300)\n(c:1x4 =300)\n").unwrap();
        let chain = chain_for(
            0,
            Side::Below,
            &boxes(),
            &model,
            &["b".to_string(), "c".to_string()],
        );
        assert_eq!(chain.stops, [0.0, 200.0, 219.0, 289.0, 500.0]);
        assert_eq!(
            chain.segments,
            [
                segment(0.0, 200.0, false),
                segment(200.0, 219.0, true), // c is 1x4: 19 thick
                segment(219.0, 289.0, false),
                segment(289.0, 500.0, false),
            ]
        );
    }

    #[test]
    fn only_the_ends_make_no_segments() {
        let model = parse("(a:2x4 =300)\n(b:2x4 =300)\n(c:1x4 =300)\n").unwrap();
        let chain = chain_for(0, Side::Below, &boxes(), &model, &["a".to_string()]);
        assert_eq!((chain.stops, chain.segments), (vec![0.0, 500.0], vec![]));
    }

    #[test]
    fn the_axes_across_a_view_lie_below_or_stand_left() {
        assert_eq!(chain_sides((1, 1)), [(0, Side::Below), (2, Side::Left)]);
        assert_eq!(chain_sides((2, 1)), [(0, Side::Below), (1, Side::Left)]);
        assert_eq!(chain_sides((0, -1)), [(1, Side::Below), (2, Side::Left)]);
        assert_eq!(Side::Below.as_str(), "below");
    }
}
