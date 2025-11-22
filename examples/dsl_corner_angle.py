"""Corner angle joint example using DSL - A 90-degree corner connection.

This example demonstrates the DSL version of corner_angle.py,
creating a corner joint where two pieces meet at right angles.
"""

from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.shell import assembly_to_build123d

from ocp_vscode import show

try:
    from utils import get_connection_summary
except ImportError:
    from examples.utils import get_connection_summary

# Define corner joint using DSL
# Two 2x4 pieces of 400mm each forming a 90-degree corner
corner_dsl = """
(corner_piece_a:2x4 {"length": 400})
(corner_piece_b:2x4 {"length": 400})

corner_piece_a -[{"contact_face": "top", "edge_shared_face": "front", "offset": FromMin(0)}
                 {"contact_face": "back", "edge_shared_face": "down", "offset": FromMin(0)}]- corner_piece_b
"""

# Parse the DSL to create a model
model = parse_dsl(corner_dsl)

# Show connection details
print("Connection Details:")
print(get_connection_summary(model))

# Convert to 3D assembly
assembly = Assembly.of(model)

# Export to build123d for visualization
compound = assembly_to_build123d(
    assembly,
    fillet_radius=3.0,  # 3mm radius for rounded edges
)

# Display in OCP CAD Viewer
show(compound)

print("Corner angle joint created successfully!")
print("This forms a clean 90-degree corner connection.")
# %%
