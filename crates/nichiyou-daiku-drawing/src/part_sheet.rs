//! Part drawings (parts.py): one sheet per group of pieces made the same
//! way, an isometric view with the drilled faces lettered and the
//! reference end marked, then each drilled face seen from outside with its
//! holes dimensioned from the reference end.

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_core::dimensioning::{Side, chain_from_stops};
use nichiyou_daiku_core::geometry::Face;
use nichiyou_daiku_core::parts::{
    PartGroup, edge_neighbours, face_letters, face_point, face_size, part_title, view_direction,
};

use crate::chain::{Drawn, Placement, arrow_points, dimension_levels, draw_chain};
use crate::solid::{Projection, board_lines};
use crate::svg::{Point, Stroke, Svg};
use crate::text::{line_height, text_size};

pub const PAGE_WIDTH: f64 = 280.0;
const MARGIN: f64 = 6.0;
const ISO_WIDTH: f64 = 70.0;
const ISO_HEIGHT: f64 = 60.0;
/// A face's letter and the letters of its neighbours
const LETTER_COLUMN: f64 = 22.0;
/// A thin face is drawn taller so its values fit
const MIN_FACE_HEIGHT: f64 = 22.0;
const MAX_SCALE: f64 = 0.8;
const FACE_GAP: f64 = 10.0;
/// Length of the reference end's triangle
const MARK: f64 = 3.5;
const ADVICE: &str = "The report's Pilot Holes table lists the same holes";

pub type Rect = (f64, f64, f64, f64);

pub struct PartSheet {
    pub title_lines: Vec<String>,
    pub letters: Vec<(Face, char)>,
    /// Each drilled face's outline
    pub faces: Vec<(Face, Rect)>,
    /// The reference end's triangles
    pub marks: Vec<[Point; 3]>,
    pub crowded: Vec<String>,
    pub width: f64,
    pub height: f64,
    pub svg: String,
}

struct Page {
    svg: Svg,
    marks: Vec<[Point; 3]>,
}

impl Page {
    fn text(&mut self, content: &str, x: f64, y: f64) {
        self.svg.text(content, (x, y), false);
    }

    fn letter(&mut self, content: char, x: f64, y: f64, hidden: bool) {
        let radius = line_height() * 0.9;
        let ring: Vec<Point> = (0..=32)
            .map(|k| {
                let a = std::f64::consts::TAU * f64::from(k) / 32.0;
                (x + radius * a.cos(), y + radius * a.sin())
            })
            .collect();
        self.svg.polyline(
            &ring,
            false,
            if hidden { Stroke::Hidden } else { Stroke::Thin },
        );
        self.text(&content.to_string(), x, y);
    }

    fn triangle(&mut self, tip: Point, direction: Point) {
        let length = (direction.0 * direction.0 + direction.1 * direction.1).sqrt();
        let d = (direction.0 / length, direction.1 / length);
        let side = (-d.1 * MARK / 2.0, d.0 * MARK / 2.0);
        let back = (tip.0 - d.0 * MARK, tip.1 - d.1 * MARK);
        let corners = [
            tip,
            (back.0 + side.0, back.1 + side.1),
            (back.0 - side.0, back.1 - side.1),
        ];
        self.marks.push(corners);
        self.svg.fill(&corners);
    }
}

fn letter_of(letters: &[(Face, char)], face: Face) -> Option<char> {
    letters.iter().find(|(f, _)| *f == face).map(|&(_, l)| l)
}

/// The title in lines as wide as the page allows, broken after a comma or
/// between its fields.
pub fn title_lines(title: &str) -> Vec<String> {
    let mut words = vec![String::new()];
    for c in title.chars() {
        let word = words.last_mut().expect("a word");
        word.push(c);
        if word.ends_with(", ") || word.ends_with("   ") {
            words.push(String::new());
        }
    }
    let mut lines = vec![String::new()];
    for word in words.into_iter().filter(|w| !w.is_empty()) {
        let last = lines.last_mut().expect("a line");
        let wider = text_size(format!("{last}{word}").trim_end()).0 > PAGE_WIDTH - 2.0 * MARGIN;
        if !last.is_empty() && wider {
            lines.push(word);
        } else {
            last.push_str(&word);
        }
    }
    lines
        .into_iter()
        .map(|line| line.trim_end().to_string())
        .collect()
}

