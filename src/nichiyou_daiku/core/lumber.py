"""Lumber data models for wood pieces.

This module provides the core data structures for representing lumber pieces
in a woodworking project. Position and rotation are determined by graph traversal,
not stored in the lumber piece itself.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, NewType, Tuple

# Type aliases for clarity
Millimeters = NewType("Millimeters", float)
Position3D = Tuple[float, float, float]
Rotation3D = Tuple[float, float, float]
Dimensions3D = Tuple[float, float, float]


class LumberType(Enum):
    """Standard lumber dimensions in inches (nominal size)."""

    LUMBER_1X4 = "1x4"
    LUMBER_1X8 = "1x8"
    LUMBER_1X16 = "1x16"
    LUMBER_2X4 = "2x4"
    LUMBER_2X8 = "2x8"
    LUMBER_2X16 = "2x16"


class Face(Enum):
    """Six faces of a rectangular lumber piece."""

    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    FRONT = "front"
    BACK = "back"


@dataclass(frozen=True)
class LumberSpec:
    """Specification for lumber cross-section dimensions in millimeters."""

    width: float
    height: float


@dataclass(frozen=True)
class LumberPiece:
    """A single piece of lumber.

    Position and rotation are not stored here but calculated
    through graph traversal from a specified origin point.

    Attributes:
        id: Unique identifier for this lumber piece
        lumber_type: Type of lumber (e.g., 2x4, 1x8)
        length: Length of the lumber piece in millimeters
    """

    id: str
    lumber_type: LumberType
    length: float

    def get_dimensions(self) -> Dimensions3D:
        """Get the dimensions (width, height, length) of the lumber piece.

        Returns:
            Tuple of (width, height, length) in millimeters

        >>> piece = LumberPiece("test", LumberType.LUMBER_2X4, 1000.0)
        >>> piece.get_dimensions()
        (38.0, 89.0, 1000.0)
        """
        spec = _get_lumber_spec(self.lumber_type)
        return (spec.width, spec.height, self.length)

    def get_face_center_local(self, face: Face) -> Position3D:
        """Get the center of the specified face in local coordinates.

        Local coordinates assume the piece center is at origin (0, 0, 0)
        with no rotation applied.

        Args:
            face: The face to get the center of

        Returns:
            3D position (x, y, z) of the face center in local coordinates

        >>> piece = LumberPiece("test", LumberType.LUMBER_2X4, 1000.0)
        >>> piece.get_face_center_local(Face.TOP)
        (0.0, 0.0, 44.5)
        >>> piece.get_face_center_local(Face.FRONT)
        (500.0, 0.0, 0.0)
        """
        width, height, length = self.get_dimensions()
        return _get_face_offset(face, width, height, length)


# Module-level functions following functional programming approach


def _get_lumber_spec(lumber_type: LumberType) -> LumberSpec:
    """Get the standard specification for a lumber type.

    Actual dimensions in millimeters for nominal inch sizes.

    Args:
        lumber_type: Type of lumber

    Returns:
        LumberSpec with standard dimensions in millimeters
    """
    # Actual dimensions for dried lumber (mm)
    # 1x nominal: 19mm thick, 2x nominal: 38mm thick
    specs: Dict[LumberType, LumberSpec] = {
        LumberType.LUMBER_1X4: LumberSpec(19.0, 89.0),  # 3/4" x 3.5"
        LumberType.LUMBER_1X8: LumberSpec(19.0, 184.0),  # 3/4" x 7.25"
        LumberType.LUMBER_1X16: LumberSpec(19.0, 387.0),  # 3/4" x 15.25"
        LumberType.LUMBER_2X4: LumberSpec(38.0, 89.0),  # 1.5" x 3.5"
        LumberType.LUMBER_2X8: LumberSpec(38.0, 184.0),  # 1.5" x 7.25"
        LumberType.LUMBER_2X16: LumberSpec(38.0, 387.0),  # 1.5" x 15.25"
    }
    return specs[lumber_type]


def _get_face_offset(
    face: Face, width: float, height: float, length: float
) -> Position3D:
    """Calculate the offset from piece center to face center.

    Args:
        face: The face to calculate offset for
        width: Width of the lumber piece
        height: Height of the lumber piece
        length: Length of the lumber piece

    Returns:
        3D offset (dx, dy, dz) from piece center to face center
    """
    face_offsets: Dict[Face, Position3D] = {
        Face.TOP: (0.0, 0.0, height / 2),
        Face.BOTTOM: (0.0, 0.0, -height / 2),
        Face.LEFT: (0.0, -width / 2, 0.0),
        Face.RIGHT: (0.0, width / 2, 0.0),
        Face.FRONT: (length / 2, 0.0, 0.0),
        Face.BACK: (-length / 2, 0.0, 0.0),
    }
    return face_offsets[face]
