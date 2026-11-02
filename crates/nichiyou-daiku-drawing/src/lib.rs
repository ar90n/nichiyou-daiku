//! Line drawings of nichiyou-daiku designs, as SVG in page mm.

pub mod chain;
pub mod hidden;
pub mod instructions;
pub mod labels;
pub mod part_sheet;
pub mod solid;
pub mod step_sheet;
pub mod svg;
pub mod text;
pub mod views;

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_core::parts::{part_groups, part_name};

/// A part's drawing, and what to tell about it: values that do not fit, as
/// the CLI warns.
#[derive(Debug)]
pub struct Drawing {
    pub svg: String,
    pub notes: Vec<String>,
}

fn assemble(source: &str) -> Result<Assembly, String> {
    let model = nichiyou_daiku_core::dsl::parse(source)
        .map_err(|e| format!("The design does not read: {e}. Fix it in the source first"))?;
    Assembly::of(model)
}

/// The drawing of step `step` (from 1), or what is wrong.
pub fn step_drawing(source: &str, step: usize) -> Result<Drawing, String> {
    let assembly = assemble(source)?;
    let plan = nichiyou_daiku_core::steps::plan_steps(&assembly);
    let count = plan.steps.len();
    let planned = step
        .checked_sub(1)
        .and_then(|i| plan.steps.get(i))
        .ok_or_else(|| format!("There is no step {step}: the design has steps 1 to {count}"))?;
    let sheet = step_sheet::step_sheet(&assembly, planned);
    Ok(Drawing {
        svg: sheet.svg,
        notes: sheet.notes,
    })
}

/// The drawing of the parts list's part `part`, or what is wrong.
pub fn part_drawing(source: &str, part: usize) -> Result<Drawing, String> {
    let assembly = assemble(source)?;
    let groups = part_groups(&assembly);
    let group = groups.get(part).ok_or_else(|| {
        format!(
            "There is no part {part}: the parts list has {} parts",
            groups.len()
        )
    })?;
    if group.holes.is_empty() {
        return Err(format!(
            "{} has no holes, so it has no drawing: it is only cut to length",
            part_name(group)
        ));
    }
    let sheet = part_sheet::part_sheet(&assembly, &groups, part);
    Ok(Drawing {
        svg: sheet.svg,
        notes: sheet.crowded,
    })
}
