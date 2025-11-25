# %%
"""Shelf example using DSL - A two-level shelf unit.

This example demonstrates how to build a shelf with two levels
using DSL syntax. The shelf has 4 legs with aprons and shelving
on both bottom and top levels.
"""

from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.core.piece import PieceType, get_shape
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.shell import (
    assembly_to_build123d,
    extract_resources,
    generate_markdown_report,
)

from ocp_vscode import show


def _calc_apron_length(length: float, leg_inset_length: float) -> float:
    return length - 2 * leg_inset_length


# ============================================================================
# SHELF DIMENSIONS
# ============================================================================
SHELF_WIDTH = 400.0
SHELF_DEPTH = 280.0
SHELF_HEIGHT = 750.0

# Apron positioning
BOTTOM_APRON_HEIGHT = 150.0  # Distance from bottom of leg to apron
TOP_APRON_HEIGHT = 250.0     # Distance from top of leg to apron

# Calculate apron lengths
apron_front_back_length = _calc_apron_length(
    SHELF_WIDTH, get_shape(PieceType.PT_2x4).height
)
apron_left_right_length = _calc_apron_length(
    SHELF_DEPTH, get_shape(PieceType.PT_2x4).width
)

# table top parameters
desired_table_top_piece_interval = 10.0  # Desired interval between tabletop pieces
table_top_piece_num = (
    int(
        (apron_front_back_length - get_shape(PieceType.PT_1x4).width)
        / (get_shape(PieceType.PT_1x4).width + desired_table_top_piece_interval)
    )
    + 1
)
table_top_piece_interval = (
    apron_front_back_length - table_top_piece_num * get_shape(PieceType.PT_1x4).width
) / (table_top_piece_num - 1)


# ============================================================================
# CREATE SHELF USING DSL
# ============================================================================

# Build DSL string with calculated dimensions
shelf_dsl = f"""
// Shelf Design
// Dimensions: {SHELF_WIDTH}mm x {SHELF_DEPTH}mm x {SHELF_HEIGHT}mm

// Four legs
(leg_left_front:2x4 ={SHELF_HEIGHT})
(leg_right_front:2x4 ={SHELF_HEIGHT})
(leg_left_back:2x4 ={SHELF_HEIGHT})
(leg_right_back:2x4 ={SHELF_HEIGHT})

// Bottom aprons
(bottom_table_top_apron_front:2x4 ={apron_front_back_length})
(bottom_table_top_apron_back:2x4 ={apron_front_back_length})
(bottom_apron_left:2x4 ={apron_left_right_length})
(bottom_apron_right:2x4 ={apron_left_right_length})
(bottom_apron_back:2x4 ={apron_front_back_length})

// Top aprons
(top_table_top_apron_front:2x4 ={apron_front_back_length})
(top_table_top_apron_back:2x4 ={apron_front_back_length})
(top_apron_left:2x4 ={apron_left_right_length})
(top_apron_right:2x4 ={apron_left_right_length})
(top_apron_front:2x4 ={apron_front_back_length})
(top_apron_back:2x4 ={apron_front_back_length})
"""

# Add bottom table top pieces
for i in range(table_top_piece_num):
    shelf_dsl += f"(bottom_table_top_{i}:1x4 ={SHELF_DEPTH})\n"

# Add top table top pieces
for i in range(table_top_piece_num):
    shelf_dsl += f"(top_table_top_{i}:1x4 ={SHELF_DEPTH})\n"

