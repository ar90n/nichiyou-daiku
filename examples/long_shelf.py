from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.anchor import Anchor
from nichiyou_daiku.core.anchor import BoundAnchor
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.screw import CoarseThreadScrew, as_spec
from nichiyou_daiku.core.geometry import FromMin
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.shell import assembly_to_build123d, extract_resources, generate_markdown_report

from ocp_vscode import show

# ============================================================================
# SHELF DIMENSIONS
# ============================================================================
SHELF_STAGES = 2
SHELF_BOTTOM_MARGIN = 150.0
SHELF_STAGE_HEIGHT = 300.0
SHELF_TOP_MARGIN = 28.0
SHELF_DEPTH = 420.0
EXPECTED_SHELF_WIDTH = 1025.0

LEG_INSET_DEPTH = get_shape(PieceType.PT_2x4).height
LEG_INSET_WIDTH = get_shape(PieceType.PT_2x4).width
APRON_HEIGHT = get_shape(PieceType.PT_2x4).width

# Table Top
SHELF_TOP_INTERVAL = get_shape(PieceType.PT_2x4).height
SHELF_TOP_PIECE_WIDTH = get_shape(PieceType.PT_2x4).width
SHELF_TOP_PIECES = (
    int(
        (EXPECTED_SHELF_WIDTH - 2 * LEG_INSET_DEPTH - SHELF_TOP_PIECE_WIDTH)
        // (SHELF_TOP_PIECE_WIDTH + SHELF_TOP_INTERVAL)
    )
    + 1
)
SHELF_TOP_HEIGHT = get_shape(PieceType.PT_1x4).height + APRON_HEIGHT

APRON_LENGTH = (
    SHELF_TOP_PIECES * (SHELF_TOP_PIECE_WIDTH + SHELF_TOP_INTERVAL) - SHELF_TOP_INTERVAL
)
SHELF_WIDTH = APRON_LENGTH + 2 * LEG_INSET_DEPTH
SHELF_HEIGHT = (
    SHELF_BOTTOM_MARGIN
    + SHELF_STAGES * (SHELF_STAGE_HEIGHT + SHELF_TOP_HEIGHT)
    + SHELF_TOP_HEIGHT
    + SHELF_TOP_MARGIN
)

# ============================================================================
# CREATE PIECES
# ============================================================================

# Four legs
legs = {
    k: Piece.of(PieceType.PT_2x4, SHELF_HEIGHT, f"leg_{k}")
    for k in [("left","front"), ("left","back"), ("right","front"), ("right","back")]
}

# Aprons
apron_fronts = [
    Piece.of(PieceType.PT_2x4, APRON_LENGTH, f"apron_front_{i}")
    for i in range(SHELF_STAGES + 1)
]
apron_backs = [
    Piece.of(PieceType.PT_2x4, APRON_LENGTH, f"apron_back_{i}")
    for i in range(SHELF_STAGES + 1)
]

# shelftop pieces
shelf_top_pieces = [
    [
        Piece.of(PieceType.PT_1x4, SHELF_DEPTH, f"shelf_top_{j}_{i}")
        for i in range(SHELF_TOP_PIECES)
    ]
    for j in range(SHELF_STAGES + 1)
]

# ============================================================================
# DEFINE CONNECTIONS
# ============================================================================
connections = []

# ----------------------------------------------------------------------------
# Shelf Top Connections
# ----------------------------------------------------------------------------
for i in range(SHELF_STAGES + 1):
    for j in range(SHELF_TOP_PIECES):
        connections.append(
            Connection.of_screw(
                target=BoundAnchor(
                    piece=shelf_top_pieces[i][j],
                    anchor=Anchor(
                        contact_face="back",
                        edge_shared_face="top",
                        offset=FromMin(value=0),
                    ),
                ),
                base=BoundAnchor(
                    piece=apron_fronts[i],
                    anchor=Anchor(
                        contact_face="right",
                        edge_shared_face="front",
                        offset=FromMin(
                            value=j * (SHELF_TOP_PIECE_WIDTH + SHELF_TOP_INTERVAL)
                        ),
                    ),
                ),
                spec=as_spec(CoarseThreadScrew.D3_8_L30)
            )
        )
        connections.append(
            Connection.of_screw(
                target=BoundAnchor(
                    piece=shelf_top_pieces[i][j],
                    anchor=Anchor(
                        contact_face="back",
                        edge_shared_face="down",
                        offset=FromMin(value=0),
                    ),
                ),
                base=BoundAnchor(
                    piece=apron_backs[i],
                    anchor=Anchor(
                        contact_face="right",
                        edge_shared_face="back",
                        offset=FromMin(
                            value=j * (SHELF_TOP_PIECE_WIDTH + SHELF_TOP_INTERVAL)
                        ),
                    ),
                ),
                spec=as_spec(CoarseThreadScrew.D3_8_L30),
            )
        )

