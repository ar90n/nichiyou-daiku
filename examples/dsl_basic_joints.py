"""Basic joint types demonstration using DSL.

This example shows the fundamental joint types available in nichiyou-daiku,
demonstrating different ways pieces can be connected together using DSL syntax.
"""

from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.shell import assembly_to_build123d
from build123d import Location
from ocp_vscode import show_object

# We'll create multiple joint examples, showing them separately

# ==============================================================================
# Example 1: T-Joint (perpendicular connection in the middle of a piece)
# ==============================================================================
print("Building T-Joint example...")

# T-Joint: Connect upright to the middle of base beam
t_joint_dsl = """
(t_base:PT_2x4 {"length": 800})
(t_upright:PT_2x4 {"length": 400})

t_base -[{"contact_face": "front", "edge_shared_face": "right", "offset": FromMin(400)}
         {"contact_face": "down", "edge_shared_face": "front", "offset": FromMin(44.5)}]- t_upright
"""

t_joint_model = parse_dsl(t_joint_dsl)

# ==============================================================================
# Example 2: Butt Joint (end-to-end connection)
# ==============================================================================
print("Building Butt Joint example...")

# Butt Joint: Connect end-to-end
butt_joint_dsl = """
(butt_first:PT_2x4 {"length": 300})
(butt_second:PT_2x4 {"length": 300})

butt_first -[{"contact_face": "top", "edge_shared_face": "left", "offset": FromMin(0)}
             {"contact_face": "down", "edge_shared_face": "left", "offset": FromMin(0)}]- butt_second
"""

butt_joint_model = parse_dsl(butt_joint_dsl)

# ==============================================================================
# Example 3: Corner Joint (two pieces meeting at right angles)
# ==============================================================================
print("Building Corner Joint example...")

# Corner Joint: Two pieces meeting at 90 degrees
corner_joint_dsl = """
(corner_a:PT_2x4 {"length": 400})
(corner_b:PT_2x4 {"length": 400})

corner_a -[{"contact_face": "back", "edge_shared_face": "right", "offset": FromMin(0)}
           {"contact_face": "left", "edge_shared_face": "front", "offset": FromMin(0)}]- corner_b
"""

corner_joint_model = parse_dsl(corner_joint_dsl)

# ==============================================================================
# Visualize all joints
# ==============================================================================

# Convert each model to assembly and then to build123d
print("\nConverting to 3D...")

# You can uncomment the joint you want to visualize:

# T-Joint
t_assembly = Assembly.of(t_joint_model)
t_compound = assembly_to_build123d(t_assembly, fillet_radius=2.0).moved(
    Location((0, 200, 0))
)

# Butt Joint
butt_assembly = Assembly.of(butt_joint_model)
butt_compound = assembly_to_build123d(butt_assembly, fillet_radius=2.0).moved(
    Location((0, -200, 0))
)

# Corner Joint
corner_assembly = Assembly.of(corner_joint_model)
corner_compound = assembly_to_build123d(corner_assembly, fillet_radius=2.0)

show_object(t_compound)
show_object(butt_compound)
show_object(corner_compound)

print("\nDone! Use OCP CAD Viewer to examine the joints.")
print("Tip: Uncomment different show() calls to view each joint type.")
# %%
