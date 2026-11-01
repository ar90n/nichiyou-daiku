//! Step images (instructions.py: step_image): the part a step leaves from
//! the isometric on the left, the step's pieces in black and the earlier
//! ones grey, its dimension view on the right, the heading on top.

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_core::dimensioning::{Side, step_dimensions};
use nichiyou_daiku_core::parts::piece_holes;
use nichiyou_daiku_core::placement::Bounds;
use nichiyou_daiku_core::steps::{PlannedStep, StepKind};

use crate::chain::{Drawn, Placement, arrow_points, dimension_levels, draw_chain};
use crate::hidden::{Sorted, board_body, sort_lines};
use crate::labels::label_at;
use crate::solid::Projection;
use crate::svg::{Ink, Point, Stroke, Svg};
use crate::text::text_size;
use crate::views::{axis_view, isometric};

pub const PAGE_WIDTH: f64 = 280.0;
pub const PAGE_HEIGHT: f64 = 140.0;
const MARGIN: f64 = 6.0;
/// Band at the top for the step's heading
const HEADING: f64 = 10.0;
const ISO_FILL: f64 = 0.9;
// The arrow showing the way the dimension view looks stays in the
// isometric's lower left corner, which a box seen from -x +y +z leaves
// empty; only its direction changes
const CUE_CENTRE: Point = (MARGIN + 22.0, MARGIN + 16.0);
const CUE_LENGTH: f64 = 30.0;
const CUE_WIDTH: f64 = 5.0;
const CUE_HEAD: f64 = 10.0;
const CUE_HEAD_WIDTH: f64 = 12.0;
/// A drawing nearer the arrow than this would seem pushed by it
const CUE_CLEARANCE: f64 = 6.0;
/// Grey names closer than this across the view do not tell it which way round
const APART: f64 = 10.0;
const AXES: [&str; 3] = ["x", "y", "z"];
pub const SPLIT_ADVICE: &str = "Split the step into steps that add fewer pieces";
pub const ONE_PIECE_ADVICE: &str = "The report's Anchor Details give where each connection is";

pub type Rect = (f64, f64, f64, f64);
/// A piece's visible lines on the page, and points along them
type Seen = (String, Vec<(Point, Point)>, Vec<Point>);

pub struct StepSheet {
    pub heading: String,
    pub labels: Vec<(String, Rect)>,
    pub dimension_labels: Vec<(String, Rect)>,
    pub references: Vec<String>,
    pub cue: Vec<Point>,
    pub iso_lines: Vec<(Point, Point)>,
    pub new_hidden: Vec<(Point, Point)>,
    pub notes: Vec<String>,
    pub svg: String,
}

pub fn heading(step: &PlannedStep) -> String {
    let name = step
        .name
        .as_ref()
        .map_or(String::new(), |name| format!(" - {name}"));
    let mark = match step.kind {
        StepKind::SubAssembly => " (sub-assembly)",
        StepKind::Join => " (join)",
        _ => "",
    };
    format!("Step {}{name}{mark}", step.number)
}

/// What to do when a step's values do not fit: a step of one piece cannot be
/// split, so the report has to give its places.
pub fn advice(step: &PlannedStep) -> &'static str {
    if step.pieces.len() > 1 {
        SPLIT_ADVICE
    } else {
        ONE_PIECE_ADVICE
    }
}

/// The arrow's outline, pointing the way a view from `view` (axis, side)
/// looks: flat on the floor, or straight down the page from above.
pub fn cue(view: (usize, i32)) -> Vec<Point> {
    let (axis, side) = view;
    // How much the isometric shortens a level line
    let shorten = (2.0_f64 / 3.0).sqrt();
    let (way, across) = if axis == 2 {
        ((0.0, -f64::from(side) * shorten), (shorten, 0.0))
    } else {
        let mut looking = [0.0; 3];
        looking[axis] = f64::from(-side);
        let mut sideways = [0.0; 3];
        sideways[1 - axis] = 1.0;
        let iso = isometric();
        (iso.project(looking), iso.project(sideways))
    };
    let at = |base: Point, k: f64, v: Point| (base.0 + v.0 * k, base.1 + v.1 * k);
    let tail = at(CUE_CENTRE, -CUE_LENGTH / 2.0, way);
    let tip = at(CUE_CENTRE, CUE_LENGTH / 2.0, way);
    let neck = at(tip, -CUE_HEAD, way);
    vec![
        at(tail, CUE_WIDTH / 2.0, across),
        at(neck, CUE_WIDTH / 2.0, across),
        at(neck, CUE_HEAD_WIDTH / 2.0, across),
        tip,
        at(neck, -CUE_HEAD_WIDTH / 2.0, across),
        at(neck, -CUE_WIDTH / 2.0, across),
        at(tail, -CUE_WIDTH / 2.0, across),
    ]
}

