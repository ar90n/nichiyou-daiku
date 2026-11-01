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
}

enum Item {
    Path {
        points: Vec<Point>,
        closed: bool,
        stroke: Stroke,
    },
    Fill(Vec<Point>),
    Text {
        text: String,
        centre: Point,
        vertical: bool,
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
        self.items.push(Item::Fill(points.to_vec()));
    }

    /// Text centred on `centre`; vertical text reads from the bottom up.
    pub fn text(&mut self, text: &str, centre: Point, vertical: bool) {
        self.items.push(Item::Text {
            text: text.to_string(),
            centre,
            vertical,
        });
    }

    pub fn render(&self, height: f64) -> String {
        let y = |v: f64| height - v;
        let path = |points: &[Point], closed: bool| {
            let mut d = String::new();
            for (i, &(px, py)) in points.iter().enumerate() {
                d.push_str(if i == 0 { "M" } else { "L" });
                d.push_str(&format!("{} {}", n(px), n(y(py))));
            }
            if closed {
                d.push('Z');
            }
            format!("<path d=\"{d}\"/>")
        };
        let mut out = format!(
            "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{w}mm\" height=\"{h}mm\" viewBox=\"0 0 {w} {h}\">",
            w = n(self.width),
            h = n(height)
        );
        let layers = [
            (Stroke::Outline, "stroke=\"#000\" stroke-width=\"0.35\""),
            (
                Stroke::Hidden,
                "stroke=\"#787878\" stroke-width=\"0.15\" stroke-dasharray=\"1.2 0.6\"",
            ),
            (Stroke::Thin, "stroke=\"#000\" stroke-width=\"0.13\""),
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
        out.push_str("<g fill=\"#000\" stroke=\"none\">");
        for item in &self.items {
            if let Item::Fill(points) = item {
                out.push_str(&path(points, true));
            }
        }
        out.push_str("</g>");
        out.push_str(&format!(
            "<g fill=\"#000\" font-family=\"DejaVu Sans, Verdana, Arial, sans-serif\" font-size=\"{}\" \
             text-anchor=\"middle\" dominant-baseline=\"central\">",
            n(font_size())
        ));
        for item in &self.items {
            if let Item::Text {
                text,
                centre,
                vertical,
            } = item
            {
                let (x, yy) = (n(centre.0), n(y(centre.1)));
                let turn = if *vertical {
                    format!(" transform=\"rotate(-90 {x} {yy})\"")
                } else {
                    String::new()
                };
                out.push_str(&format!(
                    "<text x=\"{x}\" y=\"{yy}\"{turn}>{}</text>",
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
        assert!(out.contains("<text x=\"5\" y=\"10\">A</text>"));
        assert!(out.ends_with("</svg>"));
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