# Add connections
shelf_dsl += f"""
// Front table top apron connections (bottom level)
leg_left_front -[BL>{BOTTOM_APRON_HEIGHT} DR>0]- bottom_table_top_apron_front
leg_right_front -[FR>{BOTTOM_APRON_HEIGHT} TL>0]- bottom_table_top_apron_front

// Back table top apron connections (bottom level)
leg_left_back -[BL>{BOTTOM_APRON_HEIGHT} DR>0]- bottom_table_top_apron_back
leg_right_back -[FR>{BOTTOM_APRON_HEIGHT} TL>0]- bottom_table_top_apron_back

// Front table top apron connections (top level)
leg_left_front -[BL<{TOP_APRON_HEIGHT} DR<0]- top_table_top_apron_front
leg_right_front -[FR<{TOP_APRON_HEIGHT} TL<0]- top_table_top_apron_front

// Back table top apron connections (top level)
leg_left_back -[BL<{TOP_APRON_HEIGHT} DR<0]- top_table_top_apron_back
leg_right_back -[FR<{TOP_APRON_HEIGHT} TL<0]- top_table_top_apron_back

// Bottom side apron connections
leg_left_front -[RF>{BOTTOM_APRON_HEIGHT + 150} TF<0]- bottom_apron_left
leg_left_back -[LF>{BOTTOM_APRON_HEIGHT + 150} DF<0]- bottom_apron_left
leg_right_front -[RB>{BOTTOM_APRON_HEIGHT + 150} DF<0]- bottom_apron_right
leg_right_back -[LB>{BOTTOM_APRON_HEIGHT + 150} TF<0]- bottom_apron_right
leg_left_back -[BR>{BOTTOM_APRON_HEIGHT + 150} DB<0]- bottom_apron_back
leg_right_back -[FR>{BOTTOM_APRON_HEIGHT + 150} TB<0]- bottom_apron_back

// Top side apron connections
leg_left_front -[RF<0 TF<0]- top_apron_left
leg_left_back -[LF<0 DF<0]- top_apron_left
leg_right_front -[RB<0 DF<0]- top_apron_right
leg_right_back -[LB<0 TF<0]- top_apron_right
leg_left_back -[BR<0 DB<0]- top_apron_back
leg_right_back -[FR<0 TB<0]- top_apron_back
leg_left_front -[BL<0 DF<0]- top_apron_front
leg_right_front -[FL<0 TF<0]- top_apron_front
"""

# Add bottom table top piece connections
for i in range(table_top_piece_num):
    offset = i * (get_shape(PieceType.PT_1x4).width + table_top_piece_interval)
    shelf_dsl += f"bottom_table_top_apron_front -[FR>{offset:.3f} FT>0]- bottom_table_top_{i}\n"
    shelf_dsl += f"bottom_table_top_apron_back -[FL>{offset:.3f} FD>0]- bottom_table_top_{i}\n"

# Add top table top piece connections
for i in range(table_top_piece_num):
    offset = i * (get_shape(PieceType.PT_1x4).width + table_top_piece_interval)
    shelf_dsl += f"top_table_top_apron_front -[FR>{offset:.3f} FT>0]- top_table_top_{i}\n"
    shelf_dsl += f"top_table_top_apron_back -[FL>{offset:.3f} FD>0]- top_table_top_{i}\n"

# Parse DSL to create model
print("Parsing shelf DSL...")
model = parse_dsl(shelf_dsl)

# ============================================================================
# CREATE ASSEMBLY AND EXTRACT RESOURCES
# ============================================================================
print("Creating assembly...")
assembly = Assembly.of(model)

print("Extracting bill of materials...")
resources = extract_resources(assembly)

# Display resource summary
print("\n" + resources.pretty_print())

# Generate comprehensive markdown report
print("\nGenerating detailed markdown report...")

# Define custom standard lengths for this project
custom_standard_lengths = {
    PieceType.PT_2x4: [2440.0, 3000.0, 3600.0],  # 8ft, ~10ft, 12ft
    PieceType.PT_1x4: [1800.0, 2400.0, 3000.0],  # 6ft, 8ft, 10ft
}

report = generate_markdown_report(
    resources,
    project_name="DIY Shelf Project (DSL)",
    standard_lengths=custom_standard_lengths,
    include_cut_diagram=True
)

# Save report to file
report_filename = "dsl_shelf_project_report.md"
with open(report_filename, "w", encoding="utf-8") as f:
    f.write(report)

print(f"✅ Detailed report saved to: {report_filename}")
print("📋 Report includes cut optimization and purchase recommendations")

# ============================================================================
# VISUALIZE
# ============================================================================
print("\nBuilding 3D visualization...")

# Export with smaller fillet radius for sharper edges
compound = assembly_to_build123d(assembly, fillet_radius=2.0)

# Display the result
show(compound)

print("\nShelf assembly complete!")
print(f"Shelf dimensions: {SHELF_WIDTH}mm x {SHELF_DEPTH}mm x {SHELF_HEIGHT}mm")
print(f"Using {len(model.pieces)} pieces with {len(model.connections)} connections")
# %%
