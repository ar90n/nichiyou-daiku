//! SVG in page mm. Pages are laid out with y up, as the CLI's drawings
//! are; rendering turns them into SVG's y down.

use crate::text::font_size;

pub type Point = (f64, f64);

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Stroke {
    /// Visible outlines
    Outline,
    /// Hidden lines, dashed
    Hidden,
    /// Dimension, extension and leader lines
    Thin,
    /// A step's earlier pieces, grey
    Before,
    /// A step's own pieces, bold
    New,
    /// A step's own pieces where they are hidden, dashed
    NewHidden,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Ink {
    Black,
    /// What orients and is not built: the cue and reference names
    Grey,
    /// The ground under a name
    White,
}

impl Ink {
    fn css(self) -> &'static str {
        match self {
            Ink::Black => "#000",
            Ink::Grey => "#969696",
            Ink::White => "#fff",
        }
    }
}

enum Item {
    Path {
        points: Vec<Point>,
        closed: bool,
        stroke: Stroke,
    },
    Fill {
        points: Vec<Point>,
        ink: Ink,
    },
    Text {
        text: String,
        centre: Point,
        vertical: bool,
        ink: Ink,
    },
}

pub struct Svg {
    width: f64,
    items: Vec<Item>,
}

/// A number for SVG: three decimals at most, no trailing zeros, no "-0".
fn n(value: f64) -> String {
    let text = format!("{value:.3}");
    let text = text.trim_end_matches('0').trim_end_matches('.');
    if text == "-0" {
        "0".to_string()
    } else {
        text.to_string()
    }
}

fn escape(text: &str) -> String {
    text.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}

impl Svg {
    pub fn new(width: f64) -> Svg {
        Svg {
            width,
            items: Vec::new(),
        }
    }

    pub fn line(&mut self, from: Point, to: Point, stroke: Stroke) {
        self.items.push(Item::Path {
            points: vec![from, to],
            closed: false,
            stroke,
        });
    }

    pub fn polyline(&mut self, points: &[Point], closed: bool, stroke: Stroke) {
        self.items.push(Item::Path {
            points: points.to_vec(),
            closed,
            stroke,
        });
    }

    /// A filled polygon: arrowheads and marks.
    pub fn fill(&mut self, points: &[Point]) {
        self.fill_ink(points, Ink::Black);
    }

    pub fn fill_ink(&mut self, points: &[Point], ink: Ink) {
        self.items.push(Item::Fill {
            points: points.to_vec(),
            ink,
        });
    }

    /// Text centred on `centre`; vertical text reads from the bottom up.
    pub fn text(&mut self, text: &str, centre: Point, vertical: bool) {
        self.text_ink(text, centre, vertical, Ink::Black);
    }

    pub fn text_ink(&mut self, text: &str, centre: Point, vertical: bool, ink: Ink) {
        self.items.push(Item::Text {
            text: text.to_string(),
            centre,
            vertical,
            ink,
        });
    }

