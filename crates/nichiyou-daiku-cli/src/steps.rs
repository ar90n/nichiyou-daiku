//! `steps` (cli/commands/steps.py): steps.md, a drawing of each drilled
//! part and one image per step, in one folder.

use std::path::{Path, PathBuf};

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_core::parts::part_groups;
use nichiyou_daiku_core::steps::{grouping_hint, plan_steps};
use nichiyou_daiku_drawing::instructions::{image_name, steps_markdown};
use nichiyou_daiku_drawing::part_sheet::part_sheet;
use nichiyou_daiku_drawing::step_sheet::step_sheet;

use crate::echo::{Colour, Echo};
use crate::input::{python_path, require_output};
use crate::load;
use crate::png::png;

#[derive(clap::Args)]
pub struct Args {
    /// Path to .nd file or '-' for stdin
    file: String,
    /// Directory for steps.md, the part drawings and the step images (default: <input>-steps, required for stdin).
    #[arg(short, long)]
    output: Option<String>,
    /// Width of each image in pixels.
    #[arg(long, default_value_t = 1600, value_parser = clap::value_parser!(u32).range(400..))]
    size: u32,
    /// Accepted as before; boards are drawn with square edges
    #[arg(long, default_value_t = 5.0)]
    fillet_radius: f64,
}

/// What was written and what the user should hear about it.
struct Written {
    drawings: usize,
    images: usize,
    crowded: Vec<String>,
    hint: Option<String>,
}

/// part-NN.png or step-NN.png, as an earlier run named its images.
fn is_image(name: &str) -> bool {
    let Some(rest) = name
        .strip_prefix("part-")
        .or_else(|| name.strip_prefix("step-"))
    else {
        return false;
    };
    rest.strip_suffix(".png")
        .is_some_and(|digits| !digits.is_empty() && digits.bytes().all(|b| b.is_ascii_digit()))
}

fn write(assembly: &Assembly, directory: &Path, title: &str, size: u32) -> Result<Written, String> {
    let plan = plan_steps(assembly);
    let groups = part_groups(assembly);
    // A part without holes is only cut to length: the table is enough
    let drawn: Vec<usize> = (0..groups.len())
        .filter(|&i| !groups[i].holes.is_empty())
        .collect();
    std::fs::create_dir_all(directory).map_err(|e| e.to_string())?;
    let save = |name: &str, svg: &str| {
        std::fs::write(directory.join(name), png(svg, size)?).map_err(|e| e.to_string())
    };
    let (mut files, mut crowded) = (Vec::new(), Vec::new());
    for (number, &index) in drawn.iter().enumerate() {
        let sheet = part_sheet(assembly, &groups, index);
        let name = image_name("part", number + 1, drawn.len());
        save(&name, &sheet.svg)?;
        crowded.extend(sheet.crowded);
        files.push(name);
    }
    for step in &plan.steps {
        let sheet = step_sheet(assembly, step);
        let name = image_name("step", step.number, plan.steps.len());
        save(&name, &sheet.svg)?;
        crowded.extend(sheet.notes);
        files.push(name);
    }
    std::fs::write(
        directory.join("steps.md"),
        steps_markdown(assembly, &plan, title),
    )
    .map_err(|e| e.to_string())?;
    // An old image would pass for a part or a step of this design
    for entry in std::fs::read_dir(directory).map_err(|e| e.to_string())? {
        let name = entry
            .map_err(|e| e.to_string())?
            .file_name()
            .to_string_lossy()
            .into_owned();
        if is_image(&name) && !files.contains(&name) {
            std::fs::remove_file(directory.join(&name)).map_err(|e| e.to_string())?;
        }
    }
    Ok(Written {
        drawings: drawn.len(),
        images: plan.steps.len(),
        crowded,
        hint: grouping_hint(&plan),
    })
}

fn count(n: usize, thing: &str) -> String {
    format!("{n} {thing}{}", if n == 1 { "" } else { "s" })
}

pub fn run(args: &Args, echo: &Echo) -> u8 {
    if let Err(message) = require_output(&args.file, &args.output) {
        echo.error(&format!("Error: {message}"), None);
        return 1;
    }
    let input = Path::new(&args.file);
    let stem = input
        .file_stem()
        .map_or(String::new(), |s| s.to_string_lossy().into_owned());
    let directory = match &args.output {
        Some(output) => PathBuf::from(output),
        None => input.with_file_name(format!("{stem}-steps")),
    };
    let shown = python_path(&directory.to_string_lossy());
    if directory.exists() && !directory.is_dir() {
        echo.error(
            &format!("{shown} is a file; give -o a directory for the steps"),
            None,
        );
        return 1;
    }
    let title = if args.file == "-" {
        directory
            .file_name()
            .map_or(String::new(), |name| name.to_string_lossy().into_owned())
    } else {
        stem
    };
    let assembly = match load::assembly(&args.file, echo) {
        Ok(assembly) => assembly,
        Err(code) => return code,
    };
    let written = match write(&assembly, &directory, &title, args.size) {
        Ok(written) => written,
        Err(message) => {
            echo.error(&format!("Error writing the steps: {message}"), None);
            return 1;
        }
    };
    if let Some(hint) = &written.hint {
        echo.info(hint, None);
    }
    for message in &written.crowded {
        echo.info(&format!("Warning: {message}"), Some(Colour::Yellow));
    }
    let mut listed = vec!["steps.md".to_string()];
    if written.drawings > 0 {
        listed.push(count(written.drawings, "part drawing"));
    }
    let images = count(written.images, "step image");
    echo.info(
        &format!(
            "Successfully wrote {} and {images} to {shown}",
            listed.join(", ")
        ),
        None,
    );
    0
}
