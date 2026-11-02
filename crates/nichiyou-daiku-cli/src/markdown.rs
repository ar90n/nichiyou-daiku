//! The report's Markdown (shell/report_generator.py), section by section in
//! the same order and form.

use nichiyou_daiku_core::cutting::{LumberPlan, plan_cuts};
use nichiyou_daiku_core::piece::PieceType;
use nichiyou_daiku_core::pyfmt::{format_fixed, format_mm};
use nichiyou_daiku_core::resources::{PieceResource, PilotHoleInfo, ResourceSummary};

pub struct Options<'a> {
    pub project_name: &'a str,
    pub generated_on: &'a str,
    pub cut_diagram: bool,
    pub anchor_details: bool,
    pub pilot_holes: bool,
    /// The store's lengths per type; types it leaves out keep the defaults
    pub lengths: &'a [(PieceType, Vec<f64>)],
    pub kerf: f64,
}

/// Python's f"{value:,.{precision}f}": thousands separated by commas.
pub fn grouped(value: f64, precision: usize) -> String {
    let text = format_fixed(value, precision);
    let (sign, digits) = match text.strip_prefix('-') {
        Some(rest) => ("-", rest.to_string()),
        None => ("", text.clone()),
    };
    let (whole, fraction) = match digits.split_once('.') {
        Some((w, f)) => (w.to_string(), format!(".{f}")),
        None => (digits.clone(), String::new()),
    };
    let mut out = String::new();
    for (i, ch) in whole.chars().enumerate() {
        if i > 0 && (whole.len() - i) % 3 == 0 {
            out.push(',');
        }
        out.push(ch);
    }
    format!("{sign}{out}{fraction}")
}

fn strings(lines: &[&str]) -> Vec<String> {
    lines.iter().map(|line| line.to_string()).collect()
}

fn overview(summary: &ResourceSummary, options: &Options) -> String {
    // Pine weighs about 0.5 g/cm³
    let weight_kg = summary.total_volume / 1000.0 * 0.5 / 1000.0;
    let mut types: Vec<&str> = summary
        .by_type
        .iter()
        .map(|(kind, _, _)| kind.as_str())
        .collect();
    types.sort();
    let size_line = match (summary.overall_size, &summary.size_reference) {
        (Some([x, y, z]), Some(reference)) => format!(
            "- **Overall Size (X × Y × Z)**: {} × {} × {} mm (Z is the length direction of '{reference}')\n",
            format_mm(x),
            format_mm(y),
            format_mm(z)
        ),
        _ => String::new(),
    };
    format!(
        "# {} Report\n\n*Generated on {}*\n\n## Project Overview\n\n{size_line}- **Total Pieces**: {}\n- **Lumber Types**: {} ({})\n- **Total Volume**: {} mm³\n- **Estimated Weight**: ~{} kg (assuming pine density)\n\n",
        options.project_name,
        options.generated_on,
        summary.pieces.len(),
        summary.by_type.len(),
        types.join(", "),
        grouped(summary.total_volume, 0),
        format_fixed(weight_kg, 1)
    )
}

fn warnings(summary: &ResourceSummary) -> String {
    let mut lines = strings(&[
        "## Warnings",
        "",
        "The design has problems. Fix them before building:",
        "",
    ]);
    lines.extend(summary.issues.iter().map(|issue| format!("- {issue}")));
    lines.push(String::new());
    lines.join("\n")
}

fn bill_of_materials(summary: &ResourceSummary) -> String {
    let mut lines = strings(&[
        "## Bill of Materials",
        "",
        "| ID | Type | Length (mm) | Width (mm) | Height (mm) | Volume (mm³) |",
        "|----|------|------------|-----------|------------|-------------|",
    ]);
    let mut pieces: Vec<&PieceResource> = summary.pieces.iter().collect();
    // Stable, as Python's sorted: by type, then by length
    pieces.sort_by(|a, b| {
        a.kind.as_str().cmp(b.kind.as_str()).then(
            a.length
                .partial_cmp(&b.length)
                .unwrap_or(std::cmp::Ordering::Equal),
        )
    });
    for piece in pieces {
        lines.push(format!(
            "| {} | {} | {} | {} | {} | {} |",
            piece.id,
            piece.kind.as_str(),
            format_mm(piece.length),
            format_fixed(piece.width, 0),
            format_fixed(piece.height, 0),
            grouped(piece.volume, 0)
        ));
    }
    lines.extend([String::new(), String::new()]);
    lines.join("\n")
}

