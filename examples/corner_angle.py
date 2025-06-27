"""Corner angle joint example - A 90-degree corner connection.

This example demonstrates how to create a corner joint where two pieces
meet at right angles, like the corner of a picture frame or box.
"""

from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.model import Model, PiecePair
from nichiyou_daiku.core.connection import Connection, BasePosition, Anchor
from nichiyou_daiku.core.geometry import FromMax
from nichiyou_daiku.core.geometry import Edge, EdgePoint
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.shell import assembly_to_build123d

from ocp_vscode import show

# Create two 2x4 pieces that will form a corner
# Both pieces are the same length for a symmetric corner
piece_a = Piece.of(PieceType.PT_2x4, 400.0, "corner_piece_a")
piece_b = Piece.of(PieceType.PT_2x4, 400.0, "corner_piece_b")

# Define the corner connection
# piece_a's end connects to the side of piece_b
connection = Connection.of(
    # Base position: On the left face of piece_b, at the front edge
    base=BasePosition(
        face="left",  # Side face of piece_b
        offset=FromMax(value=0.0)  # At the very front edge
    ),
    # Target anchor: On the front end of piece_a
    target=Anchor(
        face="front",  # Front end face of piece_a
        edge_point=EdgePoint(
            edge=Edge(lhs="front", rhs="left"),  # Edge at the corner
            offset=FromMin(value=0.0)  # At the corner point
        )
    )
)

# Build the model
model = Model.of(
    pieces=[piece_b, piece_a],
    connections=[
        (PiecePair(base=piece_a, target=piece_b), connection),
    ],
    label="corner_angle_joint_example"
)

# Convert to 3D assembly
assembly = Assembly.of(model)

# Export to build123d for visualization
compound = assembly_to_build123d(
    assembly, 
    fillet_radius=3.0  # 3mm radius for rounded edges
)

# Display in OCP CAD Viewer
show(compound)

print("Corner angle joint created successfully!")
print("This forms a clean 90-degree corner connection.")