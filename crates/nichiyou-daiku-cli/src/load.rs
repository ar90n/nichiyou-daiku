//! Reading, parsing and assembling a design as the commands that draw or
//! report on it do (cli/utils.py: parse_dsl_to_model,
//! create_assembly_from_model): mistakes stop with exit 1, problems warn.

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_core::diagnostics::describe_assembly_issues;
use nichiyou_daiku_core::dsl;

use crate::echo::{Colour, Echo};
use crate::input::read_source;

/// The design's assembly, or the exit code once the mistake is printed.
pub fn assembly(file: &str, echo: &Echo) -> Result<Assembly, u8> {
    let source = read_source(file).map_err(|message| {
        echo.error(&format!("Error: {message}"), None);
        1
    })?;
    echo.verbose("Parsing DSL file...");
    let model = dsl::parse(&source).map_err(|error| {
        echo.error(&format!("DSL Error: {error}"), None);
        1
    })?;
    echo.verbose(&format!(
        "Found {} pieces and {} connections",
        model.pieces.len(),
        model.connections.len()
    ));
    echo.verbose("Creating assembly...");
    let assembly = Assembly::of(model).map_err(|message| {
        echo.error(&format!("Error creating assembly: {message}"), None);
        1
    })?;
    for issue in describe_assembly_issues(&assembly) {
        echo.info(&format!("Warning: {issue}"), Some(Colour::Yellow));
    }
    Ok(assembly)
}