/// Where the reference end's triangle goes on a face's left edge: the
/// middle, unless an extension line is there; then the widest gap.
pub fn mark_height(stops: &[f64], bottom: f64, top: f64) -> f64 {
    let middle = (bottom + top) / 2.0;
    if stops.iter().all(|stop| (middle - stop).abs() > MARK) {
        return middle;
    }
    let mut ordered = stops.to_vec();
    ordered.sort_by(f64::total_cmp);
    let mut best = (ordered[0], ordered[1]);
    for pair in ordered.windows(2) {
        if pair[1] - pair[0] > best.1 - best.0 {
            best = (pair[0], pair[1]);
        }
    }
    (best.0 + best.1) / 2.0
}

fn face_view(
    group: &PartGroup,
    face: Face,
    letters: &[(Face, char)],
    page: &mut Page,
    drawn: &mut Drawn,
    bottom: f64,
) -> Rect {
    let (width, height) = face_size(face, group.size);
    let left = MARGIN + LETTER_COLUMN + dimension_levels(Side::Left).depth;
    let along = ((PAGE_WIDTH - MARGIN - left) / width).min(MAX_SCALE);
    let across = along.max(MIN_FACE_HEIGHT / height);
    let rect = (left, bottom, left + width * along, bottom + height * across);
    page.svg.polyline(
        &[
            (rect.0, rect.1),
            (rect.2, rect.1),
            (rect.2, rect.3),
            (rect.0, rect.3),
        ],
        true,
        Stroke::Outline,
    );
    let (mut us, mut vs) = (vec![0.0, width], vec![0.0, height]);
    for hole in group.holes.iter().filter(|h| h.face == face) {
        let (u, v) = face_point(face, hole.point, group.size);
        us.push(u);
        vs.push(v);
        let radius = (hole.diameter / 2.0 * along.min(across)).max(1.0);
        let (cx, cy) = (left + u * along, bottom + v * across);
        let ring: Vec<Point> = (0..=32)
            .map(|k| {
                let a = std::f64::consts::TAU * f64::from(k) / 32.0;
                (cx + radius * a.cos(), cy + radius * a.sin())
            })
            .collect();
        page.svg.polyline(&ring, false, Stroke::Outline);
    }
    let letter = letter_of(letters, face).expect("a drilled face has a letter");
    let piece = &group.pieces[0];
    let face_name = face.as_str();
    draw_chain(
        &chain_from_stops(0, Side::Below, &us),
        &Placement {
            side: Side::Below,
            edge: rect.1,
            origin: left,
            scale: along,
        },
        drawn,
        &format!("horizontal dimension values in face {letter} ({face_name}) of {piece}"),
        ADVICE,
    );
    draw_chain(
        &chain_from_stops(2, Side::Left, &vs),
        &Placement {
            side: Side::Left,
            edge: rect.0,
            origin: bottom,
            scale: across,
        },
        drawn,
        &format!("vertical dimension values in face {letter} ({face_name}) of {piece}"),
        ADVICE,
    );
    let column = MARGIN + LETTER_COLUMN / 2.0;
    let middle = (rect.1 + rect.3) / 2.0;
    page.letter(letter, column, middle, false);
    let neighbours = edge_neighbours(face);
    for (next, y) in [(neighbours.top, rect.3), (neighbours.bottom, rect.1)] {
        if let Some(l) = letter_of(letters, next) {
            page.text(&l.to_string(), column, y);
        }
    }
    if matches!(face, Face::Top | Face::Down) {
        // An end turns freely about the length, so its sides are named too
        let offset = line_height() * 2.0;
        for (next, x) in [
            (neighbours.left, column - offset),
            (neighbours.right, column + offset),
        ] {
            if let Some(l) = letter_of(letters, next) {
                page.text(&l.to_string(), x, middle);
            }
        }
    } else {
        let stops: Vec<f64> = vs.iter().map(|v| bottom + v * across).collect();
        page.triangle(
            (left - 0.6, mark_height(&stops, rect.1, rect.3)),
            (1.0, 0.0),
        );
    }
    rect
}

