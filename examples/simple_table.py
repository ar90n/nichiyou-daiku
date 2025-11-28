"""Simple table example - A basic four-legged table.

This example demonstrates how to build a simple table structure
with legs positioned inside a rectangular frame, similar to
traditional table construction.
"""

from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.anchor import Anchor
from nichiyou_daiku.core.anchor import BoundAnchor
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.geometry import FromMax, FromMin
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

# ============================================================================
# CREATE PIECES
# ============================================================================

# Four legs
leg_1 = Piece.of(PieceType.PT_2x4, TABLE_HEIGHT, "leg_1")
leg_2 = Piece.of(PieceType.PT_2x4, TABLE_HEIGHT, "leg_2")
leg_3 = Piece.of(PieceType.PT_2x4, TABLE_HEIGHT, "leg_3")
leg_4 = Piece.of(PieceType.PT_2x4, TABLE_HEIGHT, "leg_4")

# Aprons (horizontal supports between legs)
apron_front_back_length = TABLE_WIDTH - 2 * LEG_INSET_WIDTH
apron_left_right_length = TABLE_DEPTH - 2 * LEG_INSET_DEPTH

apron_front = Piece.of(PieceType.PT_2x4, apron_front_back_length, "apron_front")
apron_back = Piece.of(PieceType.PT_2x4, apron_front_back_length, "apron_back")
apron_left = Piece.of(PieceType.PT_2x4, apron_left_right_length, "apron_left")
apron_right = Piece.of(PieceType.PT_2x4, apron_left_right_length, "apron_right")

# Tabletop pieces
table_top_piece_num = 6
table_top_piece_interval = (
    apron_front_back_length - table_top_piece_num * get_shape(PieceType.PT_2x4).width
) / (table_top_piece_num + 1)
table_top_pieces = [
    Piece.of(PieceType.PT_2x4, TABLE_DEPTH, f"table_top_{i + 1}")
    for i in range(table_top_piece_num + 2)
]

# ============================================================================
# DEFINE CONNECTIONS
# ============================================================================
connections = []

# ----------------------------------------------------------------------------
# Front Apron Connections (connects leg_1 and leg_2)
# ----------------------------------------------------------------------------
connections.append(
    Connection(
        base=BoundAnchor(
            piece=leg_1,
            anchor=Anchor(
                contact_face="left", edge_shared_face="back", offset=FromMax(value=0)
            ),
        ),
        target=BoundAnchor(
            piece=apron_front,
            anchor=Anchor(
                contact_face="down", edge_shared_face="back", offset=FromMax(value=0)
            ),
        ),
    )
)

connections.append(
    Connection(
        base=BoundAnchor(
            piece=apron_front,
            anchor=Anchor(
                contact_face="top", edge_shared_face="front", offset=FromMax(value=0)
            ),
        ),
        target=BoundAnchor(
            piece=leg_2,
            anchor=Anchor(
                contact_face="right", edge_shared_face="front", offset=FromMax(value=0)
            ),
        ),
    )
)

# ----------------------------------------------------------------------------
# Back Apron Connections (connects leg_3 and leg_4)
# ----------------------------------------------------------------------------
connections.append(
    Connection(
        base=BoundAnchor(
            piece=leg_3,
            anchor=Anchor(
                contact_face="left", edge_shared_face="back", offset=FromMax(value=0)
            ),
        ),
        target=BoundAnchor(
            piece=apron_back,
            anchor=Anchor(
                contact_face="down", edge_shared_face="back", offset=FromMax(value=0)
            ),
        ),
    )
)

connections.append(
    Connection(
        base=BoundAnchor(
            piece=leg_4,
            anchor=Anchor(
                contact_face="right", edge_shared_face="front", offset=FromMax(value=0)
            ),
        ),
        target=BoundAnchor(
            piece=apron_back,
            anchor=Anchor(
                contact_face="top", edge_shared_face="front", offset=FromMax(value=0)
            ),
        ),
    )
)

