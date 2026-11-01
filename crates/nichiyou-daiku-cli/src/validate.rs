//! `validate` (cli/commands/validate.py): check the syntax, assemble, and
//! list the problems; with --json, the same for tools and agents.

use std::io::Write;

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_core::diagnostics::{collect_problems, failure_report};
use nichiyou_daiku_core::dsl;
use nichiyou_daiku_core::pyfmt::repr_f64;

use crate::echo::{Colour, Echo};
use crate::input::read_source;

#[derive(clap::Args)]
pub struct Args {
    /// Path to .nd file or '-' for stdin
    file: String,
    /// Print the result as one JSON object (problems, piece positions, overall size) for tools and agents.
    #[arg(long)]
    json: bool,
}

fn label(kind: &str) -> &'static str {
    match kind {
        "syntax" => "Syntax error",
        "semantic" => "Semantic error",
        "validation" => "Validation error",
        _ => "Unexpected error",
    }
}

fn failed(echo: &Echo, label: &str, message: &str) -> u8 {
    echo.error(&format!("✗ {label}"), Some(Colour::Red));
    echo.error(&format!("\n{message}"), None);
    1
}

fn json(file: &str) -> u8 {
    let report = match read_source(file) {
        Ok(source) => nichiyou_daiku_core::validate(&source),
        Err(message) => failure_report("file", &message, None, None),
    };
    // Not through Echo: the JSON is the output even with --quiet
    let text = serde_json::to_string_pretty(&report).expect("a report is JSON");
    let _ = writeln!(std::io::stdout(), "{text}");
    if report["valid"] == true { 0 } else { 1 }
}

pub fn run(args: &Args, echo: &Echo) -> u8 {
    if args.json {
        return json(&args.file);
    }
    let source = match read_source(&args.file) {
        Ok(source) => source,
        Err(message) => {
            echo.error(&format!("Error: {message}"), None);
            return 1;
        }
    };
    let model = match dsl::parse(&source) {
        Ok(model) => model,
        Err(error) => return failed(echo, label(error.kind.as_str()), &error.to_string()),
    };
    echo.echo("✓ DSL syntax is valid", Some(Colour::Green));
    echo.verbose("\nModel summary:");
    echo.verbose(&format!("  Pieces: {}", model.pieces.len()));
    echo.verbose(&format!("  Connections: {}", model.connections.len()));
    if !model.pieces.is_empty() {
        echo.verbose("\nPieces:");
        for piece in &model.pieces {
            let length = piece.length.map_or("None".into(), repr_f64);
            echo.verbose(&format!(
                "  - {}: {} @ {length}mm",
                piece.id,
                piece.kind.as_str()
            ));
        }
    }
    let assembly = match Assembly::of(model) {
        Ok(assembly) => assembly,
        Err(message) => return failed(echo, "Assembly error", &message),
    };
    let problems = collect_problems(&assembly);
    if !problems.is_empty() {
        echo.error("✗ Model has problems", Some(Colour::Red));
        for problem in &problems {
            echo.error(
                &format!("  - {}", problem["message"].as_str().unwrap_or_default()),
                None,
            );
        }
        return 1;
    }
    echo.echo("✓ Model is valid", Some(Colour::Green));
    0
}
