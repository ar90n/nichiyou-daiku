//! The core of nichiyou-daiku: the .nd language, the placement of pieces,
//! fasteners and holes, and the problems `validate` reports.

pub mod field;
pub mod geometry;
pub mod piece;
pub mod presets;
pub mod pyfmt;

use serde_json::{Value, json};

/// What `nichiyou-daiku validate --json` prints for an .nd source.
pub fn validate(source: &str) -> Value {
    let _ = source;
    json!({
        "valid": false,
        "error": {"kind": "unexpected", "message": "not ported yet", "line": null, "column": null},
        "overall_size": null,
        "size_reference": null,
        "pieces": [],
        "problems": [],
    })
}

/// Every piece's holes and each connection's fasteners, or None when the
/// source does not assemble.
pub fn holes(source: &str) -> Option<Value> {
    let _ = source;
    None
}
