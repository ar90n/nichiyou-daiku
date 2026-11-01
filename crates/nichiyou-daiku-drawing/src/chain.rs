//! Chain dimensions drawn beside a view (drawing.py: draw_chain): extension
//! lines, the chain with its values (inside their stretch, else in a row on
//! leaders), then the overall size.

use nichiyou_daiku_core::dimensioning::{Chain, Side, spread};
use nichiyou_daiku_core::pyfmt::format_mm;

use crate::svg::Point;
use crate::text::{line_height, text_size};

pub const ARROW: f64 = 2.0;
/// Outline to the start of an extension line
pub const GAP: f64 = 1.0;
/// Extension line beyond its dimension line
pub const OVER: f64 = 2.0;
/// Text to the lines around it
pub const PAD: f64 = 0.6;
/// View to the chain's dimension line
pub const FIRST: f64 = 8.0;
/// Depth a leader slants across to reach its value
pub const SLANT: f64 = 2.5;
/// Outside row to the overall dimension line
pub const OVERALL: f64 = 4.0;

/// Distances out from a view's edge.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Levels {
    pub line: f64,
    pub bend: f64,
    pub row: f64,
    pub overall: f64,
    /// The farthest thing drawn: the band's depth
    pub depth: f64,
}

pub fn dimension_levels(side: Side) -> Levels {
    let height = line_height();
    // Values sit above their line: toward the view below it, and away from
    // the view beside it (read from the right of the page)
    let beyond = if side == Side::Below {
        OVER
    } else {
        OVER.max(PAD + height + PAD)
    };
    let line = FIRST;
    let bend = line + beyond;
    let row = bend + SLANT;
    // The band keeps its depth even when no value needs the outside row
    let overall = row + PAD + height + PAD + OVERALL;
    let text_beyond = if side == Side::Left {
        PAD + height
    } else {
        0.0
    };
    Levels {
        line,
        bend,
        row,
        overall,
        depth: overall + OVER.max(text_beyond),
    }
}

/// Where a chain's values land: along page x below its view, page y left of
/// it; `edge` is the view's bottom or left edge.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Placement {
    pub side: Side,
    pub edge: f64,
    pub origin: f64,
    pub scale: f64,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Label {
    pub text: String,
    pub centre: Point,
    pub vertical: bool,
}

/// Lines, arrows (tip and unit direction) and values drawn, and what did
/// not fit.
#[derive(Debug, Default)]
pub struct Drawn {
    pub lines: Vec<(Point, Point)>,
    pub arrows: Vec<(Point, Point)>,
    pub labels: Vec<Label>,
    pub crowded: Vec<String>,
}

pub fn arrow_points(tip: Point, direction: Point) -> [Point; 3] {
    let back = (tip.0 - direction.0 * ARROW, tip.1 - direction.1 * ARROW);
    let normal = (-direction.1 * ARROW / 6.0, direction.0 * ARROW / 6.0);
    [
        tip,
        (back.0 + normal.0, back.1 + normal.1),
        (back.0 - normal.0, back.1 - normal.1),
    ]
}

