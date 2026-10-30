//! The core of nichiyou-daiku: the .nd language, the placement of pieces,
//! fasteners and holes, and the problems `validate` reports.

pub mod anchor;
pub mod assembly;
pub mod connection;
pub mod diagnostics;
pub mod difflib;
pub mod dsl;
pub mod field;
pub mod geometry;
pub mod model;
pub mod piece;
pub mod placement;
pub mod presets;
pub mod pyfmt;
pub mod resolve;

use serde_json::Value;

use assembly::Assembly;
use diagnostics::failure_report;

fn validate_source(source: &str) -> Value {
    let model = match dsl::parse(source) {
        Ok(model) => model,
        Err(error) => {
            return failure_report(
                error.kind.as_str(),
                &error.to_string(),
                error.line,
                error.column,
            );
        }
    };
    match Assembly::of(model) {
        Ok(assembly) => diagnostics::validation_report(&assembly),
        Err(message) => failure_report("assembly", &message, None, None),
    }
}

/// What `nichiyou-daiku validate --json` prints for an .nd source. A panic
/// is a bug, reported as an unexpected error (where panics unwind).
pub fn validate(source: &str) -> Value {
    std::panic::catch_unwind(|| validate_source(source)).unwrap_or_else(|panic| {
        let message = panic
            .downcast_ref::<String>()
            .cloned()
            .or_else(|| panic.downcast_ref::<&str>().map(|text| text.to_string()))
            .unwrap_or_else(|| "the core panicked".into());
        failure_report("unexpected", &message, None, None)
    })
}

/// Every piece's holes and each connection's fasteners, or None when the
/// source does not assemble.
pub fn holes(source: &str) -> Option<Value> {
    let model = dsl::parse(source).ok()?;
    let assembly = Assembly::of(model).ok()?;
    Some(diagnostics::holes_report(&assembly))
}
