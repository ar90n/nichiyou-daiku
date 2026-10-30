//! Errors in an .nd source, with where they are.

use std::fmt;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ErrorKind {
    Syntax,
    Semantic,
    Validation,
}

impl ErrorKind {
    /// As `validate --json` names it.
    pub fn as_str(self) -> &'static str {
        match self {
            ErrorKind::Syntax => "syntax",
            ErrorKind::Semantic => "semantic",
            ErrorKind::Validation => "validation",
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct DslError {
    pub kind: ErrorKind,
    pub message: String,
    pub line: Option<usize>,
    pub column: Option<usize>,
}

impl DslError {
    pub fn new(
        kind: ErrorKind,
        message: impl Into<String>,
        at: Option<(usize, usize)>,
    ) -> DslError {
        DslError {
            kind,
            message: message.into(),
            line: at.map(|(line, _)| line),
            column: at.map(|(_, column)| column),
        }
    }
}

impl fmt::Display for DslError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let message = &self.message;
        match (self.kind, self.line, self.column) {
            (ErrorKind::Syntax, Some(l), Some(c)) => {
                write!(f, "Syntax error at line {l}, column {c}: {message}")
            }
            (ErrorKind::Syntax, Some(l), None) => write!(f, "Syntax error at line {l}: {message}"),
            (ErrorKind::Syntax, None, _) => write!(f, "Syntax error: {message}"),
            (_, Some(l), Some(c)) => write!(f, "line {l}, column {c}: {message}"),
            (_, Some(l), None) => write!(f, "line {l}: {message}"),
            (_, None, _) => write!(f, "{message}"),
        }
    }
}

impl std::error::Error for DslError {}