fn isometric(group: &PartGroup, letters: &[(Face, char)], page: &mut Page, top: f64) {
    let extent = group.size;
    let centre = extent.map(|e| e / 2.0);
    let faces: Vec<Face> = letters.iter().map(|&(f, _)| f).collect();
    let direction = view_direction(&faces).map(f64::from);
    let view = Projection::new(direction, centre);
    let lines = board_lines(extent, &group.holes, &view);
    let all: Vec<Point> = lines
        .visible
        .iter()
        .chain(&lines.hidden)
        .flatten()
        .copied()
        .collect();
    let (min_x, max_x) = all
        .iter()
        .fold((f64::INFINITY, f64::NEG_INFINITY), |(a, b), p| {
            (a.min(p.0), b.max(p.0))
        });
    let (min_y, max_y) = all
        .iter()
        .fold((f64::INFINITY, f64::NEG_INFINITY), |(a, b), p| {
            (a.min(p.1), b.max(p.1))
        });
    let factor = 0.85 * (ISO_WIDTH / (max_x - min_x)).min(ISO_HEIGHT / (max_y - min_y));
    let origin = (
        MARGIN + ISO_WIDTH / 2.0 - (min_x + max_x) / 2.0 * factor,
        top - ISO_HEIGHT / 2.0 - (min_y + max_y) / 2.0 * factor,
    );
    let place = |p: Point| (origin.0 + p.0 * factor, origin.1 + p.1 * factor);
    for (polylines, stroke) in [
        (&lines.visible, Stroke::Outline),
        (&lines.hidden, Stroke::Hidden),
    ] {
        for polyline in polylines {
            let points: Vec<Point> = polyline.iter().map(|&p| place(p)).collect();
            page.svg.polyline(&points, false, stroke);
        }
    }
    let on_page = |point: [f64; 3]| place(view.project(point));
    let column = MARGIN + ISO_WIDTH + 8.0;
    let mut targets: Vec<(Face, char, Point)> = letters
        .iter()
        .map(|&(face, l)| {
            let n = face.normal().map(f64::from);
            (
                face,
                l,
                on_page(std::array::from_fn(|i| centre[i] + n[i] * extent[i] / 2.0)),
            )
        })
        .collect();
    targets.sort_by(|a, b| b.2.1.total_cmp(&a.2.1));
    let step = line_height() * 2.6;
    let first = top - ISO_HEIGHT / 2.0 + step * (targets.len() as f64 - 1.0) / 2.0;
    for (i, (face, l, point)) in targets.iter().enumerate() {
        let y = first - i as f64 * step;
        let hidden = !view.faces_viewer(face.normal().map(f64::from));
        page.letter(*l, column, y, hidden);
        let stroke = if hidden { Stroke::Hidden } else { Stroke::Thin };
        page.svg
            .line((column - line_height() * 0.9, y), *point, stroke);
    }
    // The reference (down) end: a triangle pointing at it from past the
    // whole piece, so that it never sits on the outline
    let end = on_page([centre[0], centre[1], 0.0]);
    let beyond = on_page([centre[0], centre[1], -60.0 / factor]);
    let length = ((end.0 - beyond.0).powi(2) + (end.1 - beyond.1).powi(2)).sqrt();
    let toward_end = ((end.0 - beyond.0) / length, (end.1 - beyond.1) / length);
    let away = (-toward_end.0, -toward_end.1);
    let mut reach = f64::NEG_INFINITY;
    for x in [0.0, extent[0]] {
        for y in [0.0, extent[1]] {
            for z in [0.0, extent[2]] {
                let p = on_page([x, y, z]);
                reach = reach.max((p.0 - end.0) * away.0 + (p.1 - end.1) * away.1);
            }
        }
    }
    let tip = (
        end.0 + away.0 * (reach + 1.0),
        end.1 + away.1 * (reach + 1.0),
    );
    page.triangle(tip, toward_end);
}

