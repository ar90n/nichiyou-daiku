"""Lumber data models for wood pieces.

This module provides the core data structures for representing lumber pieces
in a woodworking project, including their dimensions, positions, and orientations.
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
    """Standard lumber dimensions."""

    LUMBER_1X = "1x"
    LUMBER_2X = "2x"


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
    """A single piece of lumber with position and orientation.

    Attributes:
        id: Unique identifier for this lumber piece
        lumber_type: Type of lumber (1x or 2x)
        length: Length of the lumber piece in millimeters
        position: 3D position (x, y, z) in millimeters
        rotation: 3D rotation (rx, ry, rz) in degrees
    """

    id: str
    lumber_type: LumberType
    length: float
    position: Position3D = (0.0, 0.0, 0.0)
    rotation: Rotation3D = (0.0, 0.0, 0.0)

    def get_dimensions(self) -> Dimensions3D:
        """Get the dimensions (width, height, length) of the lumber piece.

        Returns:
            Tuple of (width, height, length) in millimeters

        >>> piece = LumberPiece("test", LumberType.LUMBER_2X, 1000.0)
        >>> piece.get_dimensions()
        (38.0, 89.0, 1000.0)
        """
        spec = _get_lumber_spec(self.lumber_type)
        return (spec.width, spec.height, self.length)

    def get_face_center_3d(self, face: Face) -> Position3D:
        """Get the 3D coordinates of the center of the specified face.

        Args:
            face: The face to get the center of

        Returns:
            3D position (x, y, z) of the face center in millimeters

        >>> piece = LumberPiece("test", LumberType.LUMBER_2X, 1000.0)
        >>> piece.get_face_center_3d(Face.TOP)
        (0.0, 0.0, 44.5)
        >>> piece.get_face_center_3d(Face.FRONT)
        (500.0, 0.0, 0.0)
        """
        width, height, length = self.get_dimensions()
        x, y, z = self.position

        # Calculate face center offset from piece center
        offset = _get_face_offset(face, width, height, length)
        return (x + offset[0], y + offset[1], z + offset[2])


# Module-level functions following functional programming approach


def _get_lumber_spec(lumber_type: LumberType) -> LumberSpec:
    """Get the standard specification for a lumber type.

    Args:
        lumber_type: Type of lumber

    Returns:
        LumberSpec with standard dimensions in millimeters
    """
    specs: Dict[LumberType, LumberSpec] = {
        LumberType.LUMBER_1X: LumberSpec(19.0, 38.0),
        LumberType.LUMBER_2X: LumberSpec(38.0, 89.0),
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
