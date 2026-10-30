//! The .nd language.

pub mod lexer;

pub mod ast;
pub mod error;
pub mod eval;
pub mod parser;

/// The model of an .nd source with its unknowns solved, or the first error
/// in it.
pub fn parse(source: &str) -> Result<crate::model::Model, error::DslError> {
    let statements = parser::parse_statements(source)?;
    let located = eval::evaluate(&statements)?;
    crate::resolve::resolve_model(located.model).map_err(|error| {
        // At the piece or connection the error names, else at the first token
        let pos = match (&error.piece_id, &error.connection) {
            (Some(id), _) => located.pieces.get(id),
            (None, Some(key)) => located.connections.get(key),
            (None, None) => None,
        }
        .copied()
        .unwrap_or(located.start);
        error::DslError::new(
            error::ErrorKind::Validation,
            error.message,
            Some((pos.line, pos.column)),
        )
    })
}