pub fn draw_chain(chain: &Chain, at: &Placement, out: &mut Drawn, values: &str, advice: &str) {
    let horizontal = at.side == Side::Below;
    let levels = dimension_levels(at.side);
    // Depth of a value's top: toward the view below, away from it beside
    let up = if horizontal { -1.0 } else { 1.0 };
    let along = |value: f64| at.origin + value * at.scale;
    // Dimensions go below or left: page y or x decreases with depth
    let point = |position: f64, depth: f64| -> Point {
        if horizontal {
            (position, at.edge - depth)
        } else {
            (at.edge - depth, position)
        }
    };
    let label = |out: &mut Drawn, text: &str, position: f64, depth: f64| {
        out.labels.push(Label {
            text: text.to_string(),
            centre: point(position, depth),
            vertical: !horizontal,
        });
    };
    let dimension_line = |out: &mut Drawn, low: f64, high: f64, depth: f64| {
        out.lines.push((point(low, depth), point(high, depth)));
        let (backward, forward) = if horizontal {
            ((-1.0, 0.0), (1.0, 0.0))
        } else {
            ((0.0, -1.0), (0.0, 1.0))
        };
        out.arrows.push((point(low, depth), backward));
        out.arrows.push((point(high, depth), forward));
    };
    let first = along(chain.stops[0]);
    let last = along(*chain.stops.last().expect("a chain has two stops"));
    let (low, high) = (first.min(last), first.max(last));
    let (overall, start) = if chain.segments.is_empty() {
        (levels.line, GAP)
    } else {
        for &stop in &chain.stops {
            out.lines.push((
                point(along(stop), GAP),
                point(along(stop), levels.line + OVER),
            ));
        }
        let mut outside: Vec<(String, f64, f64, f64)> = Vec::new();
        for segment in &chain.segments {
            let (a, b) = {
                let (s, e) = (along(segment.start), along(segment.end));
                (s.min(e), s.max(e))
            };
            dimension_line(out, a, b, levels.line);
            let text = format_mm(segment.end - segment.start);
            let (length, across) = text_size(&text);
            if length + 2.0 * PAD <= b - a {
                label(
                    out,
                    &text,
                    (a + b) / 2.0,
                    levels.line + up * (PAD + across / 2.0),
                );
            } else if !segment.lumber {
                outside.push((text, (a + b) / 2.0, length, across));
            }
        }
        if !outside.is_empty() {
            // A view can run the axis leftward or down; spread wants page order
            outside.sort_by(|x, y| x.1.total_cmp(&y.1));
            let middles: Vec<f64> = outside.iter().map(|o| o.1).collect();
            let lengths: Vec<f64> = outside.iter().map(|o| o.2).collect();
            let (centres, fits) = spread(&middles, &lengths, low + PAD, high - PAD, 2.0 * PAD);
            if !fits {
                out.crowded.push(format!(
                    "{} {values} do not fit beside their chain without crossing its lines. {advice}",
                    outside.len()
                ));
            }
            for ((text, middle, _, across), centre) in outside.iter().zip(centres) {
                out.lines
                    .push((point(*middle, levels.line), point(*middle, levels.bend)));
                out.lines
                    .push((point(*middle, levels.bend), point(centre, levels.row)));
                label(out, text, centre, levels.row + PAD + across / 2.0);
            }
        }
        (levels.overall, levels.line + OVER)
    };
    for end in [low, high] {
        out.lines
            .push((point(end, start), point(end, overall + OVER)));
    }
    dimension_line(out, low, high, overall);
    let text = format_mm(chain.stops.last().expect("two stops") - chain.stops[0]);
    let (length, across) = text_size(&text);
    let position = if length + 2.0 * PAD <= high - low {
        (low + high) / 2.0
    } else {
        // Too long for the stretch: beyond its low end, on the dimension
        // line extended under it (JIS)
        out.lines.push((
            point(low, overall),
            point(low - 2.0 * PAD - length, overall),
        ));
        low - PAD - length / 2.0
    };
    label(out, &text, position, overall + up * (PAD + across / 2.0));
}

#[cfg(test)]
mod tests {
    use super::*;
    use nichiyou_daiku_core::dimensioning::{Segment, chain_from_stops};

    fn below() -> Placement {
        Placement {
            side: Side::Below,
            edge: 50.0,
            origin: 10.0,
            scale: 1.0,
        }
    }

    fn near(a: Point, b: Point) -> bool {
        (a.0 - b.0).abs() < 1e-3 && (a.1 - b.1).abs() < 1e-3
    }

