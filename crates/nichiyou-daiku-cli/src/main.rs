//! The nichiyou-daiku command line (the Python version's cli/dsl_cli.py).

mod echo;
mod input;
mod markdown;
mod report;
mod validate;

use std::process::ExitCode;

use clap::{Parser, Subcommand};

use crate::echo::Echo;

/// nichiyou-daiku DSL command line tools.
///
/// Process .nd files to generate 3D models, reports, and more.
#[derive(Parser)]
#[command(name = "nichiyou-daiku")]
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
    Validate(validate::Args),
    /// Generate a markdown report from DSL file.
    Report(report::Args),
}

fn main() -> ExitCode {
    let cli = Cli::parse();
    // Accepted as the Python version's: a Rust error has no traceback to add
    let _ = cli.debug;
    let echo = Echo::new(cli.quiet, cli.verbose);
    ExitCode::from(match &cli.command {
        Commands::Validate(args) => validate::run(args, &echo),
        Commands::Report(args) => report::run(args, &echo),
    })
}
