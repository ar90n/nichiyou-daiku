//! The core for JavaScript: one function, an .nd source in, the view JSON out.

use wasm_bindgen::prelude::wasm_bindgen;

/// The view JSON of an .nd source (see the core's `view`).
#[wasm_bindgen]
pub fn view(source: &str) -> String {
    nichiyou_daiku_core::view(source).to_string()
}

/// The SVG drawing of a part (its number in view's parts), as JSON:
/// {"svg": ..., "error": null} or {"svg": null, "error": what is wrong}.
#[wasm_bindgen]
pub fn part_drawing(source: &str, part: usize) -> String {
    match nichiyou_daiku_drawing::part_drawing(source, part) {
        Ok(drawing) => {
            serde_json::json!({"svg": drawing.svg, "notes": drawing.notes, "error": null})
        }
        Err(error) => serde_json::json!({"svg": null, "notes": [], "error": error}),
    }
    .to_string()
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
    fn view_answers_json_text() {
        let answer = super::view("(a:2x4 =100)");
        let value: serde_json::Value = serde_json::from_str(&answer).unwrap();
        assert_eq!(value["pieces"][0]["id"], "a");
    }
}
