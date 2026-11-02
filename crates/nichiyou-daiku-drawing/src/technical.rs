//! The technical drawing (drawing.py: technical_drawing): the top, front
//! and right side views at one scale with hidden lines and dimensions, an
//! isometric view, and a title block, on an A4 to A1 page. Page mm, y up.

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_core::dimensioning::{Side, drawing_chains};
use nichiyou_daiku_core::parts::piece_holes;
use nichiyou_daiku_core::pyfmt::format_mm;

use crate::chain::{Drawn, Placement, arrow_points, dimension_levels, draw_chain};
use crate::hidden::{board_body, sort_lines};
use crate::solid::Projection;
use crate::svg::{Point, Stroke, Svg};
use crate::text::{line_height, text_size};
use crate::views::{axis_view, isometric};

/// Frame to the drawing
const INSET: f64 = 4.0;
/// Between views
const SPACE: f64 = 12.0;
/// Share of its space the isometric view takes
const ISO_FILL: f64 = 0.9;
/// The title block is sized before the scale is known: room for any scale
const WIDEST_SCALE: &str = "1:999.9";
const AXES: [&str; 3] = ["x", "y", "z"];
const VIEW_NAMES: [(&str, &str); 3] = [
    ("from +z", "top"),
    ("from +y", "front"),
    ("from -x", "right side"),
];

/// The title block is at least this wide, so it reads as one
const TITLE_MIN_WIDTH: f64 = 80.0;
/// Inside the title block's box, around its rows
const TITLE_PAD: f64 = 3.0;
const COLUMN_GAP: f64 = 2.5;
/// DejaVu Sans Bold runs this much wider than the regular face at most
const BOLD_WIDTH: f64 = 1.2;
const LABELS: [&str; 6] = [
    "Title:",
    "Scale:",
    "Units:",
    "Date:",
    "Drawing No.:",
    "Designed by:",
];

pub type Rect = (f64, f64, f64, f64);

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Page {
    A4,
    A3,
    A2,
    A1,
}

impl Page {
    pub const ALL: [Page; 4] = [Page::A4, Page::A3, Page::A2, Page::A1];

    /// The page of that name, in any case.
    pub fn named(name: &str) -> Option<Page> {
        Page::ALL
            .into_iter()
            .find(|p| p.name().eq_ignore_ascii_case(name))
    }

    pub fn name(self) -> &'static str {
        match self {
            Page::A4 => "A4",
            Page::A3 => "A3",
            Page::A2 => "A2",
            Page::A1 => "A1",
        }
    }

    /// Width and height in mm, landscape.
    pub fn size(self) -> (f64, f64) {
        match self {
            Page::A4 => (297.0, 210.0),
            Page::A3 => (420.0, 297.0),
            Page::A2 => (594.0, 420.0),
            Page::A1 => (841.0, 594.0),
        }
    }

    /// JIS Z 8311's margin to the frame
    fn margin(self) -> f64 {
        match self {
            Page::A4 | Page::A3 => 10.0,
            Page::A2 | Page::A1 => 20.0,
        }
    }

    fn larger(self) -> Option<Page> {
        let at = Page::ALL.iter().position(|&p| p == self).expect("a page");
        Page::ALL.get(at + 1).copied()
    }
}

/// What the title block says besides the scale.
pub struct Titles<'a> {
    pub title: &'a str,
    pub drawing_number: &'a str,
    pub designed_by: &'a str,
    pub date: &'a str,
}

pub fn frame(page: Page) -> Rect {
    let (width, height) = page.size();
    let m = page.margin();
    (m, m, width - m, height - m)
}

fn label_width() -> f64 {
    LABELS
        .iter()
        .map(|l| text_size(l).0 * BOLD_WIDTH)
        .fold(0.0, f64::max)
}

/// Room for a value: the title block takes half the frame's width at most.
fn value_room(frame: Rect) -> f64 {
    (frame.2 - frame.0) / 2.0 - 2.0 * TITLE_PAD - label_width() - COLUMN_GAP
}

fn spacing() -> f64 {
    line_height() * 1.6
}

/// The value in lines no wider than `width`, broken between characters:
/// titles and names have no spaces to break at.
fn broken(value: &str, width: f64) -> Vec<String> {
    let mut lines = vec![String::new()];
    for c in value.chars() {
        let last = lines.last_mut().expect("a line");
        let longer = format!("{last}{c}");
        if !last.is_empty() && text_size(&longer).0 > width {
            lines.push(c.to_string());
        } else {
            *last = longer;
        }
    }
    lines
}

