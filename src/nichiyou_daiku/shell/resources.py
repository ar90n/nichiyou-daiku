"""Resource extraction from woodworking assemblies.

This module provides functionality to extract and summarize the resources
(lumber pieces) required for a woodworking project from an Assembly.
"""

from typing import Dict

from pydantic import BaseModel, ConfigDict

from nichiyou_daiku.core.assembly import Assembly, Hole
from nichiyou_daiku.core.geometry import Point3D, Box
from nichiyou_daiku.core.piece import PieceType, get_shape
from nichiyou_daiku.shell.utils import detect_face_from_point


class AnchorInfo(BaseModel):
    """Anchor position information for a piece (for fabrication).

    Represents a connection point on a piece, specified by the contact face,
    edge shared face, and offset from the edge.

    Attributes:
        contact_face: The face where connection occurs (e.g., "front", "down")
        edge_shared_face: The face that defines the edge position (e.g., "top", "front")
        offset_type: Type of offset ("FromMin" or "FromMax")
        offset_value: Offset distance in millimeters

    Examples:
        >>> anchor = AnchorInfo(
        ...     contact_face="front",
        ...     edge_shared_face="top",
        ...     offset_type="FromMax",
        ...     offset_value=100.0
        ... )
        >>> anchor.contact_face
        'front'
        >>> anchor.offset_value
        100.0
    """

    contact_face: str
    edge_shared_face: str
    offset_type: str  # "FromMin" or "FromMax"
    offset_value: float  # mm


class PilotHoleInfo(BaseModel):
    """Pilot hole information for drilling guidance.

    Represents a pilot hole position on a piece surface, with coordinates
    expressed as distances from edges for easy measurement during fabrication.

    Attributes:
        face: The face where the hole is located (e.g., "top", "back")
        from_length_edge: Distance from the length edge in millimeters
        from_width_edge: Distance from the width edge in millimeters
        diameter: Hole diameter in millimeters
        depth: Hole depth in millimeters (None for through-hole)

    Examples:
        >>> hole = PilotHoleInfo(
        ...     face="top",
        ...     from_length_edge=70.0,
        ...     from_width_edge=19.0,
        ...     diameter=3.0,
        ...     depth=15.0
        ... )
        >>> hole.face
        'top'
        >>> hole.diameter
        3.0
    """

    face: str
    from_length_edge: float  # mm - distance along length axis
    from_width_edge: float  # mm - distance along width axis
    diameter: float  # mm
    depth: float | None  # mm, None for through-hole


class PieceResource(BaseModel):
    """Resource information for a single piece of lumber.

    Attributes:
        id: Unique identifier for the piece
        type: Type of lumber (e.g., PT_2x4, PT_1x4)
        length: Length in millimeters
        width: Actual width in millimeters
        height: Actual height in millimeters
        volume: Calculated volume in cubic millimeters
        anchors: List of anchor positions on this piece

    Examples:
        >>> from nichiyou_daiku.core.piece import PieceType
        >>> resource = PieceResource(
        ...     id="leg-1",
        ...     type=PieceType.PT_2x4,
        ...     length=750.0,
        ...     width=89.0,
        ...     height=38.0,
        ...     volume=2_536_500.0
        ... )
        >>> resource.type
        <PieceType.PT_2x4: '2x4'>
        >>> resource.volume
        2536500.0
        >>> len(resource.anchors)
        0
        >>> len(resource.pilot_holes)
        0
    """

    id: str
    type: PieceType
    length: float  # mm
    width: float  # mm
    height: float  # mm
    volume: float  # mm³
    anchors: list[AnchorInfo] = []
    pilot_holes: list[PilotHoleInfo] = []


