# %%
from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.anchor import Anchor
from nichiyou_daiku.core.anchor import BoundAnchor
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.geometry import FromMax, FromMin, Offset
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
SHELF_HEIGHT = 750.0  # 72cm tall (standard dining table height)

# Apron positioning
BOTTOM_APRON_HEIGHT = FromMin(value=150.0)  # Distance from bottom of leg to apron
TOP_APRON_HEIGHT = FromMax(value=250.0)  # Distance from top of leg to apron

# ============================================================================
# CREATE PIECES
# ============================================================================

# Four legs
legs = {
    pos: Piece.of(PieceType.PT_2x4, SHELF_HEIGHT, f"leg_{pos}")
    for pos in ("left_front", "right_front", "left_back", "right_back")
}

# Aprons (horizontal supports between legs)
apron_front_back_length = _calc_apron_length(
    SHELF_WIDTH, get_shape(PieceType.PT_2x4).height
)
apron_left_right_length = _calc_apron_length(
    SHELF_DEPTH, get_shape(PieceType.PT_2x4).width
)

# bottom aprons
bottom_table_top_aprons = {
    pos: Piece.of(
        PieceType.PT_2x4, apron_front_back_length, f"bottom_table_top_apron_{pos}"
    )
    for pos in ("front", "back")
}

bottom_aprons = {
    **{
        pos: Piece.of(PieceType.PT_2x4, apron_left_right_length, f"bottom_apron_{pos}")
        for pos in ("left", "right")
    },
    "back": Piece.of(PieceType.PT_2x4, apron_front_back_length, "bottom_apron_back"),
}

# top aprons
top_table_top_aprons = {
    pos: Piece.of(
        PieceType.PT_2x4, apron_front_back_length, f"top_table_top_apron_{pos}"
    )
    for pos in ("front", "back")
}

top_aprons = {
    **{
        pos: Piece.of(PieceType.PT_2x4, apron_left_right_length, f"top_apron_{pos}")
        for pos in ("left", "right")
    },
    **{
        pos: Piece.of(PieceType.PT_2x4, apron_front_back_length, f"top_apron_{pos}")
        for pos in ("front", "back")
    },
}

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

# tabletop pieces
bottom_table_top_pieces = [
    Piece.of(PieceType.PT_1x4, SHELF_DEPTH, f"bottom_table_top_{i}")
    for i in range(table_top_piece_num)
]

top_table_top_pieces = [
    Piece.of(PieceType.PT_1x4, SHELF_DEPTH, f"top_table_top_{i}")
    for i in range(table_top_piece_num)
]

# ============================================================================
# DEFINE CONNECTIONS
# ============================================================================
connections = []


# ----------------------------------------------------------------------------
# Front Apron Connections (connects leg_1 and leg_2)
# ----------------------------------------------------------------------------

for leg_pos, apron_pos in [
    ("left_front", "front"),
    ("left_back", "back"),
]:
    connections.extend(
        [
            Connection(
                base=BoundAnchor(
                    piece=f"leg_{leg_pos}",
                    anchor=Anchor(
                        contact_face="back",
                        edge_shared_face="left",
                        offset=BOTTOM_APRON_HEIGHT,
                    ),
                ),
                target=BoundAnchor(
                    piece=f"bottom_table_top_apron_{apron_pos}",
                    anchor=Anchor(
                        contact_face="down",
                        edge_shared_face="right",
                        offset=FromMin(value=0),
                    ),
                ),
            ),
            Connection(
                base=BoundAnchor(
                    piece=f"leg_{leg_pos}",
                    anchor=Anchor(
                        contact_face="back",
                        edge_shared_face="left",
                        offset=TOP_APRON_HEIGHT,
                    ),
                ),
                target=BoundAnchor(
                    piece=f"top_table_top_apron_{apron_pos}",
                    anchor=Anchor(
                        contact_face="down",
                        edge_shared_face="right",
                        offset=FromMax(value=0),
                    ),
                ),
            ),
        ]
    )