fn by_id(summary: &ResourceSummary, keep: impl Fn(&PieceResource) -> bool) -> Vec<&PieceResource> {
    let mut pieces: Vec<&PieceResource> = summary.pieces.iter().filter(|p| keep(p)).collect();
    pieces.sort_by(|a, b| a.id.cmp(&b.id));
    pieces
}

fn heading(piece: &PieceResource) -> String {
    format!(
        "### {} ({}, {}mm)",
        piece.id,
        piece.kind.as_str(),
        format_mm(piece.length)
    )
}

fn anchor_details(summary: &ResourceSummary) -> String {
    let mut lines = strings(&["## Anchor Details", ""]);
    let pieces = by_id(summary, |p| !p.anchors.is_empty());
    if pieces.is_empty() {
        lines.extend(strings(&["*No anchor points in this project.*", ""]));
        return lines.join("\n");
    }
    for piece in pieces {
        lines.extend([heading(piece), String::new()]);
        lines.extend(strings(&[
            "| Contact Face | Edge Face | Offset |",
            "|--------------|-----------|--------|",
        ]));
        for anchor in &piece.anchors {
            lines.push(format!(
                "| {} | {} | {} {}mm |",
                anchor.contact_face,
                anchor.edge_face,
                anchor.offset_type,
                format_fixed(anchor.offset_value, 1)
            ));
        }
        lines.push(String::new());
    }
    lines.join("\n")
}

/// A face's holes as text, 40 by 5 cells inside a border.
fn face_diagram(holes: &[&PilotHoleInfo], face: &str, width: f64, height: f64) -> Vec<String> {
    const W: usize = 40;
    const H: usize = 5;
    let mut grid = vec![vec![' '; W + 2]; H + 2];
    grid[0].fill('-');
    grid[H + 1].fill('-');
    for row in grid.iter_mut() {
        row[0] = '|';
        row[W + 1] = '|';
    }
    for (y, x) in [(0, 0), (0, W + 1), (H + 1, 0), (H + 1, W + 1)] {
        grid[y][x] = '+';
    }
    for hole in holes {
        // Python's int() truncates toward zero
        let x = ((hole.from_length_edge / width) * W as f64).trunc() as i64 + 1;
        let y = ((hole.from_width_edge / height) * H as f64).trunc() as i64 + 1;
        grid[y.clamp(1, H as i64) as usize][x.clamp(1, W as i64) as usize] = 'o';
    }
    let mut lines = vec![
        "```".to_string(),
        format!(
            "{face} ({}mm x {}mm):",
            format_fixed(width, 0),
            format_fixed(height, 0)
        ),
    ];
    lines.extend(
        grid.into_iter()
            .map(|row| row.into_iter().collect::<String>()),
    );
    lines.push("```".into());
    lines
}

fn pilot_hole_row(hole: &PilotHoleInfo) -> String {
    let depth = hole
        .depth
        .map_or("through".into(), |d| format!("{}mm", format_fixed(d, 1)));
    let sink = hole
        .countersink
        .map_or("-".into(), |c| format!("φ{}mm", format_fixed(c, 1)));
    format!(
        "| {} | {}mm | {}mm | φ{}mm | {depth} | {sink} |",
        hole.face,
        format_fixed(hole.from_length_edge, 1),
        format_fixed(hole.from_width_edge, 1),
        format_fixed(hole.diameter, 1)
    )
}

