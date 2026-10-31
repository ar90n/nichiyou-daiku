//! The core for JavaScript: one function, an .nd source in, the view JSON out.

use wasm_bindgen::prelude::wasm_bindgen;

/// The view JSON of an .nd source (see the core's `view`).
#[wasm_bindgen]
pub fn view(source: &str) -> String {
    nichiyou_daiku_core::view(source).to_string()
}

#[cfg(test)]
mod tests {
    #[test]
    fn view_answers_json_text() {
        let answer = super::view("(a:2x4 =100)");
        let value: serde_json::Value = serde_json::from_str(&answer).unwrap();
        assert_eq!(value["pieces"][0]["id"], "a");
    }
}
