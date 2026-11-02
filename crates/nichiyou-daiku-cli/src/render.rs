//! `render` (cli/commands/render.py): the check image, four labelled views
//! of the model, as a PNG.

use std::path::Path;

use nichiyou_daiku_drawing::render::render_sheet;

use crate::echo::Echo;
use crate::input::{python_path, refuse_overwrite, require_output};
use crate::load;
use crate::png::png;

#[derive(clap::Args)]
pub struct Args {
    /// Path to .nd file or '-' for stdin
    file: String,
    /// Output PNG path (default: <input>.png, required for stdin).
    #[arg(short, long)]
    output: Option<String>,
    /// Width and height of the image in pixels.
    #[arg(long, default_value_t = 1400, value_parser = clap::value_parser!(u32).range(400..))]
    size: u32,
    /// Accepted as before; boards are drawn with square edges
    #[arg(long, default_value_t = 5.0)]
    fillet_radius: f64,
}

pub fn run(args: &Args, echo: &Echo) -> u8 {
    if let Err(message) = require_output(&args.file, &args.output) {
        echo.error(&format!("Error: {message}"), None);
        return 1;
    }
    let output = args.output.clone().unwrap_or_else(|| {
        Path::new(&args.file)
            .with_extension("png")
            .to_string_lossy()
            .into_owned()
    });
    if let Err(message) = refuse_overwrite(&args.file, Path::new(&output)) {
        echo.error(&format!("Error: {message}"), None);
        return 1;
    }
    let named = if args.file == "-" {
        &output
    } else {
        &args.file
    };
    let title = Path::new(named)
        .file_name()
        .map_or(String::new(), |name| name.to_string_lossy().into_owned());
    let assembly = match load::assembly(&args.file, echo) {
        Ok(assembly) => assembly,
        Err(code) => return code,
    };
    let sheet = render_sheet(&assembly, &title, args.size);
    let written = png(&sheet.svg, args.size)
        .and_then(|image| std::fs::write(&output, image).map_err(|e| e.to_string()));
    if let Err(message) = written {
        echo.error(&format!("Error rendering the image: {message}"), None);
        return 1;
    }
    echo.info(
        &format!("Successfully rendered: {}", python_path(&output)),
        None,
    );
    0
}
