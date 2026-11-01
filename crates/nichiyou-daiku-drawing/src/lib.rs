//! Line drawings of nichiyou-daiku designs, as SVG in page mm.

pub mod chain;
pub mod hidden;
pub mod part_sheet;
pub mod solid;
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

/// The drawing of the parts list's part `part`, or what is wrong.
pub fn part_drawing(source: &str, part: usize) -> Result<Drawing, String> {
    let model = nichiyou_daiku_core::dsl::parse(source)
        .map_err(|e| format!("The design does not read: {e}. Fix it in the source first"))?;
    let assembly = Assembly::of(model)?;
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
    let sheet = part_sheet::part_sheet(&assembly, group);
    Ok(Drawing {
        svg: sheet.svg,
        notes: sheet.crowded,
    })
}
