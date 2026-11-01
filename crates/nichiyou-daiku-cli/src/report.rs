//! `report` (cli/commands/report.py): the Markdown report of what a design
//! takes to build.

use std::io::Write;
use std::path::Path;

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_core::cutting::DEFAULT_KERF_MM;
use nichiyou_daiku_core::dsl;
use nichiyou_daiku_core::resources::extract_resources;

use crate::echo::{Colour, Echo};
use crate::input::{python_path, read_source};
use crate::markdown::{Options, report};

#[derive(clap::Args)]
pub struct Args {
    /// Path to .nd file or '-' for stdin
    file: String,
    /// Output file path (default: stdout)
    #[arg(short, long)]
    output: Option<String>,
    /// Project name for report
    #[arg(long, default_value = "Woodworking Project")]
    project_name: String,
    /// Include cut diagram in report
    #[arg(long, overrides_with = "no_cut_diagram")]
    include_cut_diagram: bool,
    /// Leave out the cut diagram
    #[arg(long, overrides_with = "include_cut_diagram")]
    no_cut_diagram: bool,
    /// Include anchor details in report
    #[arg(long, overrides_with = "no_anchor_details")]
    include_anchor_details: bool,
    /// Leave out the anchor details
    #[arg(long, overrides_with = "include_anchor_details")]
    no_anchor_details: bool,
    /// Include pilot holes drilling guide in report
    #[arg(long, overrides_with = "no_pilot_holes")]
    include_pilot_holes: bool,
    /// Leave out the pilot holes drilling guide
    #[arg(long, overrides_with = "include_pilot_holes")]
    no_pilot_holes: bool,
    /// TOML file with the board lengths your store sells and the saw kerf (default: 1820, 2440, 3050 and 3650mm boards, 3mm kerf)
    #[arg(long)]
    stock: Option<String>,
}

fn write_report(output: &str, text: &str, echo: &Echo) -> u8 {
    let path = Path::new(output);
    if let Some(folder) = path
        .parent()
        .filter(|f| !f.as_os_str().is_empty() && !f.exists())
        && let Err(e) = std::fs::create_dir_all(folder)
    {
        echo.error(&format!("Error: Cannot create output directory: {e}"), None);
        return 1;
    }
    if path.exists() && !path.is_file() {
        echo.error(&format!("Error: Output path is not a file: {output}"), None);
        return 1;
    }
    if let Err(e) = std::fs::write(path, text) {
        echo.error(&format!("Error writing output: {e}"), None);
        return 1;
    }
    echo.info(&format!("Report written to: {}", python_path(output)), None);
    0
}

pub fn run(args: &Args, echo: &Echo) -> u8 {
    let (lengths, kerf) = (Vec::new(), DEFAULT_KERF_MM);
    let source = match read_source(&args.file) {
        Ok(source) => source,
        Err(message) => {
            echo.error(&format!("Error: {message}"), None);
            return 1;
        }
    };
    echo.verbose("Parsing DSL file...");
    let model = match dsl::parse(&source) {
        Ok(model) => model,
        Err(error) => {
            echo.error(&format!("DSL Error: {error}"), None);
            return 1;
        }
    };
    echo.verbose(&format!(
        "Found {} pieces and {} connections",
        model.pieces.len(),
        model.connections.len()
    ));
    echo.verbose("Creating assembly...");
    let assembly = match Assembly::of(model) {
        Ok(assembly) => assembly,
        Err(message) => {
            echo.error(&format!("Error creating assembly: {message}"), None);
            return 1;
        }
    };
    let summary = extract_resources(&assembly);
    for issue in &summary.issues {
        echo.info(&format!("Warning: {issue}"), Some(Colour::Yellow));
    }
    echo.verbose("Extracting resources...");
    echo.verbose("Generating report...");
    let generated_on = jiff::Zoned::now().strftime("%Y-%m-%d %H:%M").to_string();
    let text = report(
        &summary,
        &Options {
            project_name: &args.project_name,
            generated_on: &generated_on,
            // overrides_with keeps only the last of each pair
            cut_diagram: args.include_cut_diagram || !args.no_cut_diagram,
            anchor_details: args.include_anchor_details || !args.no_anchor_details,
            pilot_holes: args.include_pilot_holes || !args.no_pilot_holes,
            lengths: &lengths,
            kerf,
        },
    );
    match &args.output {
        Some(output) => write_report(output, &text, echo),
        None => {
            let _ = writeln!(std::io::stdout(), "{text}");
            0
        }
    }
}