fn pilot_holes(summary: &ResourceSummary) -> String {
    let mut lines = strings(&["## Pilot Holes", ""]);
    let pieces = by_id(summary, |p| !p.pilot_holes.is_empty());
    if pieces.is_empty() {
        lines.extend(strings(&["*No pilot holes in this project.*", ""]));
        return lines.join("\n");
    }
    lines.extend(strings(&[
        "Distances are measured on the face the hole is drilled into:",
        "- front/back faces: *From Length Edge* from the down end, *From Width Edge* from the left side",
        "- left/right faces: *From Length Edge* from the down end, *From Width Edge* from the back side",
        "- top/down (end) faces: *From Length Edge* from the left side, *From Width Edge* from the back side",
        "",
    ]));
    for piece in pieces {
        lines.extend([heading(piece), String::new()]);
        lines.extend(strings(&[
            "| Face | From Length Edge | From Width Edge | Diameter | Depth | Countersink |",
            "|---|---|---|---|---|---|",
        ]));
        let mut faces: Vec<(&str, Vec<&PilotHoleInfo>)> = Vec::new();
        for hole in &piece.pilot_holes {
            lines.push(pilot_hole_row(hole));
            match faces.iter_mut().find(|(face, _)| *face == hole.face) {
                Some((_, list)) => list.push(hole),
                None => faces.push((hole.face, vec![hole])),
            }
        }
        lines.push(String::new());
        faces.sort_by(|a, b| a.0.cmp(b.0));
        for (face, holes) in faces {
            let (width, height) = match face {
                "top" | "down" => (piece.width, piece.height),
                "left" | "right" => (piece.length, piece.height),
                _ => (piece.length, piece.width),
            };
            lines.extend(face_diagram(&holes, face, width, height));
            lines.push(String::new());
        }
    }
    lines.join("\n")
}

fn shopping_list(summary: &ResourceSummary) -> String {
    let mut lines = strings(&["## Shopping List", "", "### Lumber Required:", ""]);
    let mut types = summary.by_type.clone();
    types.sort_by_key(|(kind, _, _)| kind.as_str());
    for (kind, count, total) in types {
        lines.push(format!(
            "- **{}**: {count} pieces, total {} meters",
            kind.as_str(),
            format_fixed(total / 1000.0, 1)
        ));
    }
    if !summary.hardware.is_empty() {
        lines.extend(strings(&["", "### Hardware Required:", ""]));
        lines.extend(
            summary
                .hardware
                .iter()
                .map(|item| format!("- **{}**: {}", item.name, item.count)),
        );
    }
    if !summary.drill_bits.is_empty() {
        lines.extend(strings(&["", "### Drill Bits:", ""]));
        for bit in &summary.drill_bits {
            let deepest = bit.deepest.map_or("deepest: through".into(), |d| {
                format!("deepest {}mm", format_mm(d))
            });
            lines.push(format!(
                "- **{}mm**: {} holes, {deepest}",
                format_mm(bit.diameter),
                bit.holes
            ));
        }
        for (diameter, holes) in &summary.countersinks {
            lines.push(format!(
                "- **Countersink φ{}mm**: {holes} holes",
                format_mm(*diameter)
            ));
        }
    }
    lines.extend([String::new(), String::new()]);
    lines.join("\n")
}

fn oversize_warning(plan: &LumberPlan) -> Vec<String> {
    let longest = plan
        .available
        .iter()
        .copied()
        .fold(f64::NEG_INFINITY, f64::max);
    plan.oversize
        .iter()
        .map(|(id, length)| {
            format!(
                "- ⚠ {id} ({}mm) is longer than the longest available board ({}mm) and cannot be cut from stock",
                format_mm(*length),
                format_mm(longest)
            )
        })
        .collect()
}

