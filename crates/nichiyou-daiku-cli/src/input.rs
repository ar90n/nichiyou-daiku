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
