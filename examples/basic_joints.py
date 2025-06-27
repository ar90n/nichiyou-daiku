"""Basic joint types demonstration.

This example shows the fundamental joint types available in nichiyou-daiku,
demonstrating different ways pieces can be connected together.
"""

from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.model import Model, PiecePair
from nichiyou_daiku.core.connection import Connection, BasePosition, Anchor
from nichiyou_daiku.core.geometry import FromMax, FromMin
from nichiyou_daiku.core.geometry import Edge, EdgePoint
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.shell import assembly_to_build123d

# We'll create multiple joint examples, showing them separately

# ==============================================================================
# Example 1: T-Joint (perpendicular connection in the middle of a piece)
# ==============================================================================
print("Building T-Joint example...")

# Create pieces for T-joint
base_beam = Piece.of(PieceType.PT_2x4, 800.0, "t_base")  # Horizontal base
upright = Piece.of(PieceType.PT_2x4, 400.0, "t_upright")  # Vertical piece

# T-Joint: Connect upright to the middle of base beam
t_joint_connection = Connection.of(
    base=BasePosition(
        face="front",  # Front face of horizontal beam
        offset=FromMin(value=400.0)  # 400mm from the edge (centered on 800mm beam)
    ),
    target=Anchor(
        face="bottom",  # Bottom end of upright
        edge_point=EdgePoint(
            edge=Edge(lhs="bottom", rhs="front"),
            offset=FromMin(value=44.5)  # Centered on the 89mm width of 2x4
        )
    )
)

t_joint_model = Model.of(
    pieces=[base_beam, upright],
    connections=[(PiecePair(base=base_beam, target=upright), t_joint_connection)]
)

# ==============================================================================
# Example 2: Butt Joint (end-to-end connection)
# ==============================================================================
print("Building Butt Joint example...")

# Create pieces for butt joint
first_piece = Piece.of(PieceType.PT_2x4, 300.0, "butt_first")
second_piece = Piece.of(PieceType.PT_2x4, 300.0, "butt_second")

# Butt Joint: Connect end-to-end
butt_joint_connection = Connection.of(
    base=BasePosition(
        face="back",  # Back end of first piece
        offset=FromMin(value=0)  # Centered on height
    ),
    target=Anchor(
        face="front",  # Front end of second piece
        edge_point=EdgePoint(
            edge=Edge(lhs="front", rhs="left"),
            offset=FromMin(value=0)  # Centered
        )
    )
)

butt_joint_model = Model.of(
    pieces=[first_piece, second_piece],
    connections=[(PiecePair(base=first_piece, target=second_piece), butt_joint_connection)]
)

# ==============================================================================
# Example 3: Corner Joint (two pieces meeting at right angles)
# ==============================================================================
print("Building Corner Joint example...")

# Create pieces for corner joint
side_a = Piece.of(PieceType.PT_2x4, 400.0, "corner_a")
side_b = Piece.of(PieceType.PT_2x4, 400.0, "corner_b")

# Corner Joint: Two pieces meeting at 90 degrees
corner_joint_connection = Connection.of(
    base=BasePosition(
        face="back",  # End of first piece
        offset=FromMax(value=0.0)  # At the edge
    ),
    target=Anchor(
        face="left",  # Side of second piece  
        edge_point=EdgePoint(
            edge=Edge(lhs="front", rhs="left"),
            offset=FromMin(value=0.0)  # At the front edge
        )
    )
)

corner_joint_model = Model.of(
    pieces=[side_a, side_b],
    connections=[(PiecePair(base=side_a, target=side_b), corner_joint_connection)]
)

# ==============================================================================
# Visualize all joints
# ==============================================================================

# Convert each model to assembly and then to build123d
print("\nConverting to 3D...")

# You can uncomment the joint you want to visualize:
from build123d import Location
from ocp_vscode import show

# T-Joint
t_assembly = Assembly.of(t_joint_model)
t_compound = assembly_to_build123d(t_assembly, fillet_radius=2.0).moved(Location((0, 200, 0)))

# Butt Joint
butt_assembly = Assembly.of(butt_joint_model)
butt_compound = assembly_to_build123d(butt_assembly, fillet_radius=2.0).moved(Location((0, -200, 0)))

# Corner Joint
corner_assembly = Assembly.of(corner_joint_model)
corner_compound = assembly_to_build123d(corner_assembly, fillet_radius=2.0)
show(t_compound + butt_compound + corner_compound)

print("\nDone! Use OCP CAD Viewer to examine the joints.")
print("Tip: Uncomment different show() calls to view each joint type.")
# %%