# ----------------------------------------------------------------------------
# Left Apron Connections (connects leg_1 and leg_3)
# ----------------------------------------------------------------------------
connections.append(
    Connection(
        base=BoundAnchor(
            piece=leg_1,
            anchor=Anchor(
                contact_face="back",
                edge_shared_face="right",
                offset=FromMin(value=APRON_HEIGHT),
            ),
        ),
        target=BoundAnchor(
            piece=apron_left,
            anchor=Anchor(
                contact_face="down", edge_shared_face="back", offset=FromMin(value=0)
            ),
        ),
    )
)

connections.append(
    Connection(
        base=BoundAnchor(
            piece=leg_3,
            anchor=Anchor(
                contact_face="front",
                edge_shared_face="right",
                offset=FromMin(value=APRON_HEIGHT),
            ),
        ),
        target=BoundAnchor(
            piece=apron_left,
            anchor=Anchor(
                contact_face="top", edge_shared_face="back", offset=FromMin(value=0)
            ),
        ),
    )
)

# ----------------------------------------------------------------------------
# Right Apron Connections (connects leg_2 and leg_4)
# ----------------------------------------------------------------------------
connections.append(
    Connection(
        base=BoundAnchor(
            piece=leg_2,
            anchor=Anchor(
                contact_face="back",
                edge_shared_face="left",
                offset=FromMin(value=APRON_HEIGHT),
            ),
        ),
        target=BoundAnchor(
            piece=apron_right,
            anchor=Anchor(
                contact_face="down", edge_shared_face="front", offset=FromMin(value=0)
            ),
        ),
    )
)

connections.append(
    Connection(
        base=BoundAnchor(
            piece=leg_4,
            anchor=Anchor(
                contact_face="front",
                edge_shared_face="left",
                offset=FromMin(value=APRON_HEIGHT),
            ),
        ),
        target=BoundAnchor(
            piece=apron_right,
            anchor=Anchor(
                contact_face="top", edge_shared_face="front", offset=FromMin(value=0)
            ),
        ),
    )
)

# ----------------------------------------------------------------------------
# Tabletop Connections
# ----------------------------------------------------------------------------

# Edge pieces connect to legs
connections.append(
    Connection(
        base=BoundAnchor(
            piece=table_top_pieces[0],
            anchor=Anchor(
                contact_face="back", edge_shared_face="down", offset=FromMin(value=0)
            ),
        ),
        target=BoundAnchor(
            piece=leg_1,
            anchor=Anchor(
                contact_face="top", edge_shared_face="front", offset=FromMin(value=0)
            ),
        ),
    )
)

connections.append(
    Connection(
        base=BoundAnchor(
            piece=table_top_pieces[-1],
            anchor=Anchor(
                contact_face="back", edge_shared_face="down", offset=FromMin(value=0)
            ),
        ),
        target=BoundAnchor(
            piece=leg_2,
            anchor=Anchor(
                contact_face="top", edge_shared_face="front", offset=FromMin(value=0)
            ),
        ),
    )
)

# Middle pieces connect to front apron
for i in range(1, table_top_piece_num + 1):
    connections.append(
        Connection(
            base=BoundAnchor(
                piece=apron_front,
                anchor=Anchor(
                    contact_face="right",
                    edge_shared_face="front",
                    offset=FromMin(
                        value=(i - 1) * LEG_INSET_WIDTH + i * table_top_piece_interval
                    ),
                ),
            ),
            target=BoundAnchor(
                piece=table_top_pieces[i],
                anchor=Anchor(
                    contact_face="back", edge_shared_face="top", offset=FromMin(value=0)
                ),
            ),
        )
    )


# ============================================================================
# BUILD THE MODEL
# ============================================================================
model = Model.of(
    pieces=[
        leg_1,
        leg_2,
        leg_3,
        leg_4,
        apron_front,
        apron_back,
        apron_left,
        apron_right,
        *table_top_pieces,
    ],
    connections=connections,
    label="simple_table",
)

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
