//! SVG to PNG with resvg, in the fonts of `fonts.rs`: the images look the
//! same on every machine (agents read them), with no system library to draw.

use resvg::{tiny_skia, usvg};

/// The SVG as a PNG `width` px wide, its height to scale, on white.
pub fn png(svg: &str, width: u32) -> Result<Vec<u8>, String> {
    let options = crate::fonts::options();
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
    use resvg::usvg::fontdb::{Database, Source};

    #[test]
    fn only_the_built_in_dejavu_sans_draws_latin_text() {
        // Passes before the machine's fonts come in; it fails if their
        // DejaVu Sans, maybe another version, slips in with them
        let fonts = crate::fonts::fonts();
        let dejavu: Vec<_> = fonts
            .faces()
            .filter(|f| f.families.iter().any(|(name, _)| name == "DejaVu Sans"))
            .collect();
        assert_eq!(dejavu.len(), 2);
        assert!(dejavu.iter().all(|f| matches!(f.source, Source::Binary(_))));
    }

    #[test]
    fn what_dejavu_sans_lacks_comes_from_the_machine() {
        let mut machine = Database::new();
        machine.load_system_fonts();
        let covered = machine.faces().any(|face| {
            machine
                .with_face_data(face.id, |data, index| {
                    ttf_parser::Face::parse(data, index)
                        .ok()
                        .and_then(|f| f.glyph_index('左'))
                        .is_some()
                })
                .unwrap_or(false)
        });
        if !covered {
            return; // No Japanese font on this machine: nothing can draw it
        }
        let draw = |c: char| {
            let svg = format!(
                r##"<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60"><text x="10" y="45" font-family="DejaVu Sans, sans-serif" font-size="40">{c}</text></svg>"##
            );
            Pixmap::decode_png(&png(&svg, 60).unwrap())
                .unwrap()
                .data()
                .to_vec()
        };
        // A font without them draws both as the same missing-glyph box
        assert_ne!(draw('左'), draw('右'), "左 and 右 were drawn as boxes");
    }

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