    fn label<'a>(out: &'a Drawn, text: &str) -> &'a Label {
        out.labels.iter().find(|l| l.text == text).expect(text)
    }

    #[test]
    fn bands_below_and_left_of_a_view() {
        let b = dimension_levels(Side::Below);
        assert_eq!((b.line, b.bend, b.row), (8.0, 10.0, 12.5));
        assert!((b.overall - 20.2).abs() < 1e-9 && (b.depth - 22.2).abs() < 1e-9);
        let l = dimension_levels(Side::Left);
        assert!(
            (l.bend - 11.7).abs() < 1e-9
                && (l.overall - 21.9).abs() < 1e-9
                && (l.depth - 25.0).abs() < 1e-9
        );
    }

    #[test]
    fn values_that_fit_sit_on_their_stretch_and_the_overall_below() {
        let mut out = Drawn::default();
        draw_chain(
            &chain_from_stops(0, Side::Below, &[0.0, 100.0, 300.0]),
            &below(),
            &mut out,
            "values",
            "",
        );
        assert!(near(label(&out, "100").centre, (60.0, 43.85)));
        assert!(near(label(&out, "200").centre, (210.0, 43.85)));
        assert!(near(label(&out, "300").centre, (160.0, 31.65)));
        assert!(
            out.lines
                .iter()
                .any(|&(a, b)| near(a, (10.0, 49.0)) && near(b, (10.0, 40.0)))
        );
        assert_eq!(out.arrows.len(), 6);
        assert!(out.crowded.is_empty());
    }

    #[test]
    fn a_value_too_long_for_its_stretch_goes_to_the_row_on_a_leader() {
        let mut out = Drawn::default();
        draw_chain(
            &chain_from_stops(0, Side::Below, &[0.0, 2.0, 300.0]),
            &below(),
            &mut out,
            "values",
            "",
        );
        assert!(near(label(&out, "2").centre, (11.6515, 35.65)));
        assert!(
            out.lines
                .iter()
                .any(|&(a, b)| near(a, (11.0, 40.0)) && near(b, (11.6515, 37.5)))
        );
    }

    #[test]
    fn lumber_values_that_do_not_fit_are_left_out() {
        let chain = Chain {
            axis: 0,
            side: Side::Below,
            stops: vec![0.0, 2.0, 300.0],
            segments: vec![
                Segment {
                    start: 0.0,
                    end: 2.0,
                    lumber: true,
                },
                Segment {
                    start: 2.0,
                    end: 300.0,
                    lumber: false,
                },
            ],
        };
        let mut out = Drawn::default();
        draw_chain(&chain, &below(), &mut out, "values", "");
        assert_eq!(
            out.labels
                .iter()
                .map(|l| l.text.as_str())
                .collect::<Vec<_>>(),
            ["298", "300"]
        );
    }

    #[test]
    fn an_overall_value_too_long_goes_past_the_low_end() {
        let mut out = Drawn::default();
        draw_chain(
            &chain_from_stops(0, Side::Below, &[0.0, 3.0]),
            &below(),
            &mut out,
            "values",
            "",
        );
        assert!(near(label(&out, "3").centre, (8.3485, 43.85)));
        assert!(
            out.lines
                .iter()
                .any(|&(a, b)| near(a, (10.0, 42.0)) && near(b, (6.697, 42.0)))
        );
    }

    #[test]
    fn crowded_values_are_reported() {
        let mut out = Drawn::default();
        let chain = chain_from_stops(0, Side::Below, &[0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]);
        draw_chain(
            &chain,
            &below(),
            &mut out,
            "horizontal dimension values in face A",
            "Advice.",
        );
        assert_eq!(
            out.crowded,
            [
                "6 horizontal dimension values in face A do not fit beside their chain without crossing its lines. Advice."
            ]
        );
    }

    #[test]
    fn a_chain_left_of_its_view_reads_up_the_page() {
        let mut out = Drawn::default();
        let at = Placement {
            side: Side::Left,
            edge: 50.0,
            origin: 10.0,
            scale: 1.0,
        };
        draw_chain(
            &chain_from_stops(2, Side::Left, &[0.0, 100.0]),
            &at,
            &mut out,
            "values",
            "",
        );
        let value = label(&out, "100");
        assert!(near(value.centre, (40.15, 60.0)) && value.vertical);
    }

    #[test]
    fn arrows_are_triangles_at_their_tip() {
        let [tip, a, b] = arrow_points((0.0, 0.0), (1.0, 0.0));
        assert!(near(tip, (0.0, 0.0)) && near(a, (-2.0, 1.0 / 3.0)) && near(b, (-2.0, -1.0 / 3.0)));
    }
}
