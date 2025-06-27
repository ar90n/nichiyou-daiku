# %%
"""Simple table example - A basic four-legged table.

This example demonstrates how to build a simple table structure
with legs positioned inside a rectangular frame, similar to
traditional table construction.
"""

from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
from nichiyou_daiku.core.model import Model, PiecePair
from nichiyou_daiku.core.connection import Connection, BasePosition, Anchor
from nichiyou_daiku.core.geometry import Edge, EdgePoint, FromMax, FromMin
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.shell import assembly_to_build123d

from ocp_vscode import show

# Table dimensions (in millimeters)
TABLE_WIDTH = 800.0    # 80cm wide
TABLE_DEPTH = 600.0    # 60cm deep
TABLE_HEIGHT = 720.0   # 72cm tall (standard dining table height)
LEG_INSET_DEPTH = get_shape(PieceType.PT_2x4).height
LEG_INSET_WIDTH = get_shape(PieceType.PT_2x4).width

# Create pieces
# Four legs
leg_1 = Piece.of(PieceType.PT_2x4, TABLE_HEIGHT, "leg_1")
leg_2 = Piece.of(PieceType.PT_2x4, TABLE_HEIGHT, "leg_2")
leg_3 = Piece.of(PieceType.PT_2x4, TABLE_HEIGHT, "leg_3")
leg_4 = Piece.of(PieceType.PT_2x4, TABLE_HEIGHT, "leg_4")

# Aprons (horizontal supports between legs)
# These run between the legs to form the table frame
apron_front_back_length = TABLE_WIDTH - 2 * LEG_INSET_WIDTH
apron_left_right_length = TABLE_DEPTH - 2 * LEG_INSET_DEPTH
apron_front = Piece.of(PieceType.PT_2x4, apron_front_back_length, "apron_front")
apron_back = Piece.of(PieceType.PT_2x4, apron_front_back_length, "apron_back")
apron_left = Piece.of(PieceType.PT_2x4, apron_left_right_length, "apron_left")
apron_right = Piece.of(PieceType.PT_2x4, apron_left_right_length, "apron_right")

# Tabletop
table_top_piece_num = 6
table_top_piece_interval = (apron_front_back_length - table_top_piece_num * get_shape(PieceType.PT_2x4).width) / (table_top_piece_num + 1)
table_top_pieces = [
    Piece.of(PieceType.PT_2x4, TABLE_DEPTH, f"table_top_{i + 1}")
    for i in range(table_top_piece_num + 2)
]

# Define connections
connections = []

# Connect aprons to legs
# The aprons connect near the top of the legs (just below where tabletop would go)
APRON_HEIGHT = 100.0  # Distance from top of leg to apron


connections.append((
    PiecePair(base=leg_1, target=apron_front),
    Connection.of(
        base=BasePosition(
            face="left",
            offset=FromMax(value=0)
        ),
        target=Anchor(
            face="bottom",
            edge_point=EdgePoint(
                edge=Edge(lhs="back", rhs="bottom"),
                offset=FromMax(value=0)
            )
        )
    )
))
# Front apron connects leg_1 and leg_2
connections.append((
    PiecePair(base=leg_2, target=apron_front),
    Connection.of(
        base=BasePosition(
            face="right",
            offset=FromMax(value=0)
        ),
        target=Anchor(
            face="top",
            edge_point=EdgePoint(
                edge=Edge(lhs="front", rhs="top"),
                offset=FromMax(value=0)
            )
        )
    )
))

# Back apron connects leg_3 and leg_4
connections.append((
    PiecePair(base=leg_3, target=apron_back),
    Connection.of(
        base=BasePosition(
            face="left",
            offset=FromMax(value=0)
        ),
        target=Anchor(
            face="bottom",
            edge_point=EdgePoint(
                edge=Edge(lhs="back", rhs="bottom"),
                offset=FromMax(value=0)
            )
        )
    )
))

connections.append((
    PiecePair(base=leg_4, target=apron_back),
    Connection.of(
        base=BasePosition(
            face="right",
            offset=FromMax(value=0)
        ),
        target=Anchor(
            face="top",
            edge_point=EdgePoint(
                edge=Edge(lhs="front", rhs="top"),
                offset=FromMax(value=0)
            )
        )
    )
))

## Left apron connects leg_1 and leg_3
connections.append((
    PiecePair(base=leg_1, target=apron_left),
    Connection.of(
        base=BasePosition(
            face="back",
            offset=FromMin(value=APRON_HEIGHT)
        ),
        target=Anchor(
            face="bottom",
            edge_point=EdgePoint(
                edge=Edge(lhs="front", rhs="bottom"),
                offset=FromMin(value=0)
            )
        )
    )
))

connections.append((
    PiecePair(base=leg_3, target=apron_left),
    Connection.of(
        base=BasePosition(
            face="front",
            offset=FromMin(value=APRON_HEIGHT)
        ),
        target=Anchor(
            face="top",
            edge_point=EdgePoint(
                edge=Edge(lhs="top", rhs="front"),
                offset=FromMin(value=0)
            )
        )
    )
))

# Right apron connects leg_2 and leg_4
connections.append((
    PiecePair(base=leg_2, target=apron_right),
    Connection.of(
        base=BasePosition(
            face="back",
            offset=FromMin(value=APRON_HEIGHT)
        ),
        target=Anchor(
            face="bottom",
            edge_point=EdgePoint(
                edge=Edge(lhs="bottom", rhs="back"),
                offset=FromMin(value=0)
            )
        )
    )
))

connections.append((
    PiecePair(base=leg_4, target=apron_right),
    Connection.of(
        base=BasePosition(
            face="front",
            offset=FromMin(value=APRON_HEIGHT)
        ),
        target=Anchor(
            face="top",
            edge_point=EdgePoint(
                edge=Edge(lhs="back", rhs="top"),
                offset=FromMin(value=0)
            )
        )
    )
))

connections.append((
    PiecePair(base=table_top_pieces[0], target=leg_1),
    Connection.of(
        base=BasePosition(
            face="back",
            offset=FromMin(value=0)
        ),
        target=Anchor(
            face="top",
            edge_point=EdgePoint(
                edge=Edge(lhs="top", rhs="left"),
                offset=FromMin(value=0)
            )
        )
    )
))

connections.append((
    PiecePair(base=table_top_pieces[-1], target=leg_2),
    Connection.of(
        base=BasePosition(
            face="back",
            offset=FromMin(value=0)
        ),
        target=Anchor(
            face="top",
            edge_point=EdgePoint(
                edge=Edge(lhs="top", rhs="left"),
                offset=FromMin(value=0)
            )
        )
    )
))

for i in range(1, table_top_piece_num + 1):
    connections.append((
        PiecePair(base=apron_front, target=table_top_pieces[i]),
        Connection.of(
            base=BasePosition(
                face="right",
                offset=FromMin(value=(i - 1) * LEG_INSET_WIDTH + i * table_top_piece_interval)
            ),
            target=Anchor(
                face="back",
                edge_point=EdgePoint(
                    edge=Edge(lhs="top", rhs="back"),
                    offset=FromMin(value=0)
                )
            )
        )
    ))



# Create the model
model = Model.of(
    pieces=[
        leg_1, leg_2, leg_3, leg_4,
        apron_front, apron_back, apron_left, apron_right,
        *table_top_pieces
    ],
    connections=connections,
    label="simple_table"
)

# Convert to assembly and visualize
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
