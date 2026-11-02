//! Text sizes for the drawings: DejaVu Sans, its figures TEXT_SIZE high
//! (JIS sizes lettering by the figures). Widths come from the font's
//! advances; a browser without the font lays it out a little differently.

/// Height of the figures in page mm.
pub const TEXT_SIZE: f64 = 2.5;

const UNITS_PER_EM: f64 = 2048.0;
/// From the lowest to the highest point of 0..9
const FIGURE_HEIGHT: f64 = 1549.0;
/// A figure's width, for characters the table does not have
const DEFAULT_WIDTH: u16 = 1303;

/// Kana, kanji, hangul and full-width forms: a full em in the fonts that
/// draw them (DejaVu Sans has none of them)
const WIDE_WIDTH: u16 = 2048;

/// DejaVu Sans advance widths in font units.
const WIDTHS: &[(char, u16)] = &[
    (' ', 651),
    ('!', 821),
    ('"', 942),
    ('#', 1716),
    ('$', 1303),
    ('%', 1946),
    ('&', 1597),
    ('\'', 563),
    ('(', 799),
    (')', 799),
    ('*', 1024),
    ('+', 1716),
    (',', 651),
    ('-', 739),
    ('.', 651),
    ('/', 690),
    ('0', 1303),
    ('1', 1303),
    ('2', 1303),
    ('3', 1303),
    ('4', 1303),
    ('5', 1303),
    ('6', 1303),
    ('7', 1303),
    ('8', 1303),
    ('9', 1303),
    (':', 690),
    (';', 690),
    ('<', 1716),
    ('=', 1716),
    ('>', 1716),
    ('?', 1087),
    ('@', 2048),
    ('A', 1401),
    ('B', 1405),
    ('C', 1430),
    ('D', 1577),
    ('E', 1294),
    ('F', 1178),
    ('G', 1587),
    ('H', 1540),
    ('I', 604),
    ('J', 604),
    ('K', 1343),
    ('L', 1141),
    ('M', 1767),
    ('N', 1532),
    ('O', 1612),
    ('P', 1235),
    ('Q', 1612),
    ('R', 1423),
    ('S', 1300),
    ('T', 1251),
    ('U', 1499),
    ('V', 1401),
    ('W', 2025),
    ('X', 1403),
    ('Y', 1251),
    ('Z', 1403),
    ('[', 799),
    ('\\', 690),
    (']', 799),
    ('^', 1716),
    ('_', 1024),
    ('`', 1024),
    ('a', 1255),
    ('b', 1300),
    ('c', 1126),
    ('d', 1300),
    ('e', 1260),
    ('f', 721),
    ('g', 1300),
    ('h', 1298),
    ('i', 569),
    ('j', 569),
    ('k', 1186),
    ('l', 569),
    ('m', 1995),
    ('n', 1298),
    ('o', 1253),
    ('p', 1300),
    ('q', 1300),
    ('r', 842),
    ('s', 1067),
    ('t', 803),
    ('u', 1298),
    ('v', 1212),
    ('w', 1675),
    ('x', 1212),
    ('y', 1212),
    ('z', 1075),
    ('{', 1303),
    ('|', 690),
    ('}', 1303),
    ('~', 1716),
    ('×', 1716),
    ('φ', 1351),
    ('↧', 1716),
    ('▲', 1575),
    ('−', 1716),
];

/// The em in page mm, so that figures come out TEXT_SIZE high.
pub fn font_size() -> f64 {
    TEXT_SIZE * UNITS_PER_EM / FIGURE_HEIGHT
}

/// Height of a line of figures; dimension bands leave room for one.
pub fn line_height() -> f64 {
    TEXT_SIZE
}

fn is_wide(c: char) -> bool {
    matches!(c,
        '\u{1100}'..='\u{115F}'
        | '\u{2E80}'..='\u{303E}'
        | '\u{3041}'..='\u{33FF}'
        | '\u{3400}'..='\u{4DBF}'
        | '\u{4E00}'..='\u{9FFF}'
        | '\u{A000}'..='\u{A4CF}'
        | '\u{AC00}'..='\u{D7A3}'
        | '\u{F900}'..='\u{FAFF}'
        | '\u{FE30}'..='\u{FE4F}'
        | '\u{FF00}'..='\u{FF60}'
        | '\u{FFE0}'..='\u{FFE6}')
}

fn advance(c: char) -> u16 {
    if is_wide(c) {
        return WIDE_WIDTH;
    }
    WIDTHS
        .iter()
        .find(|(ch, _)| *ch == c)
        .map_or(DEFAULT_WIDTH, |&(_, w)| w)
}

/// Width and height of a line of text in page mm, unrotated.
pub fn text_size(text: &str) -> (f64, f64) {
    let units: f64 = text.chars().map(|c| f64::from(advance(c))).sum();
    (units / UNITS_PER_EM * font_size(), line_height())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn figures_are_text_size_high_and_one_width() {
        assert!((font_size() - 3.3054).abs() < 1e-3);
        let one = text_size("0").0;
        assert!((one - 2.1030).abs() < 1e-3);
        assert_eq!(text_size("7").0, one);
        assert!((text_size("397.5").0 - 9.4625).abs() < 1e-3);
        assert_eq!(text_size("397.5").1, TEXT_SIZE);
        assert!(text_size("φ8 ↧15 ×2").0 > text_size("8 15 2").0);
    }

    #[test]
    fn wide_characters_take_a_full_em() {
        // Kana, kanji and full-width forms are a full em in the fonts that draw them
        assert_eq!(text_size("左の枠").0, 3.0 * font_size());
        assert_eq!(text_size("ＡＢ").0, 2.0 * font_size());
    }
}
