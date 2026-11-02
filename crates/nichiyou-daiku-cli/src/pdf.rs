//! SVG to PDF with svg2pdf, in the fonts of `fonts.rs`: text stays text,
//! with only the glyphs used embedded.

use resvg::usvg;

/// usvg reads mm at 96 dpi; at the same dpi the PDF page is the SVG's page
const SVG_DPI: f32 = 96.0;

#[cfg_attr(not(test), expect(dead_code, reason = "drawing uses it"))]
pub fn pdf(svg: &str) -> Result<Vec<u8>, String> {
    let tree = usvg::Tree::from_str(svg, &crate::fonts::options()).map_err(|e| e.to_string())?;
    svg2pdf::to_pdf(
        &tree,
        svg2pdf::ConversionOptions::default(),
        svg2pdf::PageOptions { dpi: SVG_DPI },
    )
    .map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    const PAGE: &str = r##"<svg xmlns="http://www.w3.org/2000/svg" width="420mm" height="297mm" viewBox="0 0 420 297"><path d="M10 10L410 287" stroke="#000"/><text x="20" y="20" font-family="DejaVu Sans, sans-serif" font-size="5">Title: table</text></svg>"##;

    /// The first page's MediaBox in pt.
    fn media_box(pdf: &[u8]) -> Vec<f64> {
        let text = String::from_utf8_lossy(pdf);
        let start = text.find("/MediaBox [").expect("a page size") + "/MediaBox [".len();
        let end = start + text[start..].find(']').expect("a closed MediaBox");
        text[start..end]
            .split_whitespace()
            .map(|n| n.parse().unwrap())
            .collect()
    }

    #[test]
    fn a_pdf_page_is_the_svg_page_in_mm() {
        let bytes = pdf(PAGE).unwrap();
        assert!(bytes.starts_with(b"%PDF-"));
        let size = media_box(&bytes);
        // A3: 420 x 297mm is 1190.55 x 841.89pt
        assert!(
            (size[2] - 1190.55).abs() < 0.05 && (size[3] - 841.89).abs() < 0.05,
            "{size:?}"
        );
    }

    #[test]
    fn text_stays_text_in_the_built_in_font() {
        let bytes = pdf(PAGE).unwrap();
        assert!(String::from_utf8_lossy(&bytes).contains("+DejaVuSans"));
    }
}