/// The title block's rows: an attribute (empty on a continued line) and its
/// value, values broken to `width`.
pub fn title_rows(titles: &Titles, scale: &str, width: f64) -> Vec<(&'static str, String)> {
    let values = [
        titles.title.to_string(),
        scale.to_string(),
        "mm".to_string(),
        titles.date.to_string(),
        titles.drawing_number.to_string(),
        titles.designed_by.to_string(),
    ];
    LABELS
        .into_iter()
        .zip(values)
        .flat_map(|(label, value)| {
            broken(&value, width)
                .into_iter()
                .enumerate()
                .map(move |(i, line)| (if i == 0 { label } else { "" }, line))
        })
        .collect()
}

/// The title block in the frame's lower right corner, as big as its rows.
fn title_block(frame: Rect, rows: &[(&'static str, String)]) -> Rect {
    let values = rows.iter().map(|(_, v)| text_size(v).0).fold(0.0, f64::max);
    let width = (2.0 * TITLE_PAD + label_width() + COLUMN_GAP + values).max(TITLE_MIN_WIDTH);
    let height = 2.0 * TITLE_PAD + rows.len() as f64 * spacing();
    (frame.2 - width, frame.1, frame.2, frame.1 + height)
}

/// How to make room for values that do not fit (drawing.py: _crowded_advice).
fn advice(page: Page) -> String {
    match page.larger() {
        Some(larger) => format!(
            "Use a larger page (drawing --page-size {}) or leave the dimensions out (drawing --no-dimensions)",
            larger.name()
        ),
        None => "Leave the dimensions out (drawing --no-dimensions)".to_string(),
    }
}

type Segment = (Point, Point);

/// A view's lines placed on the page.
pub struct PlacedView {
    pub caption: &'static str,
    pub scale: f64,
    pub offset: Point,
    pub rect: Rect,
    pub visible: Vec<Segment>,
    /// Empty for the isometric, which shows only what is seen
    pub hidden: Vec<Segment>,
}

pub struct TechnicalSheet {
    pub frame: Rect,
    pub title_block: Rect,
    /// The orthographic views are drawn at 1:denominator
    pub denominator: f64,
    /// From +z, +y, -x, then the isometric
    pub views: Vec<PlacedView>,
    pub title_rows: Vec<(&'static str, String)>,
    pub dimensions: Drawn,
    pub svg: String,
}

struct Projected {
    caption: &'static str,
    visible: Vec<Segment>,
    hidden: Vec<Segment>,
    bounds: Rect,
}

fn projection(caption: &str) -> Projection {
    match caption {
        "from +z" => axis_view(2, 1),
        "from +y" => axis_view(1, 1),
        "from -x" => axis_view(0, -1),
        _ => isometric(),
    }
}

fn project(assembly: &Assembly, caption: &'static str) -> Projected {
    let view = projection(caption);
    let bodies: Vec<_> = assembly
        .model
        .pieces
        .iter()
        .map(|piece| {
            board_body(
                piece.shape(),
                &piece_holes(assembly, &piece.id),
                assembly.placement.pose(&piece.id),
                &view,
            )
        })
        .collect();
    let (mut visible, mut hidden) = (Vec::new(), Vec::new());
    for sorted in sort_lines(&bodies, &view) {
        visible.extend(sorted.visible);
        hidden.extend(sorted.hidden);
    }
    let bounds = visible
        .iter()
        .chain(&hidden)
        .flat_map(|&(a, b)| [a, b])
        .fold(
            (
                f64::INFINITY,
                f64::INFINITY,
                f64::NEG_INFINITY,
                f64::NEG_INFINITY,
            ),
            |r, p| (r.0.min(p.0), r.1.min(p.1), r.2.max(p.0), r.3.max(p.1)),
        );
    Projected {
        caption,
        visible,
        hidden,
        bounds,
    }
}

fn placed(projected: Projected, scale: f64, offset: Point, rect: Rect, hidden: bool) -> PlacedView {
    let at = |p: Point| (offset.0 + p.0 * scale, offset.1 + p.1 * scale);
    let moved = |lines: &[Segment]| {
        lines
            .iter()
            .map(|&(a, b)| (at(a), at(b)))
            .collect::<Vec<_>>()
    };
    PlacedView {
        caption: projected.caption,
        scale,
        offset,
        rect,
        visible: moved(&projected.visible),
        hidden: if hidden {
            moved(&projected.hidden)
        } else {
            Vec::new()
        },
    }
}

/// The scale denominator and the placed views (drawing.py: _layout): the
/// orthographic views at one scale left of the title block, the isometric
/// above it at its own.
fn layout(assembly: &Assembly, frame: Rect, block: Rect, bands: bool) -> (f64, Vec<PlacedView>) {
    let top = project(assembly, "from +z");
    let front = project(assembly, "from +y");
    let side = project(assembly, "from -x");
    let iso = project(assembly, "from -x +y +z");
    let size = |b: Rect| (b.2 - b.0, b.3 - b.1);
    let ((top_w, top_h), (front_w, front_h), (side_w, side_h)) =
        (size(top.bounds), size(front.bounds), size(side.bounds));
    let left_band = if bands {
        dimension_levels(Side::Left).depth
    } else {
        0.0
    };
    let bottom_band = if bands {
        dimension_levels(Side::Below).depth
    } else {
        0.0
    };
    let (left, bottom, top_edge) = (frame.0 + INSET, frame.1 + INSET, frame.3 - INSET);
    let right = block.0 - INSET;
    let column = top_w.max(front_w);
    let row = front_h.max(side_h);
    let largest = ((right - left - left_band - SPACE) / (column + side_w))
        .min((top_edge - bottom - 2.0 * bottom_band - SPACE) / (top_h + row));
    // Round the denominator up so the scale written is the scale drawn
    let denominator = ((10.0 / largest - 1e-9).ceil() / 10.0).max(1.0);
    let factor = 1.0 / denominator;
    let x0 = left + left_band;
    let lower = top_edge - top_h * factor - bottom_band - SPACE;
    let mut views = Vec::new();
    for (projected, (x, y)) in [
        (top, (x0, top_edge)),
        (front, (x0, lower)),
        (side, (x0 + column * factor + SPACE, lower)),
    ] {
        let (b, (w, h)) = (projected.bounds, size(projected.bounds));
        let offset = (x - b.0 * factor, y - b.3 * factor);
        let rect = (x, y - h * factor, x + w * factor, y);
        views.push(placed(projected, factor, offset, rect, true));
    }
    let space = (
        views[2].rect.2 + SPACE,
        block.3 + INSET,
        frame.2 - INSET,
        top_edge,
    );
    let (b, (w, h)) = (iso.bounds, size(iso.bounds));
    let k = ISO_FILL * ((space.2 - space.0) / w).min((space.3 - space.1) / h);
    let (cx, cy) = ((space.0 + space.2) / 2.0, (space.1 + space.3) / 2.0);
    let offset = (cx - (b.0 + b.2) / 2.0 * k, cy - (b.1 + b.3) / 2.0 * k);
    let rect = (
        cx - w * k / 2.0,
        cy - h * k / 2.0,
        cx + w * k / 2.0,
        cy + h * k / 2.0,
    );
    // Dashed back edges only crowd the isometric
    views.push(placed(iso, k, offset, rect, false));
    (denominator, views)
}

fn corners(r: Rect) -> [Point; 4] {
    [(r.0, r.1), (r.2, r.1), (r.2, r.3), (r.0, r.3)]
}

/// The drawing of `assembly` on `page`; `dimensions` false leaves them out.
pub fn technical_drawing(
    assembly: &Assembly,
    page: Page,
    titles: &Titles,
    dimensions: bool,
) -> TechnicalSheet {
    let frame = frame(page);
    let room = value_room(frame);
    let block = title_block(frame, &title_rows(titles, WIDEST_SCALE, room));
    let chains = if dimensions {
        drawing_chains(assembly)
    } else {
        Vec::new()
    };
    let (denominator, views) = layout(assembly, frame, block, !chains.is_empty());
    let rows = title_rows(titles, &format!("1:{}", format_mm(denominator)), room);
    let mut drawn = Drawn::default();
    for (caption, chain) in &chains {
        let view = views
            .iter()
            .find(|v| v.caption == *caption)
            .expect("chains go beside the orthographic views");
        let mut unit = [0.0; 3];
        unit[chain.axis] = 1.0;
        let (ux, uy) = projection(caption).project(unit);
        let at = if chain.side == Side::Below {
            Placement {
                side: Side::Below,
                edge: view.rect.1,
                origin: view.offset.0,
                scale: ux * view.scale,
            }
        } else {
            Placement {
                side: Side::Left,
                edge: view.rect.0,
                origin: view.offset.1,
                scale: uy * view.scale,
            }
        };
        let name = VIEW_NAMES
            .iter()
            .find(|(c, _)| c == caption)
            .expect("a dimensioned view")
            .1;
        let values = format!(
            "dimension values along {} in the {name} view",
            AXES[chain.axis]
        );
        draw_chain(chain, &at, &mut drawn, &values, &advice(page));
    }
    let (width, height) = page.size();
    let mut svg = Svg::new(width);
    svg.polyline(&corners(frame), true, Stroke::Frame);
    svg.polyline(&corners(block), true, Stroke::Outline);
    let value_x = block.0 + TITLE_PAD + label_width() + COLUMN_GAP;
    for (i, (label, value)) in rows.iter().enumerate() {
        let y = block.3 - TITLE_PAD - spacing() * (i as f64 + 0.5);
        if !label.is_empty() {
            svg.text_bold(label, (block.0 + TITLE_PAD, y));
        }
        svg.text(value, (value_x + text_size(value).0 / 2.0, y), false);
    }
    for view in &views {
        for &(a, b) in &view.visible {
            svg.line(a, b, Stroke::Outline);
        }
        for &(a, b) in &view.hidden {
            svg.line(a, b, Stroke::Hidden);
        }
    }
    for &(a, b) in &drawn.lines {
        svg.line(a, b, Stroke::Thin);
    }
    for &(tip, direction) in &drawn.arrows {
        svg.fill(&arrow_points(tip, direction));
    }
    for label in &drawn.labels {
        svg.text(&label.text, label.centre, label.vertical);
    }
    TechnicalSheet {
        frame,
        title_block: block,
        denominator,
        views,
        title_rows: rows,
        dimensions: drawn,
        svg: svg.render(height),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn titles(title: &str) -> Titles<'_> {
        Titles {
            title,
            drawing_number: "ND-1",
            designed_by: "nichiyou-daiku",
            date: "2026-11-02",
        }
    }

    #[test]
    fn frames_keep_the_jis_margins() {
        assert_eq!(frame(Page::A3), (10.0, 10.0, 410.0, 287.0));
        assert_eq!(frame(Page::A4), (10.0, 10.0, 287.0, 200.0));
        assert_eq!(frame(Page::A1), (20.0, 20.0, 821.0, 574.0));
    }

    #[test]
    fn pages_are_named_in_any_case() {
        assert_eq!(Page::named("a2"), Some(Page::A2));
        assert_eq!(Page::named("A3").map(Page::size), Some((420.0, 297.0)));
        assert_eq!(Page::named("A5"), None);
    }

    #[test]
    fn the_title_block_lists_attributes_and_values() {
        let rows = title_rows(&titles("file-wagon"), "1:5.5", 100.0);
        let want: Vec<(&str, String)> = vec![
            ("Title:", "file-wagon".into()),
            ("Scale:", "1:5.5".into()),
            ("Units:", "mm".into()),
            ("Date:", "2026-11-02".into()),
            ("Drawing No.:", "ND-1".into()),
            ("Designed by:", "nichiyou-daiku".into()),
        ];
        assert_eq!(rows, want);
        let block = title_block(frame(Page::A3), &rows);
        // In the frame's lower right corner
        assert_eq!((block.2, block.1), (410.0, 10.0));
        assert!(block.2 - block.0 >= 80.0);
    }

    #[test]
    fn a_long_title_wraps_within_half_the_frame() {
        let long = "a_design_with_a_very_long_name_".repeat(8);
        let page = frame(Page::A4);
        let rows = title_rows(&titles(&long), "1:5.5", value_room(page));
        assert!(rows.len() > 6);
        assert_eq!(rows[1].0, "");
        let title: String = rows
            .iter()
            .take_while(|(label, _)| *label != "Scale:")
            .map(|(_, value)| value.as_str())
            .collect();
        assert_eq!(title, long);
        let block = title_block(page, &rows);
        assert!(block.2 - block.0 <= (page.2 - page.0) / 2.0 + 1e-9);
    }

    #[test]
    fn crowded_values_are_told_how_to_make_room() {
        assert_eq!(
            advice(Page::A3),
            "Use a larger page (drawing --page-size A2) or leave the dimensions out (drawing --no-dimensions)"
        );
        assert_eq!(
            advice(Page::A1),
            "Leave the dimensions out (drawing --no-dimensions)"
        );
    }
}
