//! `drawing` (cli/commands/drawing.py): the technical drawing as a PDF, or
//! an SVG when the output is named so.

use std::path::Path;

use nichiyou_daiku_drawing::technical::{Page, Titles, technical_drawing};

use crate::echo::{Colour, Echo};
use crate::input::{python_path, refuse_overwrite, require_output};
use crate::load;
use crate::pdf::pdf;

#[derive(clap::Args)]
pub struct Args {
    /// Path to .nd file or '-' for stdin
    file: String,
    /// Output file path (default: <input>.pdf, required for stdin). Use a .svg extension to write SVG instead of PDF.
    #[arg(short, long)]
    output: Option<String>,
    /// Drawing title (default: input filename)
    #[arg(long)]
    title: Option<String>,
    /// Drawing number (default: ND-1)
    #[arg(long, default_value = "ND-1")]
    drawing_number: String,
    /// Designer name (default: nichiyou-daiku)
    #[arg(long, default_value = "nichiyou-daiku")]
    designed_by: String,
    /// Drawing page size (default: A3)
    #[arg(long, default_value = "A3", ignore_case = true, value_parser = ["A4", "A3", "A2", "A1"])]
    page_size: String,
    /// Leave out the dimensions (overall size and where the pieces go)
    #[arg(long)]
    no_dimensions: bool,
}

fn stem(path: &str) -> String {
    Path::new(path)
        .file_stem()
        .map_or(String::new(), |s| s.to_string_lossy().into_owned())
}

pub fn run(args: &Args, echo: &Echo) -> u8 {
    if let Err(message) = require_output(&args.file, &args.output) {
        echo.error(&format!("Error: {message}"), None);
        return 1;
    }
    let output = args.output.clone().unwrap_or_else(|| {
        Path::new(&args.file)
            .with_extension("pdf")
            .to_string_lossy()
            .into_owned()
    });
    if let Err(message) = refuse_overwrite(&args.file, Path::new(&output)) {
        echo.error(&format!("Error: {message}"), None);
        return 1;
    }
    let svg_only = Path::new(&output)
        .extension()
        .is_some_and(|e| e.eq_ignore_ascii_case("svg"));
    let title = args.title.clone().unwrap_or_else(|| {
        if args.file == "-" {
            stem(&output)
        } else {
            stem(&args.file)
        }
    });
    let assembly = match load::assembly(&args.file, echo) {
        Ok(assembly) => assembly,
        Err(code) => return code,
    };
    let parts = assembly.placement.groups.len();
    if !args.no_dimensions && parts > 1 {
        // Dimensions measure the whole model, which has no size when its
        // parts' places relative to each other are undefined
        echo.info(
            &format!(
                "Warning: the drawing has no dimensions: the pieces are in {parts} separate parts. Connect them to dimension it"
            ),
            Some(Colour::Yellow),
        );
    }
    let date = jiff::Zoned::now().strftime("%Y-%m-%d").to_string();
    let titles = Titles {
        title: &title,
        drawing_number: &args.drawing_number,
        designed_by: &args.designed_by,
        date: &date,
    };
    let page = Page::named(&args.page_size).expect("clap takes only the page sizes");
    let sheet = technical_drawing(&assembly, page, &titles, !args.no_dimensions);
    for message in &sheet.dimensions.crowded {
        echo.info(&format!("Warning: {message}"), Some(Colour::Yellow));
    }
    let cannot = |e: std::io::Error| format!("cannot write {}: {e}", python_path(&output));
    let written = if svg_only {
        std::fs::write(&output, &sheet.svg)
            .map_err(cannot)
            .map_err(|m| format!("Error exporting SVG: {m}"))
    } else {
        pdf(&sheet.svg)
            .and_then(|bytes| std::fs::write(&output, bytes).map_err(cannot))
            .map_err(|m| format!("Error converting to PDF: {m}"))
    };
    if let Err(message) = written {
        echo.error(&message, None);
        return 1;
    }
    echo.info(
        &format!(
            "Successfully created technical drawing: {}",
            python_path(&output)
        ),
        None,
    );
    0
}
