//! Value checks that read as pydantic's, which the Python version uses.

use std::fmt;

use crate::pyfmt::repr_f64;

/// A value a field does not accept, as pydantic words it.
#[derive(Clone, Debug, PartialEq)]
pub struct FieldError {
    pub field: &'static str,
    pub message: &'static str,
    /// The value as Python's `repr` writes it
    pub input: String,
}

impl fmt::Display for FieldError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}: {} (got {})", self.field, self.message, self.input)
    }
}

impl std::error::Error for FieldError {}

fn reject(field: &'static str, message: &'static str, value: f64) -> FieldError {
    FieldError {
        field,
        message,
        input: repr_f64(value),
    }
}

/// `Field(gt=0, allow_inf_nan=False)`
pub fn positive_finite(field: &'static str, value: f64) -> Result<f64, FieldError> {
    if !value.is_finite() {
        return Err(reject(field, "Input should be a finite number", value));
    }
    if value <= 0.0 {
        return Err(reject(field, "Input should be greater than 0", value));
    }
    Ok(value)
}

/// `Field(ge=0)`
pub fn non_negative(field: &'static str, value: f64) -> Result<f64, FieldError> {
    if value >= 0.0 {
        Ok(value)
    } else {
        Err(reject(
            field,
            "Input should be greater than or equal to 0",
            value,
        ))
    }
}
