"""Simple Table Example - Python API

Demonstrates furniture design using nichiyou-daiku Python API.
Equivalent to the side-table.nd DSL example, with the lengths and offsets
computed from the overall dimensions.

Dimensions: 500mm (W) x 400mm (D) x 600mm (H)
Material: 2x4
Joints: Dowel 8x30
"""

from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.dowel import Dowel, as_spec as dowel_spec
from nichiyou_daiku.core.geometry import Face, FromMax, FromMin
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.piece import Piece, PieceType, get_shape

# Constants
WIDTH = 500.0  # mm
DEPTH = 400.0  # mm
HEIGHT = 600.0  # mm
TOP_BOARDS = 5

LUMBER = get_shape(PieceType.PT_2x4)  # width 89mm, thickness (height) 38mm
LEG_LENGTH = HEIGHT - LUMBER.height  # the top boards sit on the legs: 562mm
APRON_FRONT_BACK = WIDTH - 2 * LUMBER.width  # between the legs' 89mm sides: 322mm
APRON_LEFT_RIGHT = DEPTH - 2 * LUMBER.height  # between the legs' 38mm sides: 324mm
SIDE_APRON_OFFSET = LEG_LENGTH - LUMBER.width  # flush with the top: 473mm
TOP_GAP = (WIDTH - TOP_BOARDS * LUMBER.width) / (TOP_BOARDS - 1)  # 13.75mm

DOWEL = dowel_spec(Dowel.D8_L30)


def create_pieces() -> dict[str, Piece]:
    """Create all furniture pieces."""
    pieces = {}

    # Legs (4x)
    for name in ["leg_fl", "leg_fr", "leg_bl", "leg_br"]:
        pieces[name] = Piece.of(PieceType.PT_2x4, LEG_LENGTH, name)

    # Aprons
    for name in ["apron_front", "apron_back"]:
        pieces[name] = Piece.of(PieceType.PT_2x4, APRON_FRONT_BACK, name)
    for name in ["apron_left", "apron_right"]:
        pieces[name] = Piece.of(PieceType.PT_2x4, APRON_LEFT_RIGHT, name)

    # Top boards, running in the depth direction
    for i in range(1, TOP_BOARDS + 1):
        pieces[f"top_{i}"] = Piece.of(PieceType.PT_2x4, DEPTH, f"top_{i}")

    return pieces


def dowel_joint(
    base: Piece,
    base_anchor: tuple[Face, Face, FromMin | FromMax],
    target: Piece,
    target_anchor: tuple[Face, Face, FromMin | FromMax],
) -> Connection:
    """Connect two pieces with 8x30 dowels.

    Each anchor is (contact_face, edge_shared_face, offset).
    """
    return Connection.of_dowel(
        base=BoundAnchor(piece=base, anchor=Anchor.of(*base_anchor)),
        target=BoundAnchor(piece=target, anchor=Anchor.of(*target_anchor)),
        spec=DOWEL,
    )


def create_connections(pieces: dict[str, Piece]) -> list[Connection]:
    """Create all connections."""
    p = pieces
    flush_top = FromMax(value=0)
    side_apron = FromMin(value=SIDE_APRON_OFFSET)
    start = FromMin(value=0)

    connections = [
        # Front and back aprons to legs (flush with top)
        dowel_joint(
            p["leg_fl"],
            ("left", "back", flush_top),
            p["apron_front"],
            ("down", "back", flush_top),
        ),
        dowel_joint(
            p["leg_fr"],
            ("right", "front", flush_top),
            p["apron_front"],
            ("top", "front", flush_top),
        ),
        dowel_joint(
            p["leg_bl"],
            ("left", "back", flush_top),
            p["apron_back"],
            ("down", "back", flush_top),
        ),
        dowel_joint(
            p["leg_br"],
            ("right", "front", flush_top),
            p["apron_back"],
            ("top", "front", flush_top),
        ),
        # Side aprons to the legs' front/back faces (flush with top)
        dowel_joint(
            p["leg_fl"],
            ("back", "right", side_apron),
            p["apron_left"],
            ("down", "back", start),
        ),
        dowel_joint(
            p["leg_bl"],
            ("front", "right", side_apron),
            p["apron_left"],
            ("top", "back", start),
        ),
        dowel_joint(
            p["leg_fr"],
            ("back", "left", side_apron),
            p["apron_right"],
            ("down", "front", start),
        ),
        dowel_joint(
            p["leg_br"],
            ("front", "left", side_apron),
            p["apron_right"],
            ("top", "front", start),
        ),
        # End top boards sit on the front legs
        dowel_joint(
            p["top_1"], ("back", "down", start), p["leg_fl"], ("top", "front", start)
        ),
        dowel_joint(
            p[f"top_{TOP_BOARDS}"],
            ("back", "down", start),
            p["leg_fr"],
            ("top", "front", start),
        ),
    ]

    # Middle top boards sit on the front apron, one gap + one board apart
    for i in range(2, TOP_BOARDS):
        offset = FromMin(value=TOP_GAP + (i - 2) * (LUMBER.width + TOP_GAP))
        connections.append(
            dowel_joint(
                p["apron_front"],
                ("right", "front", offset),
                p[f"top_{i}"],
                ("back", "top", start),
            )
        )

    return connections


def main():
    """Build the table model and assembly."""
    # Create pieces
    pieces = create_pieces()

    # Create connections
    connections = create_connections(pieces)

    # Build model
    model = Model.of(
        pieces=list(pieces.values()),
        connections=connections,
        label="Simple Table",
    )

    # Build assembly
    assembly = Assembly.of(model)

    print(f"Model: {model.label}")
    print(f"Pieces: {len(model.pieces)}")
    print(f"Connections: {len(model.connections)}")

    return assembly


if __name__ == "__main__":
    main()