# ----------------------------------------------------------------------------
# Leg Connections
# ----------------------------------------------------------------------------
for i in range(SHELF_STAGES + 1):
    # Front left leg
    connections.append(
        Connection.of_screw(
            target=BoundAnchor(
                piece=legs[("left","front")],
                anchor=Anchor(
                    contact_face="back",
                    edge_shared_face="left",
                    offset=FromMin(
                        value=SHELF_BOTTOM_MARGIN + i * (SHELF_STAGE_HEIGHT + SHELF_TOP_HEIGHT)
                    ),
                ),
            ),
            base=BoundAnchor(
                piece=apron_fronts[i],
                anchor=Anchor(
                    contact_face="down",
                    edge_shared_face="front",
                    offset=FromMin(value=0),
                ),
            ),
            spec=as_spec(CoarseThreadScrew.D4_2_L75)
        )
    )
    # Back left leg
    connections.append(
        Connection.of_screw(
            target=BoundAnchor(
                piece=legs[("left","back")],
                anchor=Anchor(
                    contact_face="back",
                    edge_shared_face="right",
                    offset=FromMin(
                        value=SHELF_BOTTOM_MARGIN + i * (SHELF_STAGE_HEIGHT + SHELF_TOP_HEIGHT)
                    ),
                ),
            ),
            base=BoundAnchor(
                piece=apron_backs[i],   
                anchor=Anchor(
                    contact_face="down",
                    edge_shared_face="back",
                    offset=FromMin(value=0),
                ),
            ),
            spec=as_spec(CoarseThreadScrew.D4_2_L75)
        )
    )
    # Front right leg
    connections.append(
        Connection.of_screw(
            target=BoundAnchor(
                piece=legs[("right","front")],
                anchor=Anchor(
                    contact_face="back",
                    edge_shared_face="right",
                    offset=FromMin(
                        value=SHELF_BOTTOM_MARGIN + i * (SHELF_STAGE_HEIGHT + SHELF_TOP_HEIGHT)
                    ),
                ),
            ),
            base=BoundAnchor(
                piece=apron_fronts[i],
                anchor=Anchor(
                    contact_face="top",
                    edge_shared_face="front",
                    offset=FromMin(value=0),
                ),
            ),
            spec=as_spec(CoarseThreadScrew.D4_2_L75)
        )
    )
    # Back right leg
    connections.append(
        Connection.of_screw(
            target=BoundAnchor(
                piece=legs[("right","back")],
                anchor=Anchor(
                    contact_face="back",
                    edge_shared_face="left",
                    offset=FromMin(
                        value=SHELF_BOTTOM_MARGIN + i * (SHELF_STAGE_HEIGHT + SHELF_TOP_HEIGHT)
                    ),
                ),
            ),
            base=BoundAnchor(     
                piece=apron_backs[i],
                anchor=Anchor(
                    contact_face="top",
                    edge_shared_face="back",
                    offset=FromMin(value=0),
                ),
            ),
            spec=as_spec(CoarseThreadScrew.D4_2_L75)
        )
    )   

# ============================================================================
# BUILD THE MODEL
# ============================================================================
model = Model.of(
    pieces=[
        *legs.values(),
        *apron_fronts,
        *apron_backs,
        *sum(shelf_top_pieces, []),
    ],
    connections=connections,
    label="long_Shelf",
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

# Generate comprehensive markdown report
print("\nGenerating detailed markdown report...")

# Define custom standard lengths for this project
custom_standard_lengths = {
    PieceType.PT_2x4: [1830.0],
    PieceType.PT_1x4: [1830.0],
}

report = generate_markdown_report(
    resources,
    project_name="DIY Long Shelf Project",
    standard_lengths=custom_standard_lengths,
    include_cut_diagram=True
)

# Save report to file
report_filename = "long_shelf_project_report.md"
with open(report_filename, "w", encoding="utf-8") as f:
    f.write(report)

print(f"✅ Detailed report saved to: {report_filename}")
print("📋 Report includes cut optimization and purchase recommendations")

# ============================================================================
# VISUALIZE
# ============================================================================
# Export with smaller fillet radius for sharper edges
compound = assembly_to_build123d(assembly, fillet_radius=2.0)

# Display the result
show(compound)
