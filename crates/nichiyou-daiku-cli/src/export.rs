//! `export` (cli/commands/export.py): the design's 3D as STL or STEP.

use std::path::Path;

use nichiyou_daiku_export::{mesh::mesh, model, step::step, stl::stl};

use crate::echo::{Colour, Echo};
use crate::input::{python_path, refuse_overwrite, require_output};
use crate::load;

#[derive(clap::Args)]
pub struct Args {
    /// Path to .nd file or '-' for stdin
    file: String,
    /// Output file path. If not specified, uses the input filename with the format's extension (required when reading from stdin). Never overwrites the input file.
    #[arg(short, long)]
    output: Option<String>,
    /// Export format. If not specified, detected from the output file extension (.stl, .step, .stp). An error is raised if it contradicts the output extension.
    #[arg(short, long, ignore_case = true, value_parser = ["stl", "step", "stp"])]
    format: Option<String>,
    /// Accepted as before; boards are exported with square edges
    #[arg(long, default_value_t = 5.0)]
    fillet_radius: f64,
}

#[derive(Clone, Copy, PartialEq)]
enum Format {
    Stl,
    Step,
}

fn detect(output: &str) -> (String, Option<Format>) {
    let extension = Path::new(output)
        .extension()
        .map_or(String::new(), |e| format!(".{}", e.to_string_lossy()));
    let format = match extension.to_ascii_lowercase().as_str() {
        ".stl" => Some(Format::Stl),
        ".step" | ".stp" => Some(Format::Step),
        _ => None,
    };
    (extension, format)
}

/// Where to write and in which format (export.py: resolve_export_target).
fn target(
    file: &str,
    output: &Option<String>,
    format: &Option<String>,
) -> Result<(String, Format), String> {
    let Some(asked) = format.as_ref().map(|f| f.to_ascii_lowercase()) else {
        let Some(output) = output else {
            return Err("Either output file (-o) or format (-f) must be specified.".into());
        };
        let (extension, detected) = detect(output);
        return detected.map(|f| (output.clone(), f)).ok_or(format!(
            "Cannot detect format from extension '{extension}'. Please specify format with -f option."
        ));
    };
    let requested = if asked == "stl" {
        Format::Stl
    } else {
        Format::Step
    };
    let Some(output) = output else {
        let path = Path::new(file).with_extension(&asked);
        return Ok((path.to_string_lossy().into_owned(), requested));
    };
    let (extension, detected) = detect(output);
    if detected.is_some_and(|d| d != requested) {
        return Err(format!(
            "Output extension '{extension}' does not match format '{asked}'."
        ));
    }
    Ok((output.clone(), requested))
}

pub fn run(args: &Args, echo: &Echo) -> u8 {
    if let Err(message) = require_output(&args.file, &args.output) {
        echo.error(&format!("Error: {message}"), None);
        return 1;
    }
    let (output, format) = match target(&args.file, &args.output, &args.format) {
        Ok(target) => target,
        Err(message) => {
            echo.error(&format!("Error: {message}"), None);
            return 1;
        }
    };
    if let Err(message) = refuse_overwrite(&args.file, Path::new(&output)) {
        echo.error(&format!("Error: {message}"), None);
        return 1;
    }
    let assembly = match load::assembly(&args.file, echo) {
        Ok(assembly) => assembly,
        Err(code) => return code,
    };
    let made = model(&assembly);
    for warning in &made.warnings {
        echo.info(&format!("Warning: {warning}"), Some(Colour::Yellow));
    }
    let bytes = match format {
        Format::Stl => stl(&made.solids.iter().map(mesh).collect::<Vec<_>>()),
        Format::Step => {
            let named = if args.file == "-" {
                &output
            } else {
                &args.file
            };
            let title = Path::new(named)
                .file_name()
                .map_or(String::new(), |n| n.to_string_lossy().into_owned());
            let timestamp = jiff::Zoned::now().strftime("%Y-%m-%dT%H:%M:%S").to_string();
            step(&made.solids, &title, &timestamp, env!("CARGO_PKG_VERSION")).into_bytes()
        }
    };
    if let Err(e) = std::fs::write(&output, bytes) {
        echo.error(
            &format!(
                "Error exporting file: cannot write {}: {e}",
                python_path(&output)
            ),
            None,
        );
        return 1;
    }
    echo.info(
        &format!("Successfully exported to: {}", python_path(&output)),
        None,
    );
    0
}
