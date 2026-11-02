//! Reading the design (cli/utils.py: read_dsl_file): a file, or '-' for stdin.

use std::io::Read;
use std::path::Path;

/// Python reads text with universal newlines: "\r\n" and "\r" become "\n".
fn universal_newlines(text: &str) -> String {
    text.replace("\r\n", "\n").replace('\r', "\n")
}

pub fn read_source(file: &str) -> Result<String, String> {
    if file == "-" {
        let mut text = String::new();
        std::io::stdin()
            .read_to_string(&mut text)
            .map_err(|e| format!("Error reading file: {e}"))?;
        return Ok(universal_newlines(&text));
    }
    let path = Path::new(file);
    if !path.exists() {
        return Err(format!("File not found: {file}"));
    }
    if !path.is_file() {
        return Err(format!("Not a file: {file}"));
    }
    std::fs::read_to_string(path)
        .map(|text| universal_newlines(&text))
        .map_err(|e| format!("Error reading file: {e}"))
}

/// stdin has no name to make the output's from (cli/utils.py:
/// require_output_for_stdin).
pub fn require_output(file: &str, output: &Option<String>) -> Result<(), String> {
    if file == "-" && output.is_none() {
        return Err("An output file (-o) is required when reading from stdin ('-').".into());
    }
    Ok(())
}

/// The output must not be the design (cli/utils.py:
/// ensure_not_overwriting_input).
pub fn refuse_overwrite(file: &str, output: &Path) -> Result<(), String> {
    let same = file != "-"
        && match (std::fs::canonicalize(file), std::fs::canonicalize(output)) {
            (Ok(a), Ok(b)) => a == b,
            // An output that is not there yet is not the design
            _ => false,
        };
    if same {
        return Err(format!(
            "Refusing to overwrite the input file: {file}. Choose a different output path with -o."
        ));
    }
    Ok(())
}

/// The path as Python's pathlib prints it: no empty or '.' parts, no
/// trailing slash.
pub fn python_path(text: &str) -> String {
    let parts: Vec<&str> = text
        .split('/')
        .filter(|part| !part.is_empty() && *part != ".")
        .collect();
    match (text.starts_with('/'), parts.is_empty()) {
        (true, _) => format!("/{}", parts.join("/")),
        (false, true) => ".".into(),
        (false, false) => parts.join("/"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn windows_line_ends_read_as_python_reads_them() {
        assert_eq!(universal_newlines("a\r\nb\rc\n"), "a\nb\nc\n");
    }

    #[test]
    fn paths_print_as_pathlib_prints_them() {
        assert_eq!(python_path("./a//b/./c.toml"), "a/b/c.toml");
        assert_eq!(python_path("a/"), "a");
        assert_eq!(python_path("/x/y"), "/x/y");
        assert_eq!(python_path("."), ".");
    }
}