/// The drawing of one part: the title, the isometric view and every drilled
/// face, top to bottom.
pub fn part_sheet(assembly: &Assembly, group: &PartGroup) -> PartSheet {
    let letters = face_letters(&group.holes, group.size);
    let drilled: Vec<Face> = letters
        .iter()
        .map(|&(f, _)| f)
        .filter(|f| group.holes.iter().any(|h| h.face == *f))
        .collect();
    let mut page = Page {
        svg: Svg::new(PAGE_WIDTH),
        marks: Vec::new(),
    };
    let mut drawn = Drawn::default();
    let below = dimension_levels(Side::Below).depth;
    let mut y = MARGIN + below;
    let mut faces = Vec::new();
    for &face in drilled.iter().rev() {
        let rect = face_view(group, face, &letters, &mut page, &mut drawn, y);
        faces.push((face, rect));
        y = rect.3 + line_height() + FACE_GAP + below;
    }
    faces.reverse();
    let top = y - below + ISO_HEIGHT;
    isometric(group, &letters, &mut page, top);
    let lines = title_lines(&part_title(&assembly.model, group));
    let spacing = line_height() * 1.6;
    for (i, line) in lines.iter().rev().enumerate() {
        let width = text_size(line).0;
        page.text(line, MARGIN + width / 2.0, top + 8.0 + i as f64 * spacing);
    }
    let height = top + 14.0 + (lines.len() as f64 - 1.0) * spacing;
    page.svg.polyline(
        &[
            (0.0, 0.0),
            (PAGE_WIDTH, 0.0),
            (PAGE_WIDTH, height),
            (0.0, height),
        ],
        true,
        Stroke::Thin,
    );
    for &(a, b) in &drawn.lines {
        page.svg.line(a, b, Stroke::Thin);
    }
    for label in &drawn.labels {
        page.svg.text(&label.text, label.centre, label.vertical);
    }
    for &(tip, direction) in &drawn.arrows {
        page.svg.fill(&arrow_points(tip, direction));
    }
    PartSheet {
        title_lines: lines,
        letters,
        faces,
        marks: page.marks,
        crowded: drawn.crowded,
        width: PAGE_WIDTH,
        height,
        svg: page.svg.render(height),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use nichiyou_daiku_core::dsl::parse;
    use nichiyou_daiku_core::parts::part_groups;

    const SHELF: &str = "(left_side:2x4 =800)\n(right_side:2x4 =800)\n(shelf:2x4 =600)\n\
        left_side -[BL<300 DL<0 D(:8x30)]- shelf\nright_side -[FL<300 TL<0 D(:8x30)]- shelf\n";

    fn sheet() -> PartSheet {
        let assembly = Assembly::of(parse(SHELF).unwrap()).unwrap();
        let groups = part_groups(&assembly);
        part_sheet(&assembly, &groups[0])
    }

    #[test]
    fn a_long_face_fills_the_page_width_and_a_wide_face_keeps_the_scale() {
        let sheet = sheet();
        assert_eq!(sheet.letters, [(Face::Back, 'A')]);
        let (face, rect) = sheet.faces[0];
        assert_eq!(face, Face::Back);
        assert!((rect.0 - 53.0).abs() < 1e-9 && (rect.2 - 274.0).abs() < 1e-9);
        assert!((rect.3 - rect.1 - 89.0 * 221.0 / 800.0).abs() < 1e-9);
        assert_eq!(
            sheet.title_lines,
            ["left_side, right_side ×2   2x4   800   φ8 ↧15 ×2"]
        );
        assert!(sheet.svg.starts_with("<svg"));
        assert!(
            sheet
                .svg
                .contains("left_side, right_side ×2   2x4   800   φ8 ↧15 ×2")
        );
        assert_eq!(sheet.width, 280.0);
    }

    #[test]
    fn a_thin_face_is_drawn_taller_so_its_values_fit() {
        // 38 high at a scale of 221/800 would be 10.5mm: drawn 22mm
        let source = "(a:2x4 =800)\n(b:2x4 =400)\nb -[DF<0 RF<300 S(Slim:3.8x65)]- a\n";
        let assembly = Assembly::of(parse(source).unwrap()).unwrap();
        let groups = part_groups(&assembly);
        let sheet = part_sheet(&assembly, &groups[0]);
        let (_, rect) = sheet
            .faces
            .iter()
            .find(|(f, _)| *f == Face::Right || *f == Face::Left)
            .copied()
            .unwrap();
        assert!((rect.3 - rect.1 - 22.0).abs() < 1e-9);
    }

    #[test]
    fn the_reference_mark_keeps_off_the_extension_lines() {
        assert_eq!(mark_height(&[0.0, 24.0], 0.0, 24.0), 12.0);
        assert_eq!(mark_height(&[0.0, 12.0, 24.0], 0.0, 24.0), 6.0);
    }

    #[test]
    fn long_titles_break_after_a_comma_or_between_fields() {
        let names: Vec<String> = (1..=8)
            .map(|i| format!("a_rather_long_piece_name_{i}"))
            .collect();
        let title = format!("{} ×8   2x4   750   φ2.5 ×12", names.join(", "));
        let lines = title_lines(&title);
        assert!(lines.len() >= 2);
        assert!(
            lines
                .iter()
                .all(|line| crate::text::text_size(line).0 <= 268.0)
        );
        // Only the spaces at a break go
        assert_eq!(lines.concat().replace(' ', ""), title.replace(' ', ""));
    }

    #[test]
    fn a_part_without_holes_has_no_drawing() {
        let error =
            crate::part_drawing("(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n", 0).unwrap_err();
        assert_eq!(
            error,
            "a, b ×2 has no holes, so it has no drawing: it is only cut to length"
        );
        assert!(
            crate::part_drawing(SHELF, 9)
                .unwrap_err()
                .starts_with("There is no part 9")
        );
        assert!(
            crate::part_drawing("(a:2x4 =400", 0)
                .unwrap_err()
                .starts_with("The design does not read")
        );
        assert!(crate::part_drawing(SHELF, 0).unwrap().starts_with("<svg"));
    }
}
