//! The fonts the PNGs and PDFs are drawn in: DejaVu Sans built in, so Latin
//! text looks the same on every machine, and the machine's fonts for what
//! DejaVu Sans lacks, such as Japanese names.

use std::sync::{Arc, OnceLock};

use resvg::usvg;
use resvg::usvg::fontdb::Database;

const FAMILY: &str = "DejaVu Sans";
static BOOK: &[u8] = include_bytes!("../fonts/DejaVuSans.ttf");
static BOLD: &[u8] = include_bytes!("../fonts/DejaVuSans-Bold.ttf");

pub fn fonts() -> Arc<Database> {
    static FONTS: OnceLock<Arc<Database>> = OnceLock::new();
    FONTS
        .get_or_init(|| {
            let mut fonts = Database::new();
            fonts.load_system_fonts();
            // The machine's DejaVu Sans may be another version: Latin text
            // comes from the built-in one only
            let theirs: Vec<_> = fonts
                .faces()
                .filter(|f| f.families.iter().any(|(name, _)| name == FAMILY))
                .map(|f| f.id)
                .collect();
            for id in theirs {
                fonts.remove_face(id);
            }
            fonts.load_font_data(BOOK.to_vec());
            fonts.load_font_data(BOLD.to_vec());
            // The drawings ask for sans-serif after DejaVu Sans
            fonts.set_sans_serif_family(FAMILY);
            Arc::new(fonts)
        })
        .clone()
}

/// SVG options that draw in these fonts.
pub fn options() -> usvg::Options<'static> {
    usvg::Options {
        fontdb: fonts(),
        font_family: FAMILY.into(),
        ..Default::default()
    }
}