fn piece_lines(
    assembly: &Assembly,
    step: &PlannedStep,
    view: &Projection,
) -> Vec<(String, Sorted)> {
    let bodies: Vec<_> = step
        .shown
        .iter()
        .map(|id| {
            let piece = assembly.model.piece(id).expect("a piece of the model");
            board_body(
                piece.shape(),
                &piece_holes(assembly, id),
                assembly.placement.pose(id),
                view,
            )
        })
        .collect();
    step.shown
        .iter()
        .cloned()
        .zip(sort_lines(&bodies, view))
        .collect()
}

fn bounds(lines: &[(String, Sorted)]) -> Rect {
    let mut b = (
        f64::INFINITY,
        f64::INFINITY,
        f64::NEG_INFINITY,
        f64::NEG_INFINITY,
    );
    for (_, sorted) in lines {
        for &(p, q) in sorted.visible.iter().chain(&sorted.hidden) {
            for point in [p, q] {
                b = (
                    b.0.min(point.0),
                    b.1.min(point.1),
                    b.2.max(point.0),
                    b.3.max(point.1),
                );
            }
        }
    }
    b
}

/// Scale and offset that centre `b` in `area`, `fill` of it.
fn fit(b: Rect, area: Rect, fill: f64) -> (f64, Point) {
    let factor = fill * ((area.2 - area.0) / (b.2 - b.0)).min((area.3 - area.1) / (b.3 - b.1));
    let centre = ((area.0 + area.2) / 2.0, (area.1 + area.3) / 2.0);
    (
        factor,
        (
            centre.0 - (b.0 + b.2) / 2.0 * factor,
            centre.1 - (b.1 + b.3) / 2.0 * factor,
        ),
    )
}

fn place(p: Point, factor: f64, offset: Point) -> Point {
    (offset.0 + p.0 * factor, offset.1 + p.1 * factor)
}

/// Points along the visible lines, close enough to stand for them.
fn samples(segments: &[(Point, Point)]) -> Vec<Point> {
    segments
        .iter()
        .flat_map(|&(a, b)| {
            (0..=20).map(move |k| {
                let t = f64::from(k) / 20.0;
                (a.0 + (b.0 - a.0) * t, a.1 + (b.1 - a.1) * t)
            })
        })
        .collect()
}

/// Whether `p` lies on the segment, but for rounding.
fn on_segment(p: Point, (a, b): (Point, Point)) -> bool {
    let (dx, dy) = (b.0 - a.0, b.1 - a.1);
    let length = dx * dx + dy * dy;
    let t = if length > 0.0 {
        (((p.0 - a.0) * dx + (p.1 - a.1) * dy) / length).clamp(0.0, 1.0)
    } else {
        0.0
    };
    let (x, y) = (a.0 + dx * t - p.0, a.1 + dy * t - p.1);
    x * x + y * y < 1e-12
}

fn inside(p: Point, r: Rect) -> bool {
    r.0 < p.0 && p.0 < r.2 && r.1 < p.1 && p.1 < r.3
}

fn box_of(points: &[Point], grow: f64) -> Rect {
    let r = points.iter().fold(
        (
            f64::INFINITY,
            f64::INFINITY,
            f64::NEG_INFINITY,
            f64::NEG_INFINITY,
        ),
        |r, p| (r.0.min(p.0), r.1.min(p.1), r.2.max(p.0), r.3.max(p.1)),
    );
    (r.0 - grow, r.1 - grow, r.2 + grow, r.3 + grow)
}

