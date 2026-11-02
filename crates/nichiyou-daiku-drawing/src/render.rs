//! The check image (shell/render.py: render_sheet): four views of the model
//! on one square sheet, with piece labels, for an agent or a person to look
//! at. Sizes are in px, y up until the SVG is written.

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_core::parts::piece_holes;
use nichiyou_daiku_core::placement::{Bounds, overall_bounds};
use nichiyou_daiku_core::pyfmt::format_mm;

use crate::hidden::{board_body, sort_lines};
use crate::labels::blocks;
use crate::solid::Projection;
use crate::svg::Point;
use crate::views::{axis_view, isometric};

/// Share of a cell's drawing area the largest view takes
const VIEW_FILL: f64 = 0.9;
/// Margin and caption band, as a share of the sheet
const MARGIN: f64 = 0.04;
/// Lines kept for the note: the title and size, then two of unlabelled pieces
const NOTE_LINES: usize = 3;
const LINE_SPACING: f64 = 1.3;
const LABEL_COLOUR: &str = "#b00000";

type Rect = (f64, f64, f64, f64);
type Segment = (Point, Point);

pub struct RenderSheet {
    pub svg: String,
    /// Each view's caption and the pieces labelled in it, in model order
    pub labels: Vec<(&'static str, Vec<String>)>,
    pub unlabelled: Vec<String>,
    pub note: Vec<String>,
}

struct View {
    caption: &'static str,
    projection: Projection,
    column: usize,
    row: usize,
}

/// The top, front, isometric and right side views (views.py: VIEWS).
fn views() -> [View; 4] {
    [
        View {
            caption: "from +z",
            projection: axis_view(2, 1),
            column: 0,
            row: 0,
        },
        View {
            caption: "from +y",
            projection: axis_view(1, 1),
            column: 0,
            row: 1,
        },
        View {
            caption: "from -x +y +z",
            projection: isometric(),
            column: 1,
            row: 0,
        },
        View {
            caption: "from -x",
            projection: axis_view(0, -1),
            column: 1,
            row: 1,
        },
    ]
}

struct Text {
    x: f64,
    y: f64,
    text: String,
    size: f64,
    colour: &'static str,
    anchor: &'static str,
}

fn visible_lines(assembly: &Assembly, view: &Projection) -> Vec<Segment> {
    let bodies: Vec<_> = assembly
        .model
        .pieces
        .iter()
        .map(|piece| {
            board_body(
                piece.shape(),
                &piece_holes(assembly, &piece.id),
                assembly.placement.pose(&piece.id),
                view,
            )
        })
        .collect();
    sort_lines(&bodies, view)
        .into_iter()
        .flat_map(|sorted| sorted.visible)
        .collect()
}

fn bounds(lines: &[Segment]) -> Option<Rect> {
    lines
        .iter()
        .flat_map(|&(a, b)| [a, b])
        .fold(None, |r: Option<Rect>, p| {
            Some(r.map_or((p.0, p.1, p.0, p.1), |r| {
                (r.0.min(p.0), r.1.min(p.1), r.2.max(p.0), r.3.max(p.1))
            }))
        })
}

/// Pieces whose centres the viewer sees, no other piece between (views.py:
/// visible_labels), in model order, with where they project.
fn visible_labels(assembly: &Assembly, view: &Projection) -> Vec<(String, Point)> {
    let boxes: Vec<(&str, Bounds)> = assembly
        .model
        .pieces
        .iter()
        .map(|p| {
            (
                p.id.as_str(),
                assembly.placement.pose(&p.id).bounds(p.shape()),
            )
        })
        .collect();
    let toward = view.toward();
    boxes
        .iter()
        .filter_map(|&(id, (low, high))| {
            let centre: [f64; 3] = std::array::from_fn(|i| (low[i] + high[i]) / 2.0);
            let hidden = boxes
                .iter()
                .any(|&(other, (l, h))| other != id && blocks(centre, toward, l, h));
            (!hidden).then(|| (id.to_string(), view.project(centre)))
        })
        .collect()
}

fn overlaps(a: Rect, b: Rect) -> bool {
    a.0 < b.2 && b.0 < a.2 && a.1 < b.3 && b.1 < a.3
}

/// textwrap's letters: word characters but digits
fn is_letter(c: char) -> bool {
    (c.is_alphanumeric() && !c.is_numeric()) || c == '_'
}

/// A word split after its hyphens where textwrap splits it: two letters (or
/// letter, hyphen, letter) before the hyphen and two letters (or letter,
/// hyphen, letter) after.
fn hyphen_parts(word: &str) -> Vec<String> {
    let chars: Vec<char> = word.chars().collect();
    let at = |i: isize| usize::try_from(i).ok().and_then(|i| chars.get(i).copied());
    let letter = |i: isize| at(i).is_some_and(is_letter);
    let (mut parts, mut start) = (Vec::new(), 0);
    for i in 1..chars.len() {
        if chars[i] != '-' {
            continue;
        }
        let j = i as isize;
        let before = (letter(j - 2) && letter(j - 1))
            || (letter(j - 3) && at(j - 2) == Some('-') && letter(j - 1));
        let after = letter(j + 1) && (letter(j + 2) || (at(j + 2) == Some('-') && letter(j + 3)));
        if before && after {
            parts.push(chars[start..=i].iter().collect());
            start = i + 1;
        }
    }
    parts.push(chars[start..].iter().collect());
    parts
}

/// Python's textwrap.wrap(text, width) for a line of words and spaces: lines
/// filled greedily, long words broken (after a hyphen when there is one).
/// Its em-dash rule is left out: piece IDs never have two hyphens in a row.
pub fn wrap(text: &str, width: usize) -> Vec<String> {
    let mut runs: Vec<String> = Vec::new();
    let mut run = String::new();
    for c in text.chars() {
        if !run.is_empty() && (c == ' ') != run.starts_with(' ') {
            runs.push(std::mem::take(&mut run));
        }
        run.push(c);
    }
    runs.push(run);
    // Popped from the end, as textwrap does
    let mut chunks: Vec<String> = runs
        .into_iter()
        .flat_map(|run| {
            if run.starts_with(' ') {
                vec![run]
            } else {
                hyphen_parts(&run)
            }
        })
        .filter(|chunk| !chunk.is_empty())
        .collect();
    chunks.reverse();
    let len = |s: &str| s.chars().count();
    let mut lines = Vec::new();
    while !chunks.is_empty() {
        if !lines.is_empty() && chunks.last().is_some_and(|c| c.trim().is_empty()) {
            chunks.pop();
        }
        let (mut line, mut length): (Vec<String>, usize) = (Vec::new(), 0);
        while let Some(chunk) = chunks.last() {
            if length + len(chunk) > width {
                break;
            }
            length += len(chunk);
            line.push(chunks.pop().expect("a chunk"));
        }
        if let Some(last) = chunks.last_mut()
            && len(last) > width
        {
            let chunk: Vec<char> = last.chars().collect();
            // A full line takes none of it (textwrap's _handle_long_word)
            let space = if width < 1 { 1 } else { width - length };
            let mut end = space;
            if let Some(hyphen) = chunk[..space].iter().rposition(|&c| c == '-')
                && hyphen > 0
                && chunk[..hyphen].iter().any(|&c| c != '-')
            {
                end = hyphen + 1;
            }
            line.push(chunk[..end].iter().collect());
            *last = chunk[end..].iter().collect();
        }
        if line.last().is_some_and(|c| c.trim().is_empty()) {
            line.pop();
        }
        if !line.is_empty() {
            lines.push(line.concat());
        }
    }
    lines
}

/// The note: the title with the overall size, then the pieces no view
/// labels, cut short with a count of the rest to fit the note's lines.
fn note(assembly: &Assembly, title: &str, unlabelled: &[String], width: usize) -> Vec<String> {
    let head = if assembly.placement.groups.len() == 1 {
        let (low, high) = overall_bounds(&assembly.model, &assembly.placement);
        let sizes: Vec<String> = (0..3).map(|i| format_mm(high[i] - low[i])).collect();
        format!("{title}  {} mm (x × y × z)", sizes.join(" x "))
    } else {
        format!("{title}  pieces not connected")
    };
    if unlabelled.is_empty() {
        return vec![head];
    }
    for shown in (1..=unlabelled.len()).rev() {
        let rest = unlabelled.len() - shown;
        let listed = format!("not labelled: {}", unlabelled[..shown].join(", "));
        let text = if rest > 0 {
            format!("{listed} (+{rest} more)")
        } else {
            listed
        };
        let lines = wrap(&text, width);
        if lines.len() < NOTE_LINES {
            return std::iter::once(head).chain(lines).collect();
        }
    }
    vec![head, format!("not labelled: {} pieces", unlabelled.len())]
}

fn escape(text: &str) -> String {
    text.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

/// The sheet, `size` px square, every view at one scale.
pub fn render_sheet(assembly: &Assembly, title: &str, size: u32) -> RenderSheet {
    let side = f64::from(size);
    let margin = side * MARGIN;
    let caption_height = side * MARGIN;
    // Floors keep small images readable
    let label_size = (side / 80.0).max(10.0);
    let caption_size = (side / 50.0).max(12.0);
    let note_size = (side / 60.0).max(10.0);
    let line_height = note_size * LINE_SPACING;
    // The note's lines stack up from the bottom margin; the views stay above
    let bottom = margin / 2.0 + (NOTE_LINES - 1) as f64 * line_height + note_size;
    let cell_width = (side - 2.0 * margin) / 2.0;
    let cell_height = (side - margin - bottom) / 2.0;
    let drawing_height = cell_height - caption_height;
    let views = views();
    let projected: Vec<(Vec<Segment>, Option<Rect>)> = views
        .iter()
        .map(|view| {
            let lines = visible_lines(assembly, &view.projection);
            let b = bounds(&lines);
            (lines, b)
        })
        .collect();
    let largest = projected
        .iter()
        .filter_map(|(_, b)| *b)
        .map(|b| (b.2 - b.0).max(b.3 - b.1))
        .fold(0.0, f64::max);
    let scale = if largest > 0.0 {
        cell_width.min(drawing_height) * VIEW_FILL / largest
    } else {
        1.0
    };
    let (mut segments, mut texts, mut labels) = (Vec::new(), Vec::new(), Vec::new());
    for (view, (lines, b)) in views.iter().zip(&projected) {
        let centre_x = margin + view.column as f64 * cell_width + cell_width / 2.0;
        let cell_top = side - margin - view.row as f64 * cell_height;
        let centre_y = cell_top - caption_height - drawing_height / 2.0;
        let (bx, by) = b.map_or((0.0, 0.0), |b| ((b.0 + b.2) / 2.0, (b.1 + b.3) / 2.0));
        let (dx, dy) = (centre_x - bx * scale, centre_y - by * scale);
        let place = |p: Point| (dx + p.0 * scale, dy + p.1 * scale);
        segments.extend(lines.iter().map(|&(a, c)| (place(a), place(c))));
        texts.push(Text {
            x: centre_x,
            y: cell_top - caption_height / 2.0,
            text: view.caption.into(),
            size: caption_size,
            colour: "black",
            anchor: "middle",
        });
        let (mut taken, mut named): (Vec<Rect>, Vec<String>) = (Vec::new(), Vec::new());
        for (id, at) in visible_labels(assembly, &view.projection) {
            let (x, y) = place(at);
            let half = id.chars().count() as f64 * label_size * 0.3;
            let area = (
                x - half,
                y - label_size / 2.0,
                x + half,
                y + label_size / 2.0,
            );
            if taken.iter().any(|&other| overlaps(area, other)) {
                continue;
            }
            taken.push(area);
            texts.push(Text {
                x,
                y,
                text: id.clone(),
                size: label_size,
                colour: LABEL_COLOUR,
                anchor: "middle",
            });
            named.push(id);
        }
        labels.push((view.caption, named));
    }
    let unlabelled: Vec<String> = assembly
        .model
        .pieces
        .iter()
        .map(|p| p.id.clone())
        .filter(|id| !labels.iter().any(|(_, named)| named.contains(id)))
        .collect();
    // About 0.55 em per character in a sans-serif font
    let width = ((side - 2.0 * margin) / (note_size * 0.55)) as usize;
    let note = note(assembly, title, &unlabelled, width);
    for (index, line) in note.iter().rev().enumerate() {
        // The last line sits in the bottom margin; earlier lines stack above
        texts.push(Text {
            x: margin,
            y: margin / 2.0 + index as f64 * line_height,
            text: line.clone(),
            size: note_size,
            colour: "black",
            anchor: "start",
        });
    }
    let n = |v: f64| format!("{v:.2}");
    let flip = |y: f64| side - y;
    let mut svg = format!(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{size}\" height=\"{size}\" \
         viewBox=\"0 0 {size} {size}\"><g fill=\"none\" stroke=\"#000\" stroke-width=\"{}\" \
         stroke-linecap=\"round\"><path d=\"",
        n((side / 1000.0).max(1.0))
    );
    for &((ax, ay), (bx, by)) in &segments {
        svg.push_str(&format!(
            "M{} {}L{} {}",
            n(ax),
            n(flip(ay)),
            n(bx),
            n(flip(by))
        ));
    }
    svg.push_str(
        "\"/></g><g font-family=\"DejaVu Sans, sans-serif\" dominant-baseline=\"middle\">",
    );
    for text in &texts {
        let common = format!(
            "x=\"{}\" y=\"{}\" font-size=\"{}\" text-anchor=\"{}\"",
            n(text.x),
            n(flip(text.y)),
            n(text.size),
            text.anchor
        );
        let body = escape(&text.text);
        // A white outline underneath keeps the text readable across lines
        svg.push_str(&format!(
            "<text {common} fill=\"white\" stroke=\"white\" stroke-width=\"{}\">{body}</text>",
            n(text.size / 5.0)
        ));
        svg.push_str(&format!(
            "<text {common} fill=\"{}\">{body}</text>",
            text.colour
        ));
    }
    svg.push_str("</g></svg>");
    RenderSheet {
        svg,
        labels,
        unlabelled,
        note,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use nichiyou_daiku_core::dsl::parse;

    #[test]
    fn wrapping_follows_python_textwrap() {
        // What textwrap.wrap gives for these (Python 3.13)
        assert_eq!(
            wrap(
                "not labelled: apron_upper_back, apron_lower_back, apron_upper_right, shelf_2",
                30
            ),
            [
                "not labelled:",
                "apron_upper_back,",
                "apron_lower_back,",
                "apron_upper_right, shelf_2"
            ]
        );
        assert_eq!(
            wrap(
                "not labelled: side-left, side-right, back-panel-top, x-1, ab-cd",
                20
            ),
            [
                "not labelled: side-",
                "left, side-right,",
                "back-panel-top, x-1,",
                "ab-cd"
            ]
        );
        assert_eq!(
            wrap(
                "not labelled: a_very_long_piece_name_that_does_not_fit_anywhere_at_all, b",
                20
            ),
            [
                "not labelled: a_very",
                "_long_piece_name_tha",
                "t_does_not_fit_anywh",
                "ere_at_all, b"
            ]
        );
        assert_eq!(
            wrap("not labelled: aa, bb (+3 more)", 12),
            ["not", "labelled:", "aa, bb (+3", "more)"]
        );
    }

    #[test]
    fn wrapping_breaks_a_long_word_only_where_the_line_has_room() {
        // textwrap gives a full line no part of the next long word
        assert_eq!(
            wrap("not labelled: leg-front-left-upper", 8),
            ["not labe", "lled:", "leg-", "front-", "left-", "upper"]
        );
        assert_eq!(
            wrap("not labelled: a--b, x-y-z, abc-def-ghi, 12-34", 10),
            [
                "not",
                "labelled:",
                "a--b,",
                "x-y-z,",
                "abc-def-",
                "ghi, 12-34"
            ]
        );
    }

    fn two_boards() -> Assembly {
        Assembly::of(parse("(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n").unwrap()).unwrap()
    }

    #[test]
    fn the_note_cuts_long_lists_short() {
        let names: Vec<String> = (0..60)
            .map(|i| format!("hidden_piece_number_{i}"))
            .collect();
        let lines = note(&two_boards(), "many.nd", &names, 66);
        assert_eq!(lines.len(), 3);
        assert!(lines[2].ends_with(" more)"), "{lines:?}");
        // Not even one name fits in the note's lines: only the count is left
        let long = vec!["a_piece_name_much_longer_than_the_note_is_wide".to_string()];
        let lines = note(&two_boards(), "long.nd", &long, 12);
        assert_eq!(lines[1], "not labelled: 1 pieces");
    }

    #[test]
    fn a_sheet_is_square_with_four_captions() {
        let sheet = render_sheet(&two_boards(), "two.nd", 800);
        assert!(
            sheet.svg.starts_with(
                "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"800\" height=\"800\""
            )
        );
        for caption in ["from +z", "from +y", "from -x +y +z", "from -x"] {
            assert!(
                sheet.svg.contains(&format!(">{caption}</text>")),
                "{caption}"
            );
        }
        assert!(
            sheet.note[0].starts_with("two.nd  ") && sheet.note[0].ends_with(" mm (x × y × z)")
        );
    }
}