for leg_pos, apron_pos in [
    ("right_front", "front"),
    ("right_back", "back"),
]:
    connections.extend(
        [
            Connection(
                base=BoundAnchor(
                    piece=f"leg_{leg_pos}",
                    anchor=Anchor(
                        contact_face="front",
                        edge_shared_face="right",
                        offset=BOTTOM_APRON_HEIGHT,
                    ),
                ),
                target=BoundAnchor(
                    piece=f"bottom_table_top_apron_{apron_pos}",
                    anchor=Anchor(
                        contact_face="top",
                        edge_shared_face="left",
                        offset=FromMin(value=0),
                    ),
                ),
            ),
            Connection(
                base=BoundAnchor(
                    piece=f"leg_{leg_pos}",
                    anchor=Anchor(
                        contact_face="front",
                        edge_shared_face="right",
                        offset=TOP_APRON_HEIGHT,
                    ),
                ),
                target=BoundAnchor(
                    piece=f"top_table_top_apron_{apron_pos}",
                    anchor=Anchor(
                        contact_face="top",
                        edge_shared_face="left",
                        offset=FromMax(value=0),
                    ),
                ),
            ),
        ]
    )

connections.extend(
    [
        Connection(
            base=BoundAnchor(
                piece="leg_left_front",
                anchor=Anchor(
                    contact_face="right",
                    edge_shared_face="front",
                    offset=FromMin(value=BOTTOM_APRON_HEIGHT.value + 150.0),
                ),
            ),
            target=BoundAnchor(
                piece="bottom_apron_left",
                anchor=Anchor(
                    contact_face="top",
                    edge_shared_face="front",
                    offset=FromMax(value=0),
                ),
            ),
        ),
        Connection(
            base=BoundAnchor(
                piece="leg_left_front",
                anchor=Anchor(
                    contact_face="right",
                    edge_shared_face="front",
                    offset=FromMax(value=0),
                ),
            ),
            target=BoundAnchor(
                piece="top_apron_left",
                anchor=Anchor(
                    contact_face="top",
                    edge_shared_face="front",
                    offset=FromMax(value=0),
                ),
            ),
        ),
        Connection(
            base=BoundAnchor(
                piece="leg_right_front",
                anchor=Anchor(
                    contact_face="right",
                    edge_shared_face="back",
                    offset=FromMin(value=BOTTOM_APRON_HEIGHT.value + 150.0),
                ),
            ),
            target=BoundAnchor(
                piece="bottom_apron_right",
                anchor=Anchor(
                    contact_face="down",
                    edge_shared_face="front",
                    offset=FromMax(value=0),
                ),
            ),
        ),
        Connection(
            base=BoundAnchor(
                piece="leg_right_front",
                anchor=Anchor(
                    contact_face="right",
                    edge_shared_face="back",
                    offset=FromMax(value=0),
                ),
            ),
            target=BoundAnchor(
                piece="top_apron_right",
                anchor=Anchor(
                    contact_face="down",
                    edge_shared_face="front",
                    offset=FromMax(value=0),
                ),
            ),
        ),
        Connection(
            base=BoundAnchor(
                piece="leg_left_back",
                anchor=Anchor(
                    contact_face="back",
                    edge_shared_face="right",
                    offset=FromMin(value=BOTTOM_APRON_HEIGHT.value + 150.0),
                ),
            ),
            target=BoundAnchor(
                piece="bottom_apron_back",
                anchor=Anchor(
                    contact_face="down",
                    edge_shared_face="back",
                    offset=FromMax(value=0),
                ),
            ),
        ),
        Connection(
            base=BoundAnchor(
                piece="leg_left_back",
                anchor=Anchor(
                    contact_face="back",
                    edge_shared_face="right",
                    offset=FromMax(value=0),
                ),
            ),
            target=BoundAnchor(
                piece="top_apron_back",
                anchor=Anchor(
                    contact_face="down",
                    edge_shared_face="back",
                    offset=FromMax(value=0),
                ),
            ),
        ),
        Connection(
            base=BoundAnchor(
                piece="leg_left_front",
                anchor=Anchor(
                    contact_face="back",
                    edge_shared_face="left",
                    offset=FromMax(value=0),
                ),
            ),
            target=BoundAnchor(
                piece="top_apron_front",
                anchor=Anchor(
                    contact_face="down",
                    edge_shared_face="front",
                    offset=FromMax(value=0),
                ),
            ),
        ),
    ]
)


