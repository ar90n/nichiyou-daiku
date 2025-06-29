"""Basic joint types demonstration.

This example shows the fundamental joint types available in nichiyou-daiku,
demonstrating different ways pieces can be connected together.
"""

from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.model import Model, PiecePair
from nichiyou_daiku.core.connection import Connection, Anchor
from nichiyou_daiku.core.geometry import FromMax, FromMin
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.shell import assembly_to_build123d
from build123d import Location
from ocp_vscode import show_object

# We'll create multiple joint examples, showing them separately

# ==============================================================================
# Example 1: T-Joint (perpendicular connection in the middle of a piece)
# ==============================================================================
print("Building T-Joint example...")

# Create pieces for T-joint
base_beam = Piece.of(PieceType.PT_2x4, 800.0, "t_base")  # Horizontal base
upright = Piece.of(PieceType.PT_2x4, 400.0, "t_upright")  # Vertical piece

# T-Joint: Connect upright to the middle of base beam
t_joint_connection = Connection(
    lhs=Anchor(
        contact_face="front",
        edge_shared_face="right",
        offset=FromMin(value=400.0)  # 400mm from the edge (centered on 800mm beam)
    ),
    rhs=Anchor(
        contact_face="bottom",
        edge_shared_face="front",
        offset=FromMin(value=44.5)  # Centered on the 89mm width of 2x4
    )
)

t_joint_model = Model.of(
    pieces=[base_beam, upright],
    connections=[(PiecePair(base=base_beam, target=upright), t_joint_connection)],
    label="t_joint"
)

# ==============================================================================
# Example 2: Butt Joint (end-to-end connection)
# ==============================================================================
print("Building Butt Joint example...")

# Create pieces for butt joint
first_piece = Piece.of(PieceType.PT_2x4, 300.0, "butt_first")
second_piece = Piece.of(PieceType.PT_2x4, 300.0, "butt_second")

# Butt Joint: Connect end-to-end
butt_joint_connection = Connection(
    lhs=Anchor(
        contact_face="top",
        edge_shared_face="left",
        offset=FromMin(value=0)
    ),
    rhs=Anchor(
        contact_face="bottom",
        edge_shared_face="left",
        offset=FromMin(value=0)
    )
)

butt_joint_model = Model.of(
    pieces=[first_piece, second_piece],
    connections=[(PiecePair(base=first_piece, target=second_piece), butt_joint_connection)],
    label="butt_joint"
)

# ==============================================================================
# Example 3: Corner Joint (two pieces meeting at right angles)
# ==============================================================================
print("Building Corner Joint example...")

# Create pieces for corner joint
side_a = Piece.of(PieceType.PT_2x4, 400.0, "corner_a")
side_b = Piece.of(PieceType.PT_2x4, 400.0, "corner_b")

# Corner Joint: Two pieces meeting at 90 degrees
corner_joint_connection = Connection(
    lhs=Anchor(
        contact_face="back",
        edge_shared_face="right",
        offset=FromMin(value=0.0)
    ),
    rhs=Anchor(
        contact_face="left",
        edge_shared_face="front",
        offset=FromMin(value=0.0)
    )
)

corner_joint_model = Model.of(
    pieces=[side_a, side_b],
    connections=[(PiecePair(base=side_a, target=side_b), corner_joint_connection)],
    label="corner_joint"
)

# ==============================================================================
# Visualize all joints
# ==============================================================================

# Convert each model to assembly and then to build123d
print("\nConverting to 3D...")

# You can uncomment the joint you want to visualize:

# T-Joint
t_assembly = Assembly.of(t_joint_model)
t_compound = assembly_to_build123d(t_assembly, fillet_radius=2.0).moved(Location((0, 200, 0)))

# Butt Joint
butt_assembly = Assembly.of(butt_joint_model)
butt_compound = assembly_to_build123d(butt_assembly, fillet_radius=2.0).moved(Location((0, -200, 0)))

# Corner Joint
corner_assembly = Assembly.of(corner_joint_model)
corner_compound = assembly_to_build123d(corner_assembly, fillet_radius=2.0)

show_object(t_compound)
show_object(butt_compound)
show_object(corner_compound)

print("\nDone! Use OCP CAD Viewer to examine the joints.")
print("Tip: Uncomment different show() calls to view each joint type.")