//! SVG to PNG with resvg, in the DejaVu Sans built in: the images look the
//! same on every machine (agents read them), with no system library.

use std::sync::{Arc, OnceLock};

use resvg::{tiny_skia, usvg};

static BOOK: &[u8] = include_bytes!("../fonts/DejaVuSans.ttf");
static BOLD: &[u8] = include_bytes!("../fonts/DejaVuSans-Bold.ttf");

fn fonts() -> Arc<usvg::fontdb::Database> {
    static FONTS: OnceLock<Arc<usvg::fontdb::Database>> = OnceLock::new();
    FONTS
        .get_or_init(|| {
            let mut fonts = usvg::fontdb::Database::new();
            fonts.load_font_data(BOOK.to_vec());
            fonts.load_font_data(BOLD.to_vec());
            // The drawings ask for sans-serif after DejaVu Sans
            fonts.set_sans_serif_family("DejaVu Sans");
            Arc::new(fonts)
        })
        .clone()
}

/// The SVG as a PNG `width` px wide, its height to scale, on white.
#[cfg_attr(not(test), expect(dead_code, reason = "render and steps use it"))]
pub fn png(svg: &str, width: u32) -> Result<Vec<u8>, String> {
    let options = usvg::Options {
        fontdb: fonts(),
        font_family: "DejaVu Sans".into(),
        ..Default::default()
    };
    let tree = usvg::Tree::from_str(svg, &options).map_err(|e| e.to_string())?;
    let size = tree.size();
    let scale = width as f32 / size.width();
    let height = (size.height() * scale).round().max(1.0) as u32;
    let mut pixmap =
        tiny_skia::Pixmap::new(width, height).ok_or("the image is too large to draw")?;
    pixmap.fill(tiny_skia::Color::WHITE);
    resvg::render(
        &tree,
        tiny_skia::Transform::from_scale(scale, scale),
        &mut pixmap.as_mut(),
    );
    pixmap.encode_png().map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use resvg::tiny_skia::Pixmap;

    #[test]
    fn a_png_is_as_wide_as_asked_and_keeps_the_shape() {
        let svg = r##"<svg xmlns="http://www.w3.org/2000/svg" width="280mm" height="140mm" viewBox="0 0 280 140"><path d="M10 10L270 130" stroke="#000"/></svg>"##;
        let image = Pixmap::decode_png(&png(svg, 800).unwrap()).unwrap();
        assert_eq!((image.width(), image.height()), (800, 400));
    }

    #[test]
    fn text_is_drawn_in_the_built_in_font() {
        let svg = r##"<svg xmlns="http://www.w3.org/2000/svg" width="200" height="50" viewBox="0 0 200 50"><text x="10" y="35" font-family="DejaVu Sans, sans-serif" font-size="30">Holes φ2.5</text></svg>"##;
        let image = Pixmap::decode_png(&png(svg, 200).unwrap()).unwrap();
        let dark = image.pixels().iter().filter(|p| p.red() < 100).count();
        assert!(
            dark > 200,
            "only {dark} dark pixels: the text was not drawn"
        );
    }
}
