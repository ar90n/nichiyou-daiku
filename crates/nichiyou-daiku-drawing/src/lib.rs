//! Line drawings of nichiyou-daiku designs, as SVG in page mm.

pub mod chain;
pub mod part_sheet;
pub mod solid;
pub mod svg;
pub mod text;

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_core::parts::{part_groups, part_name};

/// The SVG drawing of the parts list's part `part`, or what is wrong.
pub fn part_drawing(source: &str, part: usize) -> Result<String, String> {
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
    Ok(part_sheet::part_sheet(&assembly, group).svg)
}
