"""Minimal L-angle example."""

from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.model import Model, BaseTargetPair
from nichiyou_daiku.core.connection import Connection, BasePosition, FromTopOffset, Anchor
from nichiyou_daiku.core.geometry import Edge, EdgePoint
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.shell import assembly_to_build123d

# Create two 2x4 pieces
vertical = Piece.of(PieceType.PT_2x4, 600.0)
horizontal = Piece.of(PieceType.PT_2x4, 400.0)

# Connect horizontal to top of vertical
connection = Connection.of(
    BasePosition(face="top", offset=FromTopOffset(value=44.5)),
    Anchor(face="bottom", edge_point=EdgePoint(edge=Edge(lhs="bottom", rhs="back"), value=44.5))
)

# Build assembly
model = Model.of(
    [vertical, horizontal],
    [(BaseTargetPair(base=vertical, target=horizontal), connection)]
)
assembly = Assembly.of(model)

# Export and show
compound = assembly_to_build123d(assembly)

from ocp_vscode import show
show(compound)