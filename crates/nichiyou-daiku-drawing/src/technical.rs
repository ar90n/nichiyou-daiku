//! The technical drawing (drawing.py: technical_drawing): the top, front
//! and right side views at one scale with hidden lines and dimensions, an
//! isometric view, and a title block, on an A4 to A1 page. Page mm, y up.

use crate::text::{line_height, text_size};

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
#[cfg_attr(not(test), expect(dead_code, reason = "technical_drawing uses it"))]
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
#[cfg_attr(not(test), expect(dead_code, reason = "technical_drawing uses it"))]
fn title_block(frame: Rect, rows: &[(&'static str, String)]) -> Rect {
    let values = rows.iter().map(|(_, v)| text_size(v).0).fold(0.0, f64::max);
    let width = (2.0 * TITLE_PAD + label_width() + COLUMN_GAP + values).max(TITLE_MIN_WIDTH);
    let height = 2.0 * TITLE_PAD + rows.len() as f64 * spacing();
    (frame.2 - width, frame.1, frame.2, frame.1 + height)
}

/// How to make room for values that do not fit (drawing.py: _crowded_advice).
#[cfg_attr(not(test), expect(dead_code, reason = "technical_drawing uses it"))]
fn advice(page: Page) -> String {
    match page.larger() {
        Some(larger) => format!(
            "Use a larger page (drawing --page-size {}) or leave the dimensions out (drawing --no-dimensions)",
            larger.name()
        ),
        None => "Leave the dimensions out (drawing --no-dimensions)".to_string(),
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