# Middle pieces connect to front apron
def _get_too_piece_offset(ind: int, piece: Piece, interval: float) -> Offset:
    return ind * (get_shape(piece).width + interval)


def _connect_top_pieces(
    top_pieces: list[Piece], front_apron: Piece, back_apron: Piece, offset: float
) -> list[Connection]:
    return [
        *[
            Connection(
                base=BoundAnchor(
                    piece=front_apron.id,
                    anchor=Anchor(
                        contact_face="back",
                        edge_shared_face="right",
                        offset=FromMin(
                            value=_get_too_piece_offset(i, top_piece, offset)
                        ),
                    ),
                ),
                target=BoundAnchor(
                    piece=top_piece.id,
                    anchor=Anchor(
                        contact_face="back",
                        edge_shared_face="top",
                        offset=FromMin(value=0),
                    ),
                ),
            )
            for i, top_piece in enumerate(top_pieces)
        ],
        *[
            Connection(
                base=BoundAnchor(
                    piece=back_apron.id,
                    anchor=Anchor(
                        contact_face="back",
                        edge_shared_face="left",
                        offset=FromMin(
                            value=_get_too_piece_offset(
                                i, top_piece, table_top_piece_interval
                            )
                        ),
                    ),
                ),
                target=BoundAnchor(
                    piece=top_piece.id,
                    anchor=Anchor(
                        contact_face="back",
                        edge_shared_face="down",
                        offset=FromMin(value=0),
                    ),
                ),
            )
            for i, top_piece in enumerate(top_pieces)
        ],
    ]


connections.extend(
    _connect_top_pieces(
        bottom_table_top_pieces,
        bottom_table_top_aprons["front"],
        bottom_table_top_aprons["back"],
        table_top_piece_interval,
    )
)

connections.extend(
    _connect_top_pieces(
        top_table_top_pieces,
        top_table_top_aprons["front"],
        top_table_top_aprons["back"],
        table_top_piece_interval,
    )
)


# ============================================================================
# BUILD THE MODEL
# ============================================================================
model = Model.of(
    pieces=[
        *legs.values(),
        *bottom_aprons.values(),
        *top_aprons.values(),
        *bottom_table_top_aprons.values(),
        *top_table_top_aprons.values(),
        *bottom_table_top_pieces,
        *top_table_top_pieces,
    ],
    connections=connections,
    label="shelf",
)

# ============================================================================
# CREATE ASSEMBLY AND EXTRACT RESOURCES
# ============================================================================
print("Creating assembly...")
assembly = Assembly.of(model)

print("Extracting bill of materials...")
resources = extract_resources(assembly)

# Display resource summary
print("\n" + resources.pretty_print())

# Export to JSON
json_data = resources.model_dump_json(indent=2)
print("\nJSON Export (first 500 chars):")
print(json_data[:500] + "..." if len(json_data) > 500 else json_data)

# Generate comprehensive markdown report
print("\nGenerating detailed markdown report...")

# Define custom standard lengths for this project
custom_standard_lengths = {
    PieceType.PT_2x4: [2440.0, 3000.0, 3600.0],  # 8ft, ~10ft, 12ft
    PieceType.PT_1x4: [1800.0, 2400.0, 3000.0],  # 6ft, 8ft, 10ft
}

report = generate_markdown_report(
    resources,
    project_name="DIY Shelf Project",
    standard_lengths=custom_standard_lengths,
    include_cut_diagram=True,
)

# Print report preview (not saving to file to avoid generated artifacts)
print("✅ Report generated successfully")
print("📋 Report includes cut optimization and purchase recommendations")

# Show a preview of the report
print("\n" + "=" * 60)
print("REPORT PREVIEW:")
print("=" * 60)
print(report[:800] + "\n..." if len(report) > 800 else report)

# ============================================================================
# VISUALIZE
# ============================================================================
print("\n\nBuilding 3D visualization...")

# Export with smaller fillet radius for sharper edges
compound = assembly_to_build123d(assembly, fillet_radius=2.0)

# Display the result
show(compound)

print("\nShelf assembly complete!")
print(f"Shelf dimensions: {SHELF_WIDTH}mm x {SHELF_DEPTH}mm x {SHELF_HEIGHT}mm")
print(f"Using {len(model.pieces)} pieces with {len(model.connections)} connections")
