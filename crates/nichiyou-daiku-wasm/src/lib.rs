//! The core for JavaScript: an .nd source in, the view JSON or a drawing out.

use wasm_bindgen::prelude::wasm_bindgen;

/// The view JSON of an .nd source (see the core's `view`).
#[wasm_bindgen]
pub fn view(source: &str) -> String {
    nichiyou_daiku_core::view(source).to_string()
}

fn drawing_json(answer: Result<nichiyou_daiku_drawing::Drawing, String>) -> String {
    match answer {
        Ok(drawing) => {
            serde_json::json!({"svg": drawing.svg, "notes": drawing.notes, "error": null})
        }
        Err(error) => serde_json::json!({"svg": null, "notes": [], "error": error}),
    }
    .to_string()
}

/// The SVG drawing of a part (its number in view's parts), as JSON:
/// {"svg": ..., "notes": [...], "error": null} or {"svg": null, "error": what is wrong}.
#[wasm_bindgen]
pub fn part_drawing(source: &str, part: usize) -> String {
    drawing_json(nichiyou_daiku_drawing::part_drawing(source, part))
}

/// The drawing of step `step` (from 1), as JSON like part_drawing's.
#[wasm_bindgen]
pub fn step_drawing(source: &str, step: usize) -> String {
    drawing_json(nichiyou_daiku_drawing::step_drawing(source, step))
}

#[cfg(test)]
mod tests {
    #[test]
    fn part_drawing_answers_svg_or_what_is_wrong() {
        let shelf = "(left_side:2x4 =800)\n(right_side:2x4 =800)\n(shelf:2x4 =600)\n\
            left_side -[BL<300 DL<0 D(:8x30)]- shelf\nright_side -[FL<300 TL<0 D(:8x30)]- shelf\n";
        let answer: serde_json::Value =
            serde_json::from_str(&super::part_drawing(shelf, 0)).unwrap();
        assert!(answer["svg"].as_str().unwrap().starts_with("<svg") && answer["error"].is_null());
        assert_eq!(answer["notes"], serde_json::json!([]));
        let missing: serde_json::Value =
            serde_json::from_str(&super::part_drawing(shelf, 7)).unwrap();
        assert!(
            missing["svg"].is_null()
                && missing["error"]
                    .as_str()
                    .unwrap()
                    .starts_with("There is no part 7")
        );
    }

    #[test]
    fn step_drawing_answers_svg_or_what_is_wrong() {
        let three =
            "(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n(c:2x4 =400)\nb -[TF<0 BD<0]- c\n";
        let answer: serde_json::Value =
            serde_json::from_str(&super::step_drawing(three, 2)).unwrap();
        assert!(answer["svg"].as_str().unwrap().starts_with("<svg") && answer["error"].is_null());
        let missing: serde_json::Value =
            serde_json::from_str(&super::step_drawing(three, 3)).unwrap();
        assert_eq!(
            missing["error"],
            "There is no step 3: the design has steps 1 to 2"
        );
        let zero: serde_json::Value = serde_json::from_str(&super::step_drawing(three, 0)).unwrap();
        assert!(zero["svg"].is_null());
    }

    #[test]
    fn view_answers_json_text() {
        let answer = super::view("(a:2x4 =100)");
        let value: serde_json::Value = serde_json::from_str(&answer).unwrap();
        assert_eq!(value["pieces"][0]["id"], "a");
    }
}