class ResourceSummary(BaseModel):
    """Summary of all resources required for a project.

    Provides aggregated information about lumber requirements including
    counts by type, total lengths, and volumes.

    Attributes:
        pieces: List of all individual piece resources
        total_pieces: Total count of pieces
        pieces_by_type: Count of pieces grouped by lumber type
        total_length_by_type: Total length needed for each lumber type
        total_volume: Total volume of all lumber in cubic millimeters

    Examples:
        >>> from nichiyou_daiku.core.piece import PieceType
        >>> pieces = [
        ...     PieceResource(
        ...         id="p1", type=PieceType.PT_2x4, length=1000.0,
        ...         width=89.0, height=38.0, volume=3_382_000.0
        ...     ),
        ...     PieceResource(
        ...         id="p2", type=PieceType.PT_2x4, length=800.0,
        ...         width=89.0, height=38.0, volume=2_705_600.0
        ...     )
        ... ]
        >>> summary = ResourceSummary(
        ...     pieces=pieces,
        ...     total_pieces=2,
        ...     pieces_by_type={PieceType.PT_2x4: 2},
        ...     total_length_by_type={PieceType.PT_2x4: 1800.0},
        ...     total_volume=6_087_600.0
        ... )
        >>> summary.total_pieces
        2
        >>> summary.total_length_by_type[PieceType.PT_2x4]
        1800.0
    """

    pieces: list[PieceResource]
    total_pieces: int
    pieces_by_type: Dict[PieceType, int]
    total_length_by_type: Dict[PieceType, float]
    total_volume: float

    model_config = ConfigDict(
        # Ensure proper JSON serialization
    )

    def pretty_print(self) -> str:
        """Generate a human-readable summary of resources.

        Returns:
            Formatted string with resource summary

        Examples:
            >>> from nichiyou_daiku.core.piece import PieceType
            >>> summary = ResourceSummary(
            ...     pieces=[],
            ...     total_pieces=2,
            ...     pieces_by_type={PieceType.PT_2x4: 2},
            ...     total_length_by_type={PieceType.PT_2x4: 1800.0},
            ...     total_volume=6_087_600.0
            ... )
            >>> print(summary.pretty_print())  # doctest: +NORMALIZE_WHITESPACE
            Resource Summary
            ===============
            Total pieces: 2
            <BLANKLINE>
            By lumber type:
              2x4: 2 pieces (total length: 1800.0mm)
            <BLANKLINE>
            Total volume: 6,087,600.0 mm³
        """
        lines = [
            "Resource Summary",
            "===============",
            f"Total pieces: {self.total_pieces}",
            "",
            "By lumber type:",
        ]

        for piece_type, count in sorted(
            self.pieces_by_type.items(), key=lambda x: x[0].value
        ):
            total_length = self.total_length_by_type[piece_type]
            lines.append(
                f"  {piece_type.value}: {count} pieces (total length: {total_length}mm)"
            )

        lines.extend(["", f"Total volume: {self.total_volume:,.1f} mm³"])

        return "\n".join(lines)


def _point3d_to_pilot_hole_info(
    point: Point3D, hole: Hole, box: Box
) -> "PilotHoleInfo":
    """Convert a Point3D and Hole to PilotHoleInfo with edge distances.

    Converts 3D coordinates to distances from edges based on the face.
    The coordinate system is designed so that side faces (left/right/front/back)
    all use z (length) as the horizontal axis for consistent comparison.

    Face coordinate mappings:
        - top/down: from_length_edge=x, from_width_edge=y
        - left/right: from_length_edge=z, from_width_edge=y
        - front/back: from_length_edge=z, from_width_edge=x

    Args:
        point: 3D position of the hole
        hole: Hole specification (diameter, depth)
        box: Box for dimension reference

    Returns:
        PilotHoleInfo with face and edge distances
    """
    face = detect_face_from_point(point, box)

    # Map face to edge distances
    # from_length_edge: distance along the length axis of the piece
    # from_width_edge: distance along the width axis of the piece
    if face in ("top", "down"):
        from_length_edge = point.x
        from_width_edge = point.y
    elif face in ("left", "right"):
        from_length_edge = point.z
        from_width_edge = point.y
    else:  # front, back
        from_length_edge = point.z
        from_width_edge = point.x

    return PilotHoleInfo(
        face=face,
        from_length_edge=from_length_edge,
        from_width_edge=from_width_edge,
        diameter=hole.diameter,
        depth=hole.depth,
    )


