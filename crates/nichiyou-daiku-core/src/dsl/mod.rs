//! The .nd language.

pub mod lexer;

pub mod ast;
pub mod error;
pub mod eval;
pub mod parser;

/// The model of an .nd source, or the first error in it.
pub fn parse(source: &str) -> Result<crate::model::Model, error::DslError> {
    let statements = parser::parse_statements(source)?;
    Ok(eval::evaluate(&statements)?.model)
}
