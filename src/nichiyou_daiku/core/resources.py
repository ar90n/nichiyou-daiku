"""Resource extraction from woodworking models.

This module provides functionality to extract and summarize the resources
(lumber pieces) required for a woodworking project from a Model.
"""

from typing import Dict

from pydantic import BaseModel, ConfigDict

from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.piece import PieceType, get_shape


class PieceResource(BaseModel):
    """Resource information for a single piece of lumber.

    Attributes:
        id: Unique identifier for the piece
        type: Type of lumber (e.g., PT_2x4, PT_1x4)
        length: Length in millimeters
        width: Actual width in millimeters
        height: Actual height in millimeters
        volume: Calculated volume in cubic millimeters

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
    """

    id: str
    type: PieceType
    length: float  # mm
    width: float  # mm
    height: float  # mm
    volume: float  # mm³


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


def extract_resources(model: Model) -> ResourceSummary:
    """Extract all required resources from a Model.

    Analyzes a woodworking model and produces a comprehensive summary
    of all lumber pieces required, including their dimensions and
    aggregated statistics.

    Args:
        model: The woodworking model to analyze

    Returns:
        ResourceSummary containing detailed piece information and statistics

    Examples:
        >>> from nichiyou_daiku.core.model import Model
        >>> from nichiyou_daiku.core.piece import Piece, PieceType
        >>> pieces = [
        ...     Piece.of(PieceType.PT_2x4, 1000.0, "p1"),
        ...     Piece.of(PieceType.PT_2x4, 800.0, "p2"),
        ...     Piece.of(PieceType.PT_1x4, 600.0, "p3")
        ... ]
        >>> model = Model.of(pieces=pieces, connections=[])
        >>> resources = extract_resources(model)
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
    pieces_list = []
    pieces_by_type: Dict[PieceType, int] = {}
    total_length_by_type: Dict[PieceType, float] = {}
    total_volume = 0.0

    for piece in model.pieces.values():
        # Get the 3D shape with actual dimensions
        shape = get_shape(piece)

        # Calculate volume
        volume = shape.width * shape.height * shape.length

        # Create resource entry
        resource = PieceResource(
            id=piece.id,
            type=piece.type,
            length=piece.length,
            width=shape.width,
            height=shape.height,
            volume=volume,
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
