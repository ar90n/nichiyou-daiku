"""Lumber data models for wood pieces.

This module provides the core data structures for representing lumber pieces
in a woodworking project. Position and rotation are determined by graph traversal,
not stored in the lumber piece itself.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, NewType, Tuple

from .geometry import Shape2D, Shape3D


class LumberType(Enum):
    """Standard lumber dimensions in inches (nominal size)."""

    LUMBER_2X4 = "2x4"

    def shape(self) -> Shape2D:
       return {
            LumberType.LUMBER_2X4: Shape2D(89.0, 38.0),
        }[self]


class LumberFace(Enum):
    """Six faces of a rectangular lumber piece."""

    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    FRONT = "front"
    BACK = "back"

class LumberAxis(Enum):
    """Axes for lumber piece orientation."""
    WIDTH = "width"    # Left to right
    HEIGHT = "height"  # Back to front
    LENGTH = "length"  # Bottom to top

class LumberPolarity(Enum):
    """Polarity of lumber piece faces."""
    FORWARD = "forward"  # Positive direction
    BACKWARD = "backward"  # Negative direction

@dataclass(frozen=True)
class LumberDirection:
    """Direction of a lumber piece along an axis.

    Attributes:
        axis: The axis along which the direction is defined
        polarity: The polarity of the direction (forward/backward)
    """
    axis: LumberAxis
    polarity: LumberPolarity

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

def rotate_face_90(direction: LumberDirection, face: LumberFace) -> LumberFace:
    """Rotate a lumber face 90 degrees in the specified direction.

    Args:
        direction: The direction to rotate the face
        face: The original face to rotate
    Returns:
        The new face after rotation
    """
    rotation_map: Dict[Tuple[LumberAxis, LumberPolarity], Dict[LumberFace, LumberFace]] = {
        (LumberAxis.WIDTH, LumberPolarity.FORWARD): {
            LumberFace.TOP: LumberFace.BACK,
            LumberFace.BACK: LumberFace.BOTTOM,
            LumberFace.BOTTOM: LumberFace.FRONT,
            LumberFace.FRONT: LumberFace.TOP,
        },
        (LumberAxis.WIDTH, LumberPolarity.BACKWARD): {
            LumberFace.TOP: LumberFace.FRONT,
            LumberFace.BACK: LumberFace.TOP,
            LumberFace.BOTTOM: LumberFace.BACK,
            LumberFace.FRONT: LumberFace.BOTTOM,
        },
        (LumberAxis.HEIGHT, LumberPolarity.FORWARD): {
            LumberFace.TOP: LumberFace.RIGHT,
            LumberFace.RIGHT: LumberFace.BOTTOM,
            LumberFace.BOTTOM: LumberFace.LEFT,
            LumberFace.LEFT: LumberFace.TOP,
        },
        (LumberAxis.HEIGHT, LumberPolarity.BACKWARD): {
            LumberFace.TOP: LumberFace.LEFT,
            LumberFace.RIGHT: LumberFace.TOP,
            LumberFace.BOTTOM: LumberFace.RIGHT,
            LumberFace.LEFT: LumberFace.BOTTOM,
        },
        (LumberAxis.LENGTH, LumberPolarity.FORWARD): {
            LumberFace.RIGHT: LumberFace.BACK,
            LumberFace.BACK: LumberFace.LEFT,
            LumberFace.LEFT: LumberFace.FRONT,
            LumberFace.FRONT: LumberFace.RIGHT,
        },
        (LumberAxis.LENGTH, LumberPolarity.BACKWARD): {
            LumberFace.RIGHT: LumberFace.FRONT,
            LumberFace.BACK: LumberFace.RIGHT,
            LumberFace.LEFT: LumberFace.BACK,
            LumberFace.FRONT: LumberFace.LEFT,
        },
    }

    return rotation_map[(direction.axis, direction.polarity)][face]

def rotate_face_180(direction: LumberDirection, face: LumberFace) -> LumberFace:
    """Rotate a lumber face 180 degrees in the specified direction.

    Args:
        direction: The direction to rotate the face
        face: The original face to rotate
    Returns:
        The new face after rotation
    """
    return rotate_face_90(direction, rotate_face_90(direction, face))

def rotate_face_270(direction: LumberDirection, face: LumberFace) -> LumberFace:
    """Rotate a lumber face 270 degrees in the specified direction.

    Args:
        direction: The direction to rotate the face
        face: The original face to rotate
    Returns:
        The new face after rotation
    """
    return rotate_face_90(direction, rotate_face_180(direction, face))

def calc_angle(direction: LumberDirection, src: LumberFace, dst: LumberFace) -> float:
    """Calculate the angle between two faces in a given direction.

    Args:
        direction: The direction of rotation
        src: The source face
        dst: The destination face
    Returns:
        The angle in degrees between the two faces
    """
    ret = 0.0
    while src != dst:
        print(src,dst)
        src = rotate_face_90(direction, src)
        ret += 90.0
    return ret

def get_shape(piece: LumberPiece) -> Shape3D:
    base_shape = piece.lumber_type.shape()

    return Shape3D(width=base_shape.width, height=base_shape.height, length=piece.length)
