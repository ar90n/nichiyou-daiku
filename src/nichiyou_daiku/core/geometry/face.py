"""Face types and operations for lumber pieces.

This module provides the Face type and related operations for working with
the six faces of a rectangular piece of lumber.
"""

from typing import Literal

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


def face_from_target_to_base_coords(
    target_face_dir: Face, base_contact_face: Face, target_contact_face: Face
) -> Face:
    """Convert a face direction from target piece coordinates to base piece coordinates.

    When base_contact_face touches target_contact_face, this function converts
    a face direction from the target piece's coordinate system to the base piece's
    coordinate system.

    Args:
        target_face_dir: Face direction in target piece coordinates
        base_contact_face: Face of the base piece that makes contact
        target_contact_face: Face of the target piece that makes contact

    Returns:
        The face direction converted to base piece coordinates

    Examples:
        >>> face_from_target_to_base_coords("front", "front", "top")
        'top'
        >>> face_from_target_to_base_coords("right", "top", "bottom")
        'left'
        >>> face_from_target_to_base_coords("top", "left", "right")
        'top'
    """
    # Define coordinate transformation for each base-target contact combination
    match (base_contact_face, target_contact_face):
        # Base TOP contacts Target faces
        case ("top", "top"):
            transform = {
                "top": "bottom",
                "bottom": "top",
                "left": "left",
                "right": "right",
                "front": "back",
                "back": "front",
            }
        case ("top", "bottom"):
            transform = {
                "top": "top",
                "bottom": "bottom",
                "left": "right",
                "right": "left",
                "front": "front",
                "back": "back",
            }
        case ("top", "left"):
            transform = {
                "top": "right",
                "bottom": "left",
                "left": "top",
                "right": "bottom",
                "front": "front",
                "back": "back",
            }
        case ("top", "right"):
            transform = {
                "top": "left",
                "bottom": "right",
                "left": "bottom",
                "right": "top",
                "front": "back",
                "back": "front",
            }
        case ("top", "front"):
            transform = {
                "top": "back",
                "bottom": "front",
                "left": "left",
                "right": "right",
                "front": "top",
                "back": "bottom",
            }
        case ("top", "back"):
            transform = {
                "top": "front",
                "bottom": "back",
                "left": "right",
                "right": "left",
                "front": "bottom",
                "back": "top",
            }

        # Base BOTTOM contacts Target faces
        case ("bottom", "top"):
            transform = {
                "top": "bottom",
                "bottom": "top",
                "left": "right",
                "right": "left",
                "front": "front",
                "back": "back",
            }
        case ("bottom", "bottom"):
            transform = {
                "top": "top",
                "bottom": "bottom",
                "left": "left",
                "right": "right",
                "front": "back",
                "back": "front",
            }
        case ("bottom", "left"):
            transform = {
                "top": "left",
                "bottom": "right",
                "left": "bottom",
                "right": "top",
                "front": "back",
                "back": "front",
            }
        case ("bottom", "right"):
            transform = {
                "top": "right",
                "bottom": "left",
                "left": "top",
                "right": "bottom",
                "front": "front",
                "back": "back",
            }
        case ("bottom", "front"):
            transform = {
                "top": "front",
                "bottom": "back",
                "left": "right",
                "right": "left",
                "front": "bottom",
                "back": "top",
            }
        case ("bottom", "back"):
            transform = {
                "top": "back",
                "bottom": "front",
                "left": "left",
                "right": "right",
                "front": "top",
                "back": "bottom",
            }

        # Base LEFT contacts Target faces
        case ("left", "top"):
            transform = {
                "top": "left",
                "bottom": "right",
                "left": "bottom",
                "right": "top",
                "front": "back",
                "back": "front",
            }
        case ("left", "bottom"):
            transform = {
                "top": "right",
                "bottom": "left",
                "left": "top",
                "right": "bottom",
                "front": "front",
                "back": "back",
            }
        case ("left", "left"):
            transform = {
                "top": "bottom",
                "bottom": "top",
                "left": "left",
                "right": "right",
                "front": "front",
                "back": "back",
            }
        case ("left", "right"):
            transform = {
                "top": "top",
                "bottom": "bottom",
                "left": "right",
                "right": "left",
                "front": "back",
                "back": "front",
            }
        case ("left", "front"):
            transform = {
                "top": "front",
                "bottom": "back",
                "left": "right",
                "right": "left",
                "front": "left",
                "back": "right",
            }
        case ("left", "back"):
            transform = {
                "top": "back",
                "bottom": "front",
                "left": "left",
                "right": "right",
                "front": "right",
                "back": "left",
            }

        # Base RIGHT contacts Target faces
        case ("right", "top"):
            transform = {
                "top": "right",
                "bottom": "left",
                "left": "top",
                "right": "bottom",
                "front": "front",
                "back": "back",
            }
        case ("right", "bottom"):
            transform = {
                "top": "left",
                "bottom": "right",
                "left": "bottom",
                "right": "top",
                "front": "back",
                "back": "front",
            }
        case ("right", "left"):
            transform = {
                "top": "top",
                "bottom": "bottom",
                "left": "right",
                "right": "left",
                "front": "back",
                "back": "front",
            }
        case ("right", "right"):
            transform = {
                "top": "bottom",
                "bottom": "top",
                "left": "left",
                "right": "right",
                "front": "front",
                "back": "back",
            }
        case ("right", "front"):
            transform = {
                "top": "back",
                "bottom": "front",
                "left": "left",
                "right": "right",
                "front": "right",
                "back": "left",
            }
        case ("right", "back"):
            transform = {
                "top": "front",
                "bottom": "back",
                "left": "right",
                "right": "left",
                "front": "left",
                "back": "right",
            }

        # Base FRONT contacts Target faces
        case ("front", "top"):
            transform = {
                "top": "back",
                "bottom": "front",
                "left": "left",
                "right": "right",
                "front": "top",
                "back": "bottom",
            }
        case ("front", "bottom"):
            transform = {
                "top": "front",
                "bottom": "back",
                "left": "right",
                "right": "left",
                "front": "bottom",
                "back": "top",
            }
        case ("front", "left"):
            transform = {
                "top": "top",
                "bottom": "bottom",
                "left": "back",
                "right": "front",
                "front": "left",
                "back": "right",
            }
        case ("front", "right"):
            transform = {
                "top": "bottom",
                "bottom": "top",
                "left": "front",
                "right": "back",
                "front": "right",
                "back": "left",
            }
        case ("front", "front"):
            transform = {
                "top": "top",
                "bottom": "bottom",
                "left": "right",
                "right": "left",
                "front": "front",
                "back": "back",
            }
        case ("front", "back"):
            transform = {
                "top": "bottom",
                "bottom": "top",
                "left": "left",
                "right": "right",
                "front": "back",
                "back": "front",
            }

        # Base BACK contacts Target faces
        case ("back", "top"):
            transform = {
                "top": "front",
                "bottom": "back",
                "left": "right",
                "right": "left",
                "front": "bottom",
                "back": "top",
            }
        case ("back", "bottom"):
            transform = {
                "top": "back",
                "bottom": "front",
                "left": "left",
                "right": "right",
                "front": "top",
                "back": "bottom",
            }
        case ("back", "left"):
            transform = {
                "top": "bottom",
                "bottom": "top",
                "left": "front",
                "right": "back",
                "front": "right",
                "back": "left",
            }
        case ("back", "right"):
            transform = {
                "top": "top",
                "bottom": "bottom",
                "left": "back",
                "right": "front",
                "front": "left",
                "back": "right",
            }
        case ("back", "front"):
            transform = {
                "top": "bottom",
                "bottom": "top",
                "left": "left",
                "right": "right",
                "front": "back",
                "back": "front",
            }
        case ("back", "back"):
            transform = {
                "top": "top",
                "bottom": "bottom",
                "left": "right",
                "right": "left",
                "front": "front",
                "back": "back",
            }

        case _:
            raise ValueError(
                f"Invalid face combination: base={base_contact_face}, target={target_contact_face}"
            )

    return transform[target_face_dir]
