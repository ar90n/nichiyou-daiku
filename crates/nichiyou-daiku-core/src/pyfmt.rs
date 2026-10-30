//! Numbers and strings written as the Python version writes them, so that
//! messages read the same and `validate --json` gives the same values.

/// Python's `repr(float)`: the shortest digits that read back the same,
/// in fixed notation for exponents -4..16 and scientific otherwise.
pub fn repr_f64(value: f64) -> String {
    if let Some(text) = non_finite(value) {
        return text;
    }
    // Rust's `{:e}` gives the same shortest digits, e.g. 1.2345678901234568e16
    let scientific = format!("{value:e}");
    let (mantissa, exponent) = scientific.split_once('e').expect("an exponent");
    let exponent: i32 = exponent.parse().expect("a number");
    let sign = if mantissa.starts_with('-') { "-" } else { "" };
    if (-4..16).contains(&exponent) {
        let digits: String = mantissa.chars().filter(char::is_ascii_digit).collect();
        let point = exponent + 1;
        let fixed = if point <= 0 {
            format!("0.{}{digits}", "0".repeat(point.unsigned_abs() as usize))
        } else if point as usize >= digits.len() {
            format!("{digits}{}.0", "0".repeat(point as usize - digits.len()))
        } else {
            format!(
                "{}.{}",
                &digits[..point as usize],
                &digits[point as usize..]
            )
        };
        format!("{sign}{fixed}")
    } else {
        format!("{mantissa}{}", exponent_text(exponent))
    }
}

/// Python's `format(value, f".{precision}f")`.
pub fn format_fixed(value: f64, precision: usize) -> String {
    if let Some(text) = non_finite(value) {
        return text;
    }
    // Rust rounds the exact binary value half to even, as Python does
    format!("{value:.precision$}")
}

/// Python's `format(value, f".{precision}g")`.
pub fn format_g(value: f64, precision: usize) -> String {
    if let Some(text) = non_finite(value) {
        return text;
    }
    let precision = precision.max(1);
    if value == 0.0 {
        return if value.is_sign_negative() { "-0" } else { "0" }.into();
    }
    let scientific = format!("{:.*e}", precision - 1, value);
    let (mantissa, exponent) = scientific.split_once('e').expect("an exponent");
    let exponent: i32 = exponent.parse().expect("a number");
    if (-4..precision as i32).contains(&exponent) {
        let decimals = (precision as i32 - 1 - exponent) as usize;
        strip_zeros(&format!("{value:.decimals$}"))
    } else {
        format!("{}{}", strip_zeros(mantissa), exponent_text(exponent))
    }
}

/// Python's `repr(str)`.
pub fn repr_str(value: &str) -> String {
    let quote = if value.contains('\'') && !value.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut out = String::from(quote);
    for ch in value.chars() {
        match ch {
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c == quote => {
                out.push('\\');
                out.push(c);
            }
            c if (c as u32) < 0x20 || (0x7f..=0xa0).contains(&(c as u32)) => {
                out.push_str(&format!("\\x{:02x}", c as u32));
            }
            c => out.push(c),
        }
    }
    out.push(quote);
    out
}

/// `round(value, 6) + 0.0` in Python: millimetres to a millionth, without -0.0.
pub fn round_mm(value: f64) -> f64 {
    if !value.is_finite() {
        return value;
    }
    format!("{value:.6}").parse::<f64>().expect("a number") + 0.0
}

/// A length in messages: one decimal (without ".0"), or two significant
/// digits below 0.1mm.
pub fn format_mm(value: f64) -> String {
    if value.abs() >= 0.1 {
        let text = format_fixed(value, 1);
        match text.strip_suffix(".0") {
            Some(whole) => whole.to_string(),
            None => text,
        }
    } else {
        format_g(value, 2)
    }
}

fn non_finite(value: f64) -> Option<String> {
    if value.is_nan() {
        Some("nan".into())
    } else if value.is_infinite() {
        Some(if value > 0.0 { "inf" } else { "-inf" }.into())
    } else {
        None
    }
}

fn exponent_text(exponent: i32) -> String {
    let sign = if exponent < 0 { '-' } else { '+' };
    format!("e{sign}{:02}", exponent.unsigned_abs())
}

fn strip_zeros(text: &str) -> String {
    if text.contains('.') {
        text.trim_end_matches('0').trim_end_matches('.').to_string()
    } else {
        text.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn repr_f64_is_python_repr() {
        let cases = [
            (50.0, "50.0"),
            (0.1, "0.1"),
            (1e-7, "1e-07"),
            (1e16, "1e+16"),
            (123456789012345.0, "123456789012345.0"),
            (1234567890123456.0, "1234567890123456.0"),
            (12345678901234567.0, "1.2345678901234568e+16"),
            (0.0001, "0.0001"),
            (0.00001, "1e-05"),
            (-5.0, "-5.0"),
            (f64::INFINITY, "inf"),
            (f64::NEG_INFINITY, "-inf"),
            (129.66666666666666, "129.66666666666666"),
            (0.30000000000000004, "0.30000000000000004"),
            (-0.0, "-0.0"),
        ];
        for (value, expected) in cases {
            assert_eq!(repr_f64(value), expected, "{value:?}");
        }
        assert_eq!(repr_f64(f64::NAN), "nan");
    }

    #[test]
    fn format_mm_is_the_python_one() {
        let cases = [
            (0.1, "0.1"),
            (12.0, "12"),
            (12.34, "12.3"),
            (0.05, "0.05"),
            (0.0123, "0.012"),
            (0.0001234, "0.00012"),
            (1e-05, "1e-05"),
            (0.0, "0"),
            (2.25, "2.2"),
            (2.35, "2.4"),
            (-3.0, "-3"),
            (1234567.0, "1234567"),
            (0.099999, "0.1"),
            (0.15, "0.1"),
            (-0.04, "-0.04"),
        ];
        for (value, expected) in cases {
            assert_eq!(format_mm(value), expected, "{value:?}");
        }
    }

    #[test]
    fn format_g_is_python_g() {
        let cases = [
            (-5.0, "-5"),
            (0.0, "0"),
            (1e-07, "1e-07"),
            (123456789.0, "1.23457e+08"),
            (2.5, "2.5"),
            (0.000123456, "0.000123456"),
            (100000.0, "100000"),
            (1000000.0, "1e+06"),
        ];
        for (value, expected) in cases {
            assert_eq!(format_g(value, 6), expected, "{value:?}");
        }
    }

    #[test]
    fn round_mm_is_python_round_to_6_digits() {
        let cases = [
            (0.0000005, 0.0),
            (0.0000015, 2e-06),
            (2.675, 2.675),
            (129.666666666666, 129.666667),
            (-0.0000001, 0.0),
            (0.1 + 0.2, 0.3),
            (1234.5678915, 1234.567892),
            (-1e-9, 0.0),
        ];
        for (value, expected) in cases {
            assert_eq!(round_mm(value), expected, "{value:?}");
        }
        // round_mm(-1e-9) is +0.0, not -0.0
        assert!(round_mm(-1e-9).is_sign_positive());
    }

    #[test]
    fn repr_str_is_python_repr() {
        let cases = [
            ("x", "'x'"),
            ("it's", "\"it's\""),
            ("\"a\"", "'\"a\"'"),
            ("a\\b", "'a\\\\b'"),
            ("\n", "'\\n'"),
            ("say \"hi\" it's", "'say \"hi\" it\\'s'"),
            ("日本", "'日本'"),
        ];
        for (value, expected) in cases {
            assert_eq!(repr_str(value), expected, "{value:?}");
        }
    }
}
