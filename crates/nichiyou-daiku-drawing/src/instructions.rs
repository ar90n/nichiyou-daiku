//! The instructions page (shell/instructions.py: steps_markdown): the parts
//! to make, then per step its heading, image, pieces and fasteners. No prose:
//! the images and numbers tell how.

use nichiyou_daiku_core::assembly::Assembly;
use nichiyou_daiku_core::hardware::count_hardware;
use nichiyou_daiku_core::parts::{PartGroup, part_groups, part_name};
use nichiyou_daiku_core::pyfmt::format_mm;
use nichiyou_daiku_core::steps::{StepPlan, grouping_hint};

use crate::step_sheet::heading;

/// part-01.png, step-01.png, …: wide enough for every number.
pub fn image_name(kind: &str, number: usize, count: usize) -> String {
    let digits = count.to_string().len().max(2);
    format!("{kind}-{number:0digits$}.png")
}

/// Every part's lumber, length and count, then the drawings of the drilled
/// ones.
fn parts(assembly: &Assembly) -> Vec<String> {
    let groups = part_groups(assembly);
    // A part without holes is only cut to length: the table is enough
    let drawn: Vec<&PartGroup> = groups.iter().filter(|g| !g.holes.is_empty()).collect();
    let image = |group: &PartGroup| {
        drawn
            .iter()
            .position(|d| d.pieces == group.pieces)
            .map(|i| image_name("part", i + 1, drawn.len()))
    };
    let mut lines: Vec<String> = [
        "## Parts",
        "",
        "| Pieces | Lumber | Length (mm) | Count | Drawing |",
        "|--------|--------|-------------|-------|---------|",
    ]
    .map(String::from)
    .to_vec();
    for group in &groups {
        let lumber = assembly
            .model
            .piece(&group.pieces[0])
            .expect("a piece of the model")
            .kind
            .as_str();
        let drawing = image(group).map_or(String::new(), |name| format!("[{name}]({name})"));
        lines.push(format!(
            "| {} | {lumber} | {} | {} | {drawing} |",
            group.pieces.join(", "),
            format_mm(group.size[2]),
            group.pieces.len()
        ));
    }
    lines.push(String::new());
    for (i, group) in drawn.iter().enumerate() {
        lines.extend([
            format!("### {}", part_name(group)),
            String::new(),
            format!(
                "![Part {}]({})",
                i + 1,
                image_name("part", i + 1, drawn.len())
            ),
            String::new(),
        ]);
    }
    lines
}

pub fn steps_markdown(assembly: &Assembly, plan: &StepPlan, title: &str) -> String {
    let mut lines = vec![format!("# {title}: assembly steps"), String::new()];
    if let Some(hint) = grouping_hint(plan) {
        lines.extend([hint, String::new()]);
    }
    lines.extend(parts(assembly));
    for step in &plan.steps {
        lines.extend([
            format!("## {}", heading(step)),
            String::new(),
            format!(
                "![Step {}]({})",
                step.number,
                image_name("step", step.number, plan.steps.len())
            ),
            String::new(),
            "| Piece | Lumber | Length (mm) |".into(),
            "|-------|--------|-------------|".into(),
        ]);
        for id in &step.pieces {
            let piece = assembly.model.piece(id).expect("a piece of the model");
            let length = piece.length.map_or("?".into(), format_mm);
            lines.push(format!("| {id} | {} | {length} |", piece.kind.as_str()));
        }
        let hardware = count_hardware(assembly, Some(step.connections.as_slice()));
        if !hardware.is_empty() {
            lines.extend([
                String::new(),
                "| Fastener | Count |".into(),
                "|----------|-------|".into(),
            ]);
            lines.extend(
                hardware
                    .iter()
                    .map(|item| format!("| {} | {} |", item.name, item.count)),
            );
        }
        lines.push(String::new());
    }
    lines.join("\n")
}