def extract_resources(assembly: Assembly) -> ResourceSummary:
    """Extract all required resources from an Assembly.

    Analyzes a woodworking assembly and produces a comprehensive summary
    of all lumber pieces required, including their dimensions and
    aggregated statistics. Also extracts anchor positions for fabrication.

    Args:
        assembly: The woodworking assembly to analyze

    Returns:
        ResourceSummary containing detailed piece information and statistics

    Examples:
        >>> from nichiyou_daiku.core.model import Model
        >>> from nichiyou_daiku.core.assembly import Assembly
        >>> from nichiyou_daiku.core.piece import Piece, PieceType
        >>> pieces = [
        ...     Piece.of(PieceType.PT_2x4, 1000.0, "p1"),
        ...     Piece.of(PieceType.PT_2x4, 800.0, "p2"),
        ...     Piece.of(PieceType.PT_1x4, 600.0, "p3")
        ... ]
        >>> model = Model.of(pieces=pieces, connections=[])
        >>> assembly = Assembly.of(model)
        >>> resources = extract_resources(assembly)
        >>> resources.total_pieces
        3
        >>> resources.pieces_by_type[PieceType.PT_2x4]
        2
        >>> resources.pieces_by_type[PieceType.PT_1x4]
        1
        >>> resources.total_length_by_type[PieceType.PT_2x4]
        1800.0
        >>> resources.total_length_by_type[PieceType.PT_1x4]
        600.0
    """
    # Extract anchor information from connections via model
    piece_anchors: Dict[str, list[AnchorInfo]] = {}

    for (lhs_id, rhs_id), connection in assembly.model.connections.items():
        # Add lhs anchor to base piece
        if lhs_id not in piece_anchors:
            piece_anchors[lhs_id] = []

        lhs_anchor = connection.lhs
        offset_type = type(lhs_anchor.offset).__name__
        piece_anchors[lhs_id].append(
            AnchorInfo(
                contact_face=lhs_anchor.contact_face,
                edge_shared_face=lhs_anchor.edge_shared_face,
                offset_type=offset_type,
                offset_value=lhs_anchor.offset.value,
            )
        )

        # Add rhs anchor to target piece
        if rhs_id not in piece_anchors:
            piece_anchors[rhs_id] = []

        rhs_anchor = connection.rhs
        offset_type = type(rhs_anchor.offset).__name__
        piece_anchors[rhs_id].append(
            AnchorInfo(
                contact_face=rhs_anchor.contact_face,
                edge_shared_face=rhs_anchor.edge_shared_face,
                offset_type=offset_type,
                offset_value=rhs_anchor.offset.value,
            )
        )

    # Extract pilot hole information
    piece_pilot_holes: Dict[str, list[PilotHoleInfo]] = {}
    for piece_id, holes in assembly.pilot_holes.items():
        box = assembly.boxes[piece_id]
        piece_pilot_holes[piece_id] = [
            _point3d_to_pilot_hole_info(point, hole, box) for point, hole in holes
        ]

    # Extract piece resources from model
    pieces_list = []
    pieces_by_type: Dict[PieceType, int] = {}
    total_length_by_type: Dict[PieceType, float] = {}
    total_volume = 0.0

    for piece in assembly.model.pieces.values():
        # Get the 3D shape with actual dimensions
        shape = get_shape(piece)

        # Calculate volume
        volume = shape.width * shape.height * shape.length

        # Create resource entry with anchors and pilot holes
        resource = PieceResource(
            id=piece.id,
            type=piece.type,
            length=piece.length,
            width=shape.width,
            height=shape.height,
            volume=volume,
            anchors=piece_anchors.get(piece.id, []),
            pilot_holes=piece_pilot_holes.get(piece.id, []),
        )
        pieces_list.append(resource)

        # Update aggregates
        pieces_by_type[piece.type] = pieces_by_type.get(piece.type, 0) + 1
        total_length_by_type[piece.type] = (
            total_length_by_type.get(piece.type, 0.0) + piece.length
        )
        total_volume += volume

    return ResourceSummary(
        pieces=pieces_list,
        total_pieces=len(pieces_list),
        pieces_by_type=pieces_by_type,
        total_length_by_type=total_length_by_type,
        total_volume=total_volume,
    )