fn purchase_recommendations(plans: &[(PieceType, LumberPlan)], kerf: f64) -> String {
    let mut lines = vec![
        "## Purchase Recommendations".to_string(),
        String::new(),
        format!("Saw kerf: {}mm per cut", format_mm(kerf)),
        String::new(),
    ];
    for (kind, plan) in plans {
        let mut lengths = plan.available.clone();
        lengths.sort_by(f64::total_cmp);
        let listed: Vec<String> = lengths
            .iter()
            .map(|l| format!("{}mm", format_mm(*l)))
            .collect();
        lines.push(format!(
            "### {} Lumber (Available: {})",
            kind.as_str(),
            listed.join(", ")
        ));
        lines.push("Optimal purchase:".into());
        for (length, count) in plan.board_counts() {
            lines.push(format!("- {count} × {}mm boards", format_mm(length)));
        }
        lines.push(format!(
            "Total waste: {}mm ({}%)",
            format_mm(plan.total_waste()),
            format_fixed(plan.waste_percentage(), 1)
        ));
        lines.extend(oversize_warning(plan));
        lines.push(String::new());
    }
    lines.join("\n")
}

fn cut_list(plans: &[(PieceType, LumberPlan)]) -> String {
    let mut lines = strings(&["## Optimized Cut List", ""]);
    for (kind, plan) in plans {
        lines.extend([format!("### {} Boards", kind.as_str()), String::new()]);
        let warnings = oversize_warning(plan);
        if !warnings.is_empty() {
            lines.extend(warnings);
            lines.push(String::new());
        }
        for (i, board) in plan.boards.iter().enumerate() {
            lines.push(format!(
                "**Board {}** ({}mm):",
                i + 1,
                format_mm(board.length)
            ));
            for (id, length) in &board.cuts {
                lines.push(format!("- Cut {}mm → {id}", format_mm(*length)));
            }
            if board.waste > 0.0 {
                lines.push(format!("- Waste: {}mm", format_mm(board.waste)));
            }
            lines.push(String::new());
        }
    }
    lines.join("\n")
}

/// The whole report, its sections joined as the Python version joins them.
pub fn report(summary: &ResourceSummary, options: &Options) -> String {
    let pieces: Vec<(String, PieceType, f64)> = summary
        .pieces
        .iter()
        .map(|p| (p.id.clone(), p.kind, p.length))
        .collect();
    let plans = plan_cuts(&pieces, options.lengths, options.kerf);
    let mut sections = vec![overview(summary, options)];
    if !summary.issues.is_empty() {
        sections.push(warnings(summary));
    }
    sections.push(bill_of_materials(summary));
    if options.anchor_details {
        sections.push(anchor_details(summary));
    }
    if options.pilot_holes {
        sections.push(pilot_holes(summary));
    }
    sections.push(shopping_list(summary));
    sections.push(purchase_recommendations(&plans, options.kerf));
    if options.cut_diagram {
        sections.push(cut_list(&plans));
    }
    sections.push("---\n*Report generated by nichiyou-daiku*".into());
    sections.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn thousands_are_grouped_as_python_groups_them() {
        assert_eq!(grouped(2536500.0, 0), "2,536,500");
        assert_eq!(grouped(744040.0, 0), "744,040");
        assert_eq!(grouped(999.5, 0), "1,000");
        assert_eq!(grouped(6087600.0, 1), "6,087,600.0");
        assert_eq!(grouped(12.0, 0), "12");
    }

    #[test]
    fn a_face_diagram_puts_each_hole_in_its_cell() {
        let hole = PilotHoleInfo {
            face: "back",
            from_length_edge: 220.0,
            from_width_edge: 44.5,
            diameter: 2.5,
            depth: None,
            countersink: None,
        };
        let lines = face_diagram(&[&hole], "back", 440.0, 89.0);
        assert_eq!(lines[1], "back (440mm x 89mm):");
        assert_eq!(lines[2], format!("+{}+", "-".repeat(40)));
        // 220/440 of 40 is 20, then one for the border; 44.5/89 of 5 is 2 (int), plus one
        assert_eq!(lines[2 + 3].chars().nth(21), Some('o'));
    }

    #[test]
    fn the_pilot_holes_table_gives_each_countersink() {
        let line = pilot_hole_row(&PilotHoleInfo {
            face: "front",
            from_length_edge: 75.0,
            from_width_edge: 44.5,
            diameter: 2.0,
            depth: None,
            countersink: Some(6.5),
        });
        assert_eq!(
            line,
            "| front | 75.0mm | 44.5mm | φ2.0mm | through | φ6.5mm |"
        );
    }
}
