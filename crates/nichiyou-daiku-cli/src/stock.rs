//! The board lengths a store sells and the saw kerf, from a TOML file
//! (shell/stock.py), with the same checks and messages:
//!
//! ```toml
//! kerf = 2                         # saw kerf in mm (3 when left out)
//! [lengths]                        # lengths in mm; unlisted types keep the defaults
//! "2x4" = [1820, 2440, 3050, 3650]
//! ```

use nichiyou_daiku_core::cutting::DEFAULT_KERF_MM;
use nichiyou_daiku_core::piece::PieceType;
use nichiyou_daiku_core::pyfmt::{repr_f64, repr_str};
use toml::Value;

use crate::input::python_path;

pub struct Stock {
    pub lengths: Vec<(PieceType, Vec<f64>)>,
    pub kerf: f64,
}

const KEYS: [&str; 2] = ["kerf", "lengths"];

/// The OS's words for an error, as Python's strerror gives them.
fn os_reason(error: &std::io::Error) -> String {
    let text = error.to_string();
    match text.rfind(" (os error ") {
        Some(end) => text[..end].to_string(),
        None => text,
    }
}

/// Python's repr() of what tomllib reads.
fn repr(value: &Value) -> String {
    match value {
        Value::String(text) => repr_str(text),
        Value::Integer(n) => n.to_string(),
        Value::Float(x) => repr_f64(*x),
        Value::Boolean(b) => if *b { "True" } else { "False" }.into(),
        // tomllib reads dates as datetime objects, whose repr no one writes here
        Value::Datetime(date) => date.to_string(),
        Value::Array(items) => format!(
            "[{}]",
            items.iter().map(repr).collect::<Vec<_>>().join(", ")
        ),
        Value::Table(table) => {
            let items: Vec<String> = table
                .iter()
                .map(|(k, v)| format!("{}: {}", repr_str(k), repr(v)))
                .collect();
            format!("{{{}}}", items.join(", "))
        }
    }
}

/// Python's str(): a string as it is, anything else as repr().
fn python_str(value: &Value) -> String {
    match value {
        Value::String(text) => text.clone(),
        other => repr(other),
    }
}

/// A finite number (TOML's true is not one, nor its nan and inf).
fn number(value: &Value) -> Option<f64> {
    match value {
        Value::Integer(n) => Some(*n as f64),
        Value::Float(x) if x.is_finite() => Some(*x),
        _ => None,
    }
}

fn lengths(path: &str, table: &Value) -> Result<Vec<(PieceType, Vec<f64>)>, String> {
    let Value::Table(table) = table else {
        return Err(format!(
            "{path}: [lengths] must be a table of lumber types, e.g. \"2x4\" = [1820, 2440]"
        ));
    };
    let mut out = Vec::new();
    for (name, values) in table {
        if name == "kerf" {
            // TOML puts every key after [lengths] into that table
            return Err(format!(
                "{path}: kerf is inside [lengths]. Move kerf = {} above the [lengths] line",
                python_str(values)
            ));
        }
        let Some(kind) = PieceType::parse(name) else {
            let known: Vec<&str> = PieceType::ALL.iter().map(|kind| kind.as_str()).collect();
            return Err(format!(
                "{path}: Unknown lumber type '{name}' in [lengths]. Use one of: {}",
                known.join(", ")
            ));
        };
        let Value::Array(items) = values else {
            return Err(format!(
                "{path}: '{name}' must be a list of lengths in mm, e.g. \"{name}\" = [1820, 2440]"
            ));
        };
        if items.is_empty() {
            return Err(format!(
                "{path}: '{name}' needs at least one length, e.g. \"{name}\" = [1820]"
            ));
        }
        let Some(numbers) = items
            .iter()
            .map(|item| number(item).filter(|n| *n > 0.0))
            .collect::<Option<Vec<f64>>>()
        else {
            return Err(format!(
                "{path}: '{name}' lengths must be positive numbers in mm, got {}",
                python_str(values)
            ));
        };
        out.push((kind, numbers));
    }
    Ok(out)
}

pub fn load_stock(file: &str) -> Result<Stock, String> {
    let path = python_path(file);
    let bytes = std::fs::read(file)
        .map_err(|e| format!("Cannot read the stock file {path}: {}", os_reason(&e)))?;
    // A byte order mark is fine, as Python's utf-8-sig reads it
    let bytes = bytes.strip_prefix(b"\xef\xbb\xbf").unwrap_or(&bytes);
    let text = std::str::from_utf8(bytes).map_err(|e| {
        format!(
            "{path}: not UTF-8 text (byte {}). Save the file as UTF-8",
            e.valid_up_to()
        )
    })?;
    let data: toml::Table = text.parse().map_err(|e: toml::de::Error| {
        format!(
            "{path}: not valid TOML ({}). Write e.g. kerf = 3 and \"2x4\" = [1820, 2440]",
            e.message().trim_end()
        )
    })?;
    if let Some(key) = data.keys().find(|key| !KEYS.contains(&key.as_str())) {
        return Err(format!(
            "{path}: Unknown key '{key}'. Use 'kerf' and a [lengths] table"
        ));
    }
    let kerf = match data.get("kerf") {
        None => DEFAULT_KERF_MM,
        Some(value) => {
            let Some(kerf) = number(value) else {
                return Err(format!(
                    "{path}: kerf must be a number in mm, got {}",
                    repr(value)
                ));
            };
            if kerf < 0.0 {
                return Err(format!(
                    "{path}: kerf must be 0 or more, got {}",
                    python_str(value)
                ));
            }
            kerf
        }
    };
    let lengths = match data.get("lengths") {
        Some(table) => lengths(&path, table)?,
        None => Vec::new(),
    };
    Ok(Stock { lengths, kerf })
}

#[cfg(test)]
mod tests {
    use super::*;
    use toml::Value;

    #[test]
    fn values_print_as_python_prints_them() {
        let list: Value =
            toml::from_str::<toml::Table>("v = [1820, \"a\", true, -5, 2.5]").unwrap()["v"].clone();
        assert_eq!(repr(&list), "[1820, 'a', True, -5, 2.5]");
        assert_eq!(python_str(&Value::String("3mm".into())), "3mm");
        assert_eq!(repr(&Value::String("3mm".into())), "'3mm'");
    }

    #[test]
    fn the_os_words_its_reasons_without_the_code() {
        let error = std::io::Error::from_raw_os_error(2);
        assert_eq!(os_reason(&error), "No such file or directory");
    }
}
