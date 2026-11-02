//! The nichiyou-daiku command line (the Python version's cli/dsl_cli.py).

mod echo;
mod fonts;
mod input;
mod load;
mod markdown;
mod pdf;
mod png;
mod render;
mod report;
mod steps;
mod stock;
mod validate;

use std::process::ExitCode;

use clap::{Parser, Subcommand};

use crate::echo::Echo;

/// nichiyou-daiku DSL command line tools.
///
/// Process .nd files to generate 3D models, reports, and more.
#[derive(Parser)]
// click keeps the last of a repeated option, as wrappers adding to defaults expect
#[command(name = "nichiyou-daiku", args_override_self = true)]
struct Cli {
    /// Show tracebacks for unexpected errors
    #[arg(short, long)]
    debug: bool,
    /// Show progress messages
    #[arg(short, long)]
    verbose: bool,
    /// Minimize output
    #[arg(short, long)]
    quiet: bool,
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Validate a DSL file and the model it describes.
    #[command(args_override_self = true)]
    Validate(validate::Args),
    /// Generate a markdown report from DSL file.
    #[command(args_override_self = true)]
    Report(report::Args),
    /// Render a check image (PNG): four labelled views of the model.
    ///
    /// The views look from +z, +y, -x and -x +y +z (the top, the front, the
    /// right side and an isometric view; the furniture's front faces +y), in
    /// the axes of the first piece declared (see validate --json). Each
    /// piece's ID is written where the viewer can see its center; pieces
    /// hidden in every view are listed in the note.
    #[command(args_override_self = true)]
    Render(render::Args),
    /// Write assembly instructions: steps.md, a drawing of each drilled part
    /// and one image per step.
    ///
    /// The parts come first: what to cut, and where to drill each face, from
    /// the reference end marked with a triangle. The steps come from the
    /// file's steps block; without one, each step adds one piece. Each step
    /// image shows what is built so far in grey and the step's pieces in
    /// black, beside a view dimensioning where they go.
    #[command(args_override_self = true)]
    Steps(steps::Args),
}

fn main() -> ExitCode {
    let cli = Cli::parse();
    // Accepted as the Python version's: a Rust error has no traceback to add
    let _ = cli.debug;
    let echo = Echo::new(cli.quiet, cli.verbose);
    ExitCode::from(match &cli.command {
        Commands::Validate(args) => validate::run(args, &echo),
        Commands::Report(args) => report::run(args, &echo),
        Commands::Render(args) => render::run(args, &echo),
        Commands::Steps(args) => steps::run(args, &echo),
    })
}
