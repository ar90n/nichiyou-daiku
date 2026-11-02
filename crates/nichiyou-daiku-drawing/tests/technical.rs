//! The technical drawing's page: views at one scale that fit the frame
//! beside the title block, hidden lines in the orthographic views only, and
//! the dimensions.

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_drawing::technical::{Page, Rect, TechnicalSheet, Titles, technical_drawing};

const TABLE: &str = include_str!("../../../examples/nd_files/simple_table_unknowns.nd");

fn assembly(source: &str) -> Assembly {
    Assembly::of(nichiyou_daiku_core::dsl::parse(source).unwrap()).unwrap()
}

fn titles() -> Titles<'static> {
    Titles {
        title: "table",
        drawing_number: "ND-1",
        designed_by: "nichiyou-daiku",
        date: "2026-11-02",
    }
}

fn inside(r: Rect, outer: Rect) -> bool {
    outer.0 <= r.0 && r.2 <= outer.2 && outer.1 <= r.1 && r.3 <= outer.3
}

fn apart(a: Rect, b: Rect) -> bool {
    a.2 <= b.0 || b.2 <= a.0 || a.3 <= b.1 || b.3 <= a.1
}

/// Everything drawn stays in the frame; the orthographic views keep off the
/// title block and the isometric sits above it.
fn assert_fits(sheet: &TechnicalSheet) {
    for view in &sheet.views {
        assert!(
            inside(view.rect, sheet.frame),
            "{} {:?} out of {:?}",
            view.caption,
            view.rect,
            sheet.frame
        );
    }
    for view in &sheet.views[..3] {
        assert!(
            apart(view.rect, sheet.title_block),
            "{} on the title block",
            view.caption
        );
    }
    assert!(
        sheet.views[3].rect.1 >= sheet.title_block.3,
        "the isometric is not above the title block"
    );
    for &(a, b) in &sheet.dimensions.lines {
        for p in [a, b] {
            assert!(
                inside((p.0, p.1, p.0, p.1), sheet.frame),
                "dimension line at {p:?} out of the frame"
            );
        }
    }
}

#[test]
fn views_fit_the_frame_beside_the_title_block() {
    let sheet = technical_drawing(&assembly(TABLE), Page::A3, &titles(), true);
    let captions: Vec<&str> = sheet.views.iter().map(|v| v.caption).collect();
    assert_eq!(captions, ["from +z", "from +y", "from -x", "from -x +y +z"]);
    assert_fits(&sheet);
    // The three orthographic views share the scale written in the title block
    assert!(
        sheet.views[..3]
            .iter()
            .all(|v| (v.scale - 1.0 / sheet.denominator).abs() < 1e-12)
    );
    assert_eq!(
        sheet.title_rows[1],
        (
            "Scale:",
            format!(
                "1:{}",
                nichiyou_daiku_core::pyfmt::format_mm(sheet.denominator)
            )
        )
    );
}

#[test]
fn the_scale_is_rounded_up_to_a_tenth_and_at_most_full_size() {
    let sheet = technical_drawing(&assembly(TABLE), Page::A3, &titles(), true);
    let tenths = sheet.denominator * 10.0;
    assert!((tenths - tenths.round()).abs() < 1e-9 && sheet.denominator > 1.0);
    let small = technical_drawing(&assembly("(a:2x4 =100)\n"), Page::A1, &titles(), true);
    assert_eq!(small.denominator, 1.0);
}

#[test]
fn a_tall_post_fits_an_a4_page() {
    let sheet = technical_drawing(&assembly("(post:2x4 =3650)\n"), Page::A4, &titles(), true);
    assert_fits(&sheet);
}

#[test]
fn hidden_lines_are_in_the_orthographic_views_only() {
    let sheet = technical_drawing(&assembly(TABLE), Page::A3, &titles(), true);
    assert!(sheet.views[..3].iter().any(|v| !v.hidden.is_empty()));
    assert!(sheet.views[3].hidden.is_empty());
    assert!(sheet.svg.contains("class=\"hidden\""));
}

#[test]
fn dimensions_go_in_only_when_asked_and_connected() {
    let with = technical_drawing(&assembly(TABLE), Page::A3, &titles(), true);
    assert!(!with.dimensions.labels.is_empty());
    let without = technical_drawing(&assembly(TABLE), Page::A3, &titles(), false);
    assert!(without.dimensions.labels.is_empty() && without.dimensions.lines.is_empty());
    let apart = technical_drawing(
        &assembly("(a:2x4 =400)\n(b:2x4 =400)\n"),
        Page::A3,
        &titles(),
        true,
    );
    assert!(apart.dimensions.labels.is_empty());
}

#[test]
fn the_page_is_the_paper_in_mm() {
    let sheet = technical_drawing(&assembly(TABLE), Page::A4, &titles(), true);
    assert!(sheet.svg.starts_with(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"297mm\" height=\"210mm\" viewBox=\"0 0 297 210\">"
    ));
    assert!(sheet.svg.contains(">table</text>") && sheet.svg.contains(">Designed by:</text>"));
}
