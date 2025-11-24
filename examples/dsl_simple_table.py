"""Simple table example using DSL - A basic four-legged table.

This example demonstrates how to build a simple table structure
with legs positioned inside a rectangular frame using DSL syntax.
"""

from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.core.piece import PieceType, get_shape
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.shell import assembly_to_build123d

from ocp_vscode import show


# ============================================================================
# TABLE DIMENSIONS
# ============================================================================
TABLE_WIDTH = 800.0  # 80cm wide
TABLE_DEPTH = 600.0  # 60cm deep
TABLE_HEIGHT = 720.0  # 72cm tall (standard dining table height)

# Calculate insets based on lumber dimensions
LEG_INSET_DEPTH = get_shape(PieceType.PT_2x4).height
LEG_INSET_WIDTH = get_shape(PieceType.PT_2x4).width

# Apron positioning
APRON_HEIGHT = 100.0  # Distance from top of leg to apron

# Calculate apron lengths
apron_front_back_length = TABLE_WIDTH - 2 * LEG_INSET_WIDTH
apron_left_right_length = TABLE_DEPTH - 2 * LEG_INSET_DEPTH

# Tabletop calculations
table_top_piece_num = 6
table_top_piece_interval = (
    apron_front_back_length - table_top_piece_num * get_shape(PieceType.PT_2x4).width
) / (table_top_piece_num + 1)

# ============================================================================
# CREATE TABLE USING DSL
# ============================================================================

# Build DSL string with calculated dimensions
table_dsl = f"""
(leg_1:2x4 {{"length": {TABLE_HEIGHT}}})
(leg_2:2x4 {{"length": {TABLE_HEIGHT}}})
(leg_3:2x4 {{"length": {TABLE_HEIGHT}}})
(leg_4:2x4 {{"length": {TABLE_HEIGHT}}})

(apron_front:2x4 {{"length": {apron_front_back_length}}})
(apron_back:2x4 {{"length": {apron_front_back_length}}})
(apron_left:2x4 {{"length": {apron_left_right_length}}})
(apron_right:2x4 {{"length": {apron_left_right_length}}})

(table_top_1:2x4 {{"length": {TABLE_DEPTH}}})
(table_top_2:2x4 {{"length": {TABLE_DEPTH}}})
(table_top_3:2x4 {{"length": {TABLE_DEPTH}}})
(table_top_4:2x4 {{"length": {TABLE_DEPTH}}})
(table_top_5:2x4 {{"length": {TABLE_DEPTH}}})
(table_top_6:2x4 {{"length": {TABLE_DEPTH}}})
(table_top_7:2x4 {{"length": {TABLE_DEPTH}}})
(table_top_8:2x4 {{"length": {TABLE_DEPTH}}})

leg_1 -[{{"contact_face": "left", "edge_shared_face": "back", "offset": FromMax(0)}}
        {{"contact_face": "down", "edge_shared_face": "back", "offset": FromMax(0)}}]- apron_front

leg_2 -[{{"contact_face": "right", "edge_shared_face": "front", "offset": FromMax(0)}}
        {{"contact_face": "top", "edge_shared_face": "front", "offset": FromMax(0)}}]- apron_front

leg_3 -[{{"contact_face": "left", "edge_shared_face": "back", "offset": FromMax(0)}}
        {{"contact_face": "down", "edge_shared_face": "back", "offset": FromMax(0)}}]- apron_back

leg_4 -[{{"contact_face": "right", "edge_shared_face": "front", "offset": FromMax(0)}}
        {{"contact_face": "top", "edge_shared_face": "front", "offset": FromMax(0)}}]- apron_back

leg_1 -[{{"contact_face": "back", "edge_shared_face": "right", "offset": FromMin({APRON_HEIGHT})}}
        {{"contact_face": "down", "edge_shared_face": "back", "offset": FromMin(0)}}]- apron_left

leg_3 -[{{"contact_face": "front", "edge_shared_face": "right", "offset": FromMin({APRON_HEIGHT})}}
        {{"contact_face": "top", "edge_shared_face": "back", "offset": FromMin(0)}}]- apron_left

leg_2 -[{{"contact_face": "back", "edge_shared_face": "left", "offset": FromMin({APRON_HEIGHT})}}
        {{"contact_face": "down", "edge_shared_face": "front", "offset": FromMin(0)}}]- apron_right

leg_4 -[{{"contact_face": "front", "edge_shared_face": "left", "offset": FromMin({APRON_HEIGHT})}}
        {{"contact_face": "top", "edge_shared_face": "front", "offset": FromMin(0)}}]- apron_right

table_top_1 -[{{"contact_face": "back", "edge_shared_face": "down", "offset": FromMin(0)}}
              {{"contact_face": "top", "edge_shared_face": "front", "offset": FromMin(0)}}]- leg_1

table_top_8 -[{{"contact_face": "back", "edge_shared_face": "down", "offset": FromMin(0)}}
              {{"contact_face": "top", "edge_shared_face": "front", "offset": FromMin(0)}}]- leg_2
"""

# Add connections for middle table top pieces to front apron
for i in range(2, 8):
    offset = (i - 2) * LEG_INSET_WIDTH + (i - 1) * table_top_piece_interval
    table_dsl += f"""
apron_front -[{{"contact_face": "right", "edge_shared_face": "front", "offset": FromMin({offset})}}
               {{"contact_face": "back", "edge_shared_face": "top", "offset": FromMin(0)}}]- table_top_{i}
"""

# Parse DSL to create model
model = parse_dsl(table_dsl)

# ============================================================================
# VISUALIZE
# ============================================================================
print("Building simple table...")
assembly = Assembly.of(model)

# Export with smaller fillet radius for sharper edges
compound = assembly_to_build123d(assembly, fillet_radius=2.0)

# Display the result
show(compound)

print("\nSimple table assembly complete!")
print(f"Table frame dimensions: {TABLE_WIDTH}mm x {TABLE_DEPTH}mm")
print(f"Table height: {TABLE_HEIGHT}mm")
print(f"Using {len(model.pieces)} pieces with {len(model.connections)} connections")
print("\nNote: The tabletop would be added on top of this frame structure.")
# %%
