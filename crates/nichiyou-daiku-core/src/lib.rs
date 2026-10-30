//! The core of nichiyou-daiku: the .nd language, the placement of pieces,
//! fasteners and holes, and the problems `validate` reports.

pub mod anchor;
pub mod connection;
pub mod difflib;
pub mod dsl;
pub mod field;
pub mod geometry;
pub mod model;
pub mod piece;
pub mod placement;
pub mod presets;
pub mod pyfmt;

use serde_json::{Value, json};

fn failure(kind: &str, message: &str, line: Option<usize>, column: Option<usize>) -> Value {
    json!({
        "valid": false,
        "error": {"kind": kind, "message": message, "line": line, "column": column},
        "overall_size": null,
        "size_reference": null,
        "pieces": [],
        "problems": [],
    })
}

/// What `nichiyou-daiku validate --json` prints for an .nd source.
pub fn validate(source: &str) -> Value {
    match dsl::parse(source) {
        Err(error) => failure(
            error.kind.as_str(),
            &error.to_string(),
            error.line,
            error.column,
        ),
        Ok(_) => failure("unexpected", "not ported yet", None, None),
    }
}

/// Every piece's holes and each connection's fasteners, or None when the
/// source does not assemble.
pub fn holes(source: &str) -> Option<Value> {
    let _ = source;
    None
}