/// `fit` in `area`, drawn smaller until no line comes into `keep_out`.
fn clear_fit(lines: &[(String, Sorted)], area: Rect, keep_out: Rect) -> (f64, Point) {
    let all: Vec<(Point, Point)> = lines
        .iter()
        .flat_map(|(_, s)| s.visible.iter().copied())
        .collect();
    let points = samples(&all);
    let b = bounds(lines);
    let mut fill = ISO_FILL;
    loop {
        let (factor, offset) = fit(b, area, fill);
        let clear = !points
            .iter()
            .any(|&p| inside(place(p, factor, offset), keep_out));
        if clear || fill < 0.3 {
            return (factor, offset);
        }
        fill *= 0.95;
    }
}

fn free(r: Rect, taken: &[Rect]) -> bool {
    taken
        .iter()
        .all(|b| r.2 <= b.0 || b.2 <= r.0 || r.3 <= b.1 || b.3 <= r.1)
}

/// Whether a segment passes through the inside of a box (Liang-Barsky).
fn crosses(r: Rect, (a, b): (Point, Point)) -> bool {
    let (dx, dy) = (b.0 - a.0, b.1 - a.1);
    let (mut start, mut end) = (0.0_f64, 1.0_f64);
    for (p, q) in [
        (-dx, a.0 - r.0),
        (dx, r.2 - a.0),
        (-dy, a.1 - r.1),
        (dy, r.3 - a.1),
    ] {
        if p == 0.0 {
            if q <= 0.0 {
                return false;
            }
        } else if p < 0.0 {
            start = start.max(q / p);
        } else {
            end = end.min(q / p);
        }
    }
    start < end
}

fn named(
    world: &[(String, Bounds)],
    view: &Projection,
    pieces: &[String],
    scale: f64,
    offset: Point,
    taken: &[Rect],
    segments: &[(Point, Point)],
) -> Vec<(String, Rect)> {
    let mut boxes: Vec<(String, Rect)> = Vec::new();
    for id in pieces {
        let Some(point) = label_at(world, id, view) else {
            continue;
        };
        let (x, y) = place(point, scale, offset);
        let (w, h) = text_size(id);
        let r = (x - w / 2.0, y - h / 2.0, x + w / 2.0, y + h / 2.0);
        let others: Vec<Rect> = taken
            .iter()
            .copied()
            .chain(boxes.iter().map(|(_, b)| *b))
            .collect();
        if free(r, &others) && !segments.iter().any(|s| crosses(r, *s)) {
            boxes.push((id.clone(), r));
        }
    }
    boxes
}