    pub fn render(&self, height: f64) -> String {
        let y = |v: f64| height - v;
        let shape = |points: &[Point], closed: bool| {
            let mut d = String::new();
            for (i, &(px, py)) in points.iter().enumerate() {
                d.push_str(if i == 0 { "M" } else { "L" });
                d.push_str(&format!("{} {}", n(px), n(y(py))));
            }
            if closed {
                d.push('Z');
            }
            d
        };
        let path =
            |points: &[Point], closed: bool| format!("<path d=\"{}\"/>", shape(points, closed));
        let mut out = format!(
            "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{w}mm\" height=\"{h}mm\" viewBox=\"0 0 {w} {h}\">",
            w = n(self.width),
            h = n(height)
        );
        let layers = [
            (
                Stroke::Before,
                "class=\"before\" stroke=\"#a0a0a0\" stroke-width=\"0.18\"",
            ),
            (
                Stroke::New,
                "class=\"new\" stroke=\"#000\" stroke-width=\"0.5\"",
            ),
            (
                Stroke::NewHidden,
                "class=\"new-hidden\" stroke=\"#000\" stroke-width=\"0.25\" stroke-dasharray=\"1.2 0.6\"",
            ),
            (
                Stroke::Outline,
                "class=\"outline\" stroke=\"#000\" stroke-width=\"0.35\"",
            ),
            (
                Stroke::Hidden,
                "class=\"hidden\" stroke=\"#787878\" stroke-width=\"0.15\" stroke-dasharray=\"1.2 0.6\"",
            ),
            (
                Stroke::Thin,
                "class=\"thin\" stroke=\"#000\" stroke-width=\"0.13\"",
            ),
        ];
        for (stroke, style) in layers {
            out.push_str(&format!(
                "<g fill=\"none\" stroke-linecap=\"round\" {style}>"
            ));
            for item in &self.items {
                if let Item::Path {
                    points,
                    closed,
                    stroke: s,
                } = item
                    && *s == stroke
                {
                    out.push_str(&path(points, *closed));
                }
            }
            out.push_str("</g>");
        }
        // Fills keep their order: a name's ground goes under what follows it
        out.push_str("<g stroke=\"none\">");
        for item in &self.items {
            if let Item::Fill { points, ink } = item {
                out.push_str(&format!(
                    "<path d=\"{}\" fill=\"{}\"/>",
                    shape(points, true),
                    ink.css()
                ));
            }
        }
        out.push_str("</g>");
        out.push_str(&format!(
            "<g fill=\"#000\" font-family=\"DejaVu Sans, Verdana, Arial, sans-serif\" font-size=\"{}\" \
             text-anchor=\"middle\" \
             xml:space=\"preserve\" style=\"white-space:pre\">",
            n(font_size())
        ));
        for item in &self.items {
            if let Item::Text {
                text,
                centre,
                vertical,
                ink,
            } = item
            {
                let (x, yy) = (n(centre.0), n(y(centre.1)));
                // Black text takes the group's fill
                let colour = if *ink == Ink::Black {
                    String::new()
                } else {
                    format!(" fill=\"{}\"", ink.css())
                };
                let turn = if *vertical {
                    format!(" transform=\"rotate(-90 {x} {yy})\"")
                } else {
                    String::new()
                };
                out.push_str(&format!(
                    "<text x=\"{x}\" y=\"{yy}\" dominant-baseline=\"central\"{colour}{turn}>{}</text>",
                    escape(text)
                ));
            }
        }
        out.push_str("</g></svg>");
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pages_turn_y_up_into_svg_y_down() {
        let mut svg = Svg::new(280.0);
        svg.line((0.0, 0.0), (10.0, 0.0), Stroke::Outline);
        svg.text("A", (5.0, 90.0), false);
        let out = svg.render(100.0);
        assert!(out.starts_with("<svg xmlns=\"http://www.w3.org/2000/svg\""));
        assert!(out.contains("viewBox=\"0 0 280 100\""));
        assert!(out.contains("<path d=\"M0 100L10 100\"/>"));
        // On each text: older WebKit does not inherit it from the group
        assert!(out.contains("<text x=\"5\" y=\"10\" dominant-baseline=\"central\">A</text>"));
        assert!(out.ends_with("</svg>"));
    }

    #[test]
    fn runs_of_spaces_stay_apart() {
        // A title's fields are three spaces apart; SVG would collapse them
        let mut svg = Svg::new(10.0);
        svg.text("a   b", (1.0, 1.0), false);
        let out = svg.render(10.0);
        assert!(out.contains("xml:space=\"preserve\"") && out.contains("white-space:pre"));
        assert!(out.contains(">a   b</text>"));
    }

    #[test]
    fn steps_draw_earlier_pieces_grey_and_new_ones_bold() {
        let mut svg = Svg::new(10.0);
        svg.line((0.0, 0.0), (1.0, 0.0), Stroke::Before);
        svg.line((0.0, 1.0), (1.0, 1.0), Stroke::New);
        svg.line((0.0, 2.0), (1.0, 2.0), Stroke::NewHidden);
        let out = svg.render(10.0);
        assert!(out.contains("<g fill=\"none\" stroke-linecap=\"round\" class=\"before\" stroke=\"#a0a0a0\" stroke-width=\"0.18\"><path d=\"M0 10L1 10\"/></g>"));
        assert!(out.contains(
            "class=\"new\" stroke=\"#000\" stroke-width=\"0.5\"><path d=\"M0 9L1 9\"/></g>"
        ));
        assert!(out.contains("class=\"new-hidden\" stroke=\"#000\" stroke-width=\"0.25\" stroke-dasharray=\"1.2 0.6\"><path d=\"M0 8L1 8\"/></g>"));
        assert!(out.find("class=\"before\"").unwrap() < out.find("class=\"new\"").unwrap());
    }

    #[test]
    fn grounds_are_white_and_cues_grey() {
        let mut svg = Svg::new(10.0);
        svg.fill_ink(&[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)], Ink::White);
        svg.text_ink("leg", (5.0, 5.0), false, Ink::Grey);
        let out = svg.render(10.0);
        assert!(out.contains("<path d=\"M0 10L1 10L1 9Z\" fill=\"#fff\"/>"));
        assert!(out.contains(
            "<text x=\"5\" y=\"5\" dominant-baseline=\"central\" fill=\"#969696\">leg</text>"
        ));
    }

    #[test]
    fn names_stay_text() {
        let mut svg = Svg::new(10.0);
        svg.text("a<b & \"c\"", (1.0, 1.0), true);
        let out = svg.render(10.0);
        assert!(out.contains(">a&lt;b &amp; &quot;c&quot;</text>"));
        assert!(out.contains("transform=\"rotate(-90 1 9)\""));
    }
}
