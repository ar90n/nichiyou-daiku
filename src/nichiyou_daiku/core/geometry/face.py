"""Face types and operations for lumber pieces.

This module provides the Face type and related operations for working with
the six faces of a rectangular piece of lumber.
"""

from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from .edge import Edge

# Need to import Edge for runtime use as well
try:
    from .edge import Edge
except ImportError:
    # For doctests, use a simple replacement
    class Edge:
        def __init__(self, lhs, rhs):
            self.lhs = lhs
            self.rhs = rhs

# Define Face as a Literal type
Face = Literal["top", "bottom", "left", "right", "front", "back"]
"""The six faces of a rectangular piece of lumber.

Represents the six faces of a rectangular piece of lumber, used for
specifying connections and orientations.

- top/bottom: faces perpendicular to X axis
- left/right: faces perpendicular to Y axis  
- front/back: faces perpendicular to Z axis

Examples:
    >>> face: Face = "top"
    >>> face
    'top'
    >>> faces: list[Face] = ["top", "bottom", "left", "right", "front", "back"]
    >>> "top" in faces
    True
"""


def opposite(face: Face) -> Face:
    """Get the opposite face.

    Returns the face that is opposite to the given face.

    Args:
        face: The face to find the opposite of

    Returns:
        Opposite face

    Examples:
        >>> opposite("top")
        'bottom'
        >>> opposite("left")
        'right'
        >>> opposite("front")
        'back'
    """
    match face:
        case "top":
            return "bottom"
        case "bottom":
            return "top"
        case "left":
            return "right"
        case "right":
            return "left"
        case "front":
            return "back"
        case "back":
            return "front"


def cross(lhs: Face, rhs: Face) -> Face:
    """Calculate the cross product of two faces.

    Determines the face that results from the cross product of two
    given faces, following the right-hand rule.

    Args:
        lhs: First face
        rhs: Second face

    Returns:
        Resulting face from the cross product

    Examples:
        >>> cross("top", "front")
        'left'
        >>> cross("left", "bottom")
        'back'
    """
    # Normalize the faces to canonical orientation
    if lhs in ("bottom", "left", "back"):
        lhs, rhs = rhs, opposite(lhs)
    if lhs in ("bottom", "left", "back"):
        lhs, rhs = rhs, opposite(lhs)
    if rhs in ("bottom", "left", "back"):
        lhs, rhs = opposite(rhs), lhs

    match (lhs, rhs):
        case ("top", "front"):
            return "left"
        case ("front", "top"):
            return "right"
        case ("right", "top"):
            return "back"
        case ("top", "right"):
            return "front"
        case ("front", "right"):
            return "bottom"
        case ("right", "front"):
            return "top"
        case _:
            raise ValueError(f"Invalid face combination: {lhs}, {rhs}")


def has_bottom_to_top_axis(face: Face) -> bool:
    """Check if a face is on the top-to-bottom axis.

    Determines if the given face is either "top" or "bottom".

    Args:
        face: The face to check

    Returns:
        True if the face is on the top-to-bottom axis, False otherwise

    Examples:
        >>> has_bottom_to_top_axis("top")
        True
        >>> has_bottom_to_top_axis("bottom")
        True
        >>> has_bottom_to_top_axis("left")
        False
    """
    return face in ("top", "bottom")


def has_left_to_right_axis(face: Face) -> bool:
    """Check if a face is on the left-to-right axis.

    Determines if the given face is either "left" or "right".

    Args:
        face: The face to check

    Returns:
        True if the face is on the left-to-right axis, False otherwise

    Examples:
        >>> has_left_to_right_axis("left")
        True
        >>> has_left_to_right_axis("right")
        True
        >>> has_left_to_right_axis("front")
        False
    """
    return face in ("left", "right")


def has_back_to_front_axis(face: Face) -> bool:
    """Check if a face is on the front-to-back axis.

    Determines if the given face is either "front" or "back".

    Args:
        face: The face to check

    Returns:
        True if the face is on the front-to-back axis, False otherwise

    Examples:
        >>> has_back_to_front_axis("front")
        True
        >>> has_back_to_front_axis("back")
        True
        >>> has_back_to_front_axis("top")
        False
    """
    return face in ("front", "back")


def has_same_axis(lhs: Face, rhs: Face) -> bool:
    """Check if two faces are on the same axis.

    Determines if two faces are aligned along the same axis (X, Y, or Z).

    Args:
        lhs: First face
        rhs: Second face

    Returns:
        True if the faces are on the same axis, False otherwise

    Examples:
        >>> has_same_axis("top", "bottom")
        True
        >>> has_same_axis("left", "right")
        True
        >>> has_same_axis("front", "back")
        True
        >>> has_same_axis("top", "left")
        False
    """
    return (
        (has_bottom_to_top_axis(lhs) and has_bottom_to_top_axis(rhs))
        or (has_left_to_right_axis(lhs) and has_left_to_right_axis(rhs))
        or (has_back_to_front_axis(lhs) and has_back_to_front_axis(rhs))
    )


def is_adjacent(lhs: Face, rhs: Face) -> bool:
    """Check if two faces are adjacent.

    Determines if two faces are adjacent to each other.

    Args:
        lhs: First face
        rhs: Second face

    Returns:
        True if the faces are adjacent, False otherwise

    Examples:
        >>> is_adjacent("top", "front")
        True
        >>> is_adjacent("left", "back")
        True
        >>> is_adjacent("top", "bottom")
        False
    """
    return lhs != rhs and not has_same_axis(lhs, rhs)