pub fn step_sheet(assembly: &Assembly, step: &PlannedStep) -> StepSheet {
    let new = |id: &str| step.pieces.iter().any(|p| p == id);
    let mut svg = Svg::new(PAGE_WIDTH);
    // A light border keeps every step's image the same size
    svg.polyline(
        &[
            (0.0, 0.0),
            (PAGE_WIDTH, 0.0),
            (PAGE_WIDTH, PAGE_HEIGHT),
            (0.0, PAGE_HEIGHT),
        ],
        true,
        Stroke::Before,
    );

    // The isometric, clear of the arrow
    let iso = isometric();
    let iso_area = (
        MARGIN,
        MARGIN,
        PAGE_WIDTH / 2.0 - MARGIN,
        PAGE_HEIGHT - HEADING,
    );
    let iso_raw = piece_lines(assembly, step, &iso);
    let cue = cue(step.view);
    let keep_out = box_of(&cue, CUE_CLEARANCE);
    let (factor, offset) = clear_fit(&iso_raw, iso_area, keep_out);
    let mut iso_lines = Vec::new();
    for (id, sorted) in &iso_raw {
        // Dashed back edges only crowd the isometric
        let stroke = if new(id) { Stroke::New } else { Stroke::Before };
        for &(a, b) in &sorted.visible {
            let (a, b) = (place(a, factor, offset), place(b, factor, offset));
            svg.line(a, b, stroke);
            iso_lines.push((a, b));
        }
    }

    // The dimension view, the bands left and below
    let view = axis_view(step.view.0, step.view.1);
    let area = (
        PAGE_WIDTH / 2.0 + MARGIN,
        MARGIN,
        PAGE_WIDTH - MARGIN,
        PAGE_HEIGHT - HEADING,
    );
    let dim_raw = piece_lines(assembly, step, &view);
    let (left, below) = (
        dimension_levels(Side::Left).depth,
        dimension_levels(Side::Below).depth,
    );
    let inner = (area.0 + left, area.1 + below, area.2, area.3);
    let b = bounds(&dim_raw);
    let scale = ((inner.2 - inner.0) / (b.2 - b.0)).min((inner.3 - inner.1) / (b.3 - b.1));
    let shift = (inner.0 - b.0 * scale, inner.3 - b.3 * scale);
    let frame = (
        inner.0,
        inner.3 - (b.3 - b.1) * scale,
        inner.0 + (b.2 - b.0) * scale,
        inner.3,
    );
    let mut drawn = Drawn::default();
    for chain in step_dimensions(assembly, step) {
        let mut unit = [0.0; 3];
        unit[chain.axis] = 1.0;
        let (ux, uy) = view.project(unit);
        let at = if chain.side == Side::Below {
            Placement {
                side: Side::Below,
                edge: frame.1,
                origin: shift.0,
                scale: ux * scale,
            }
        } else {
            Placement {
                side: Side::Left,
                edge: frame.0,
                origin: shift.1,
                scale: uy * scale,
            }
        };
        let values = format!(
            "dimension values along {} in step {}",
            AXES[chain.axis], step.number
        );
        draw_chain(&chain, &at, &mut drawn, &values, advice(step));
    }
    let mut new_hidden = Vec::new();
    for (id, sorted) in &dim_raw {
        let stroke = if new(id) { Stroke::New } else { Stroke::Before };
        for &(a, b) in &sorted.visible {
            svg.line(place(a, scale, shift), place(b, scale, shift), stroke);
        }
        // They show this step's pieces where earlier ones hide them
        if new(id) {
            for &(a, b) in &sorted.hidden {
                let line = (place(a, scale, shift), place(b, scale, shift));
                svg.line(line.0, line.1, Stroke::NewHidden);
                new_hidden.push(line);
            }
        }
    }
    for &(a, b) in &drawn.lines {
        svg.line(a, b, Stroke::Thin);
    }

    let world: Vec<(String, Bounds)> = step
        .shown
        .iter()
        .map(|id| {
            let piece = assembly.model.piece(id).expect("a piece of the model");
            (
                id.clone(),
                assembly.placement.pose(id).bounds(piece.shape()),
            )
        })
        .collect();
    let mut labels = named(&world, &iso, &step.pieces, factor, offset, &[keep_out], &[]);
    let values: Vec<Rect> = drawn
        .labels
        .iter()
        .map(|label| {
            let (w, h) = text_size(&label.text);
            let (w, h) = if label.vertical { (h, w) } else { (w, h) };
            (
                label.centre.0 - w / 2.0,
                label.centre.1 - h / 2.0,
                label.centre.0 + w / 2.0,
                label.centre.1 + h / 2.0,
            )
        })
        .collect();
    let mut segments = drawn.lines.clone();
    for &(tip, direction) in &drawn.arrows {
        let [a, b, c] = arrow_points(tip, direction);
        segments.extend([(a, b), (b, c), (c, a)]);
    }
    let mut dimension_labels = named(
        &world,
        &view,
        &step.pieces,
        scale,
        shift,
        &values,
        &segments,
    );
    let placed = |raw: &[(String, Sorted)], k: f64, at: Point| -> Vec<Seen> {
        raw.iter()
            .map(|(id, sorted)| {
                let lines: Vec<(Point, Point)> = sorted
                    .visible
                    .iter()
                    .map(|&(a, b)| (place(a, k, at), place(b, k, at)))
                    .collect();
                let points = samples(&lines);
                (id.clone(), lines, points)
            })
            .collect()
    };
    let iso_seen = placed(&iso_raw, factor, offset);
    let dim_seen = placed(&dim_raw, scale, shift);
    // A grey name stands on its own piece: on another it would hide that
    // one's lines and seem to name it. A line of another along one of its
    // own, as an edge straight behind its outline is, is its line too
    let on_others = |r: Rect, seen: &[Seen], id: &str| {
        let own = &seen
            .iter()
            .find(|(p, _, _)| p == id)
            .expect("a shown piece")
            .1;
        seen.iter()
            .filter(|(p, _, _)| p != id)
            .any(|(_, _, points)| {
                points
                    .iter()
                    .any(|&q| inside(q, r) && !own.iter().any(|&line| on_segment(q, line)))
            })
    };
    let name_left = |id: &String, left: &[(String, Rect)]| -> Option<Rect> {
        let taken: Vec<Rect> = std::iter::once(keep_out)
            .chain(left.iter().map(|(_, r)| *r))
            .collect();
        let r = named(
            &world,
            &iso,
            std::slice::from_ref(id),
            factor,
            offset,
            &taken,
            &[],
        )
        .pop()?
        .1;
        (!on_others(r, &iso_seen, id)).then_some(r)
    };
    let name_right = |id: &String, right: &[(String, Rect)]| -> Option<Rect> {
        let taken: Vec<Rect> = values
            .iter()
            .copied()
            .chain(right.iter().map(|(_, r)| *r))
            .collect();
        let r = named(
            &world,
            &view,
            std::slice::from_ref(id),
            scale,
            shift,
            &taken,
            &segments,
        )
        .pop()?
        .1;
        (!on_others(r, &dim_seen, id)).then_some(r)
    };
    let centre = |id: &str| {
        let (_, (low, high)) = world.iter().find(|(p, _)| p == id).expect("a shown piece");
        std::array::from_fn::<f64, 3, _>(|i| (low[i] + high[i]) / 2.0)
    };
    let mut both: Vec<Rect> = step
        .pieces
        .iter()
        .filter(|p| labels.iter().any(|(id, _)| id == *p))
        .filter_map(|p| {
            dimension_labels
                .iter()
                .find(|(id, _)| id == p)
                .map(|(_, r)| *r)
        })
        .collect();
    // A view from the side can be mirrored left to right; from above or below
    // the names tie it down whichever way they sit apart
    let across_only = step.view.0 != 2;
    let apart = |a: Rect, b: Rect| {
        let dx = ((a.0 + a.2) / 2.0 - (b.0 + b.2) / 2.0).abs();
        let dy = ((a.1 + a.3) / 2.0 - (b.1 + b.3) / 2.0).abs();
        (if across_only { dx } else { dx.max(dy) }) >= APART
    };
    let told = |both: &[Rect]| {
        both.iter()
            .enumerate()
            .any(|(i, a)| both[i + 1..].iter().any(|b| apart(*a, *b)))
    };
    let count = step.pieces.len() as f64;
    let middle: [f64; 3] =
        std::array::from_fn(|i| step.pieces.iter().map(|p| centre(p)[i]).sum::<f64>() / count);
    let partners: Vec<&String> = step
        .connections
        .iter()
        .flat_map(|(a, b)| [a, b])
        .filter(|p| !step.pieces.contains(p))
        .collect();
    let distance = |id: &str| {
        let c = centre(id);
        (0..3)
            .map(|i| (c[i] - middle[i]).powi(2))
            .sum::<f64>()
            .sqrt()
    };
    let mut earlier: Vec<&String> = step
        .shown
        .iter()
        .filter(|p| !step.pieces.contains(p))
        .collect();
    earlier.sort_by(|a, b| {
        (!partners.contains(a))
            .cmp(&!partners.contains(b))
            .then(distance(a).total_cmp(&distance(b)))
    });
    let mut references: Vec<String> = Vec::new();
    for id in earlier {
        if told(&both) {
            break;
        }
        let (Some(l), Some(r)) = (name_left(id, &labels), name_right(id, &dimension_labels)) else {
            continue;
        };
        if both.iter().all(|b| apart(r, *b)) {
            labels.push((id.clone(), l));
            dimension_labels.push((id.clone(), r));
            both.push(r);
            references.push(id.clone());
        }
    }
    if !told(&both) {
        // Names that cannot tell which way round it is only add to read
        labels.retain(|(id, _)| !references.contains(id));
        dimension_labels.retain(|(id, _)| !references.contains(id));
        references.clear();
    }

    // A white ground under each name keeps it readable over the lines
    for (_, r) in labels.iter().chain(&dimension_labels) {
        svg.fill_ink(
            &[(r.0, r.1), (r.2, r.1), (r.2, r.3), (r.0, r.3)],
            Ink::White,
        );
    }
    for (id, r) in labels.iter().chain(&dimension_labels) {
        let ink = if references.contains(id) {
            Ink::Grey
        } else {
            Ink::Black
        };
        svg.text_ink(id, ((r.0 + r.2) / 2.0, (r.1 + r.3) / 2.0), false, ink);
    }
    let title = heading(step);
    svg.text(
        &title,
        (
            MARGIN + text_size(&title).0 / 2.0,
            PAGE_HEIGHT - HEADING / 2.0,
        ),
        false,
    );
    for label in &drawn.labels {
        svg.text(&label.text, label.centre, label.vertical);
    }
    for &(tip, direction) in &drawn.arrows {
        svg.fill(&arrow_points(tip, direction));
    }
    // The arrow is grey: it orients, it is not built
    svg.fill_ink(&cue, Ink::Grey);
    StepSheet {
        heading: title,
        labels,
        dimension_labels,
        references,
        cue,
        iso_lines,
        new_hidden,
        notes: drawn.crowded,
        svg: svg.render(PAGE_HEIGHT),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use nichiyou_daiku_core::dsl::parse;
    use nichiyou_daiku_core::steps::plan_steps;

    const THREE: &str =
        "(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n(c:2x4 =400)\nb -[TF<0 BD<0]- c\n";

    fn read(path: &str) -> String {
        std::fs::read_to_string(format!("{}/../../{path}", env!("CARGO_MANIFEST_DIR"))).unwrap()
    }

    fn sheets(source: &str) -> Vec<StepSheet> {
        let assembly = Assembly::of(parse(source).unwrap()).unwrap();
        plan_steps(&assembly)
            .steps
            .iter()
            .map(|step| step_sheet(&assembly, step))
            .collect()
    }

    fn direction(cue: &[Point]) -> Point {
        let tail = ((cue[0].0 + cue[6].0) / 2.0, (cue[0].1 + cue[6].1) / 2.0);
        let (dx, dy) = (cue[3].0 - tail.0, cue[3].1 - tail.1);
        let length = (dx * dx + dy * dy).sqrt();
        (dx / length, dy / length)
    }

    #[test]
    fn steps_are_headed_as_the_steps_page_heads_them() {
        let assembly = Assembly::of(parse(THREE).unwrap()).unwrap();
        let plan = plan_steps(&assembly);
        assert_eq!(heading(&plan.steps[0]), "Step 1");
        assert_eq!(advice(&plan.steps[0]), SPLIT_ADVICE);
        assert_eq!(advice(&plan.steps[1]), ONE_PIECE_ADVICE);
    }

    #[test]
    fn the_arrow_points_the_way_the_dimension_view_looks() {
        let down = direction(&cue((2, 1)));
        assert!(down.0.abs() < 1e-9 && (down.1 + 1.0).abs() < 1e-9);
        // From -y, looking toward +y: as the isometric draws +y
        let toward = direction(&cue((1, -1)));
        let (x, y) = crate::views::isometric().project([0.0, 1.0, 0.0]);
        let length = (x * x + y * y).sqrt();
        assert!((toward.0 - x / length).abs() < 1e-9 && (toward.1 - y / length).abs() < 1e-9);
    }

    #[test]
    fn the_isometric_keeps_clear_of_the_arrow() {
        for sheet in sheets(&read("skills/design/examples/two-tier-shelf.nd")) {
            let xs: Vec<f64> = sheet.cue.iter().map(|p| p.0).collect();
            let ys: Vec<f64> = sheet.cue.iter().map(|p| p.1).collect();
            let (x0, x1) = (
                xs.iter().cloned().fold(f64::INFINITY, f64::min) - 6.0,
                xs.iter().cloned().fold(f64::NEG_INFINITY, f64::max) + 6.0,
            );
            let (y0, y1) = (
                ys.iter().cloned().fold(f64::INFINITY, f64::min) - 6.0,
                ys.iter().cloned().fold(f64::NEG_INFINITY, f64::max) + 6.0,
            );
            for &(a, b) in &sheet.iso_lines {
                for k in 0..=20 {
                    let t = f64::from(k) / 20.0;
                    let p = (a.0 + (b.0 - a.0) * t, a.1 + (b.1 - a.1) * t);
                    assert!(
                        !(x0 < p.0 && p.0 < x1 && y0 < p.1 && p.1 < y1),
                        "{}",
                        sheet.heading
                    );
                }
            }
        }
    }

    #[test]
    fn dashed_lines_only_in_the_dimension_view() {
        let all = sheets(&read("skills/design/examples/two-tier-shelf.nd"));
        assert!(all.iter().any(|sheet| !sheet.new_hidden.is_empty()));
        for sheet in &all {
            assert!(
                sheet
                    .new_hidden
                    .iter()
                    .all(|(a, b)| a.0 >= PAGE_WIDTH / 2.0 && b.0 >= PAGE_WIDTH / 2.0)
            );
        }
    }

    #[test]
    fn crowded_values_say_to_split_the_step() {
        // 39 slats 12.5mm apart up a 2m post, all in one step
        let mut source = String::from("(rail:2x4 =2000)\n");
        for i in 0..39 {
            source.push_str(&format!(
                "(s{i}:2x2 =300)\nrail -[RF<{} BT<0]- s{i}\n",
                f64::from(i) * 50.5
            ));
        }
        let names: Vec<String> = (0..39).map(|i| format!("s{i}")).collect();
        source.push_str(&format!(
            "steps {{\n  \"All\": rail, {}\n}}\n",
            names.join(", ")
        ));
        let sheet = &sheets(&source)[0];
        assert!(!sheet.notes.is_empty());
        assert!(sheet.notes[0].contains("in step 1") && sheet.notes[0].ends_with(SPLIT_ADVICE));
    }

    #[test]
    fn the_frame_is_named_without_grey_names() {
        // leg_1 and leg_3 sit apart in both halves: they tell left from right
        let frame = &sheets(&read("skills/design/examples/two-tier-shelf.nd"))[0];
        let names: Vec<&str> = frame
            .dimension_labels
            .iter()
            .map(|(id, _)| id.as_str())
            .collect();
        assert!(names.contains(&"leg_1") && names.contains(&"leg_3"));
        assert!(frame.references.is_empty());
    }

    #[test]
    fn names_are_this_steps_pieces_or_grey_references() {
        let assembly =
            Assembly::of(parse(&read("skills/design/examples/two-tier-shelf.nd")).unwrap())
                .unwrap();
        for step in &plan_steps(&assembly).steps {
            let sheet = step_sheet(&assembly, step);
            for (id, _) in sheet.labels.iter().chain(&sheet.dimension_labels) {
                assert!(
                    step.pieces.contains(id) || sheet.references.contains(id),
                    "{}: {id}",
                    sheet.heading
                );
            }
        }
    }

    #[test]
    fn a_reference_tells_left_from_right_when_the_step_cannot() {
        // Step 4 of the table adds leg_3 at the back alone
        let table = sheets(&read("examples/nd_files/simple_table_compact.nd"));
        let step = &table[3];
        assert_eq!(step.references.len(), 1);
        let reference = &step.references[0];
        assert!(step.labels.iter().any(|(id, _)| id == reference));
        assert!(step.dimension_labels.iter().any(|(id, _)| id == reference));
    }

    #[test]
    fn grey_names_sit_apart_and_on_their_own_piece() {
        // The side table's joining aprons hide behind the legs seen from the side
        let join = &sheets(&read("skills/design/examples/side-table.nd"))[2];
        assert_eq!(join.references.len(), 2);
        let centre = |id: &str| {
            let (_, r) = join.dimension_labels.iter().find(|(p, _)| p == id).unwrap();
            (r.0 + r.2) / 2.0
        };
        assert!((centre(&join.references[0]) - centre(&join.references[1])).abs() >= 10.0);
    }
}
