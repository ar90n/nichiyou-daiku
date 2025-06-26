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


def orientation_from_target_to_base_coords(
    target_face: Face, 
    target_edge: "Edge",
    base_contact_face: Face, 
    target_contact_face: Face
) -> tuple[Face, "Edge"]:
    """Transform target orientation to base coordinate system.
    
    When two pieces connect, this function transforms the target piece's
    orientation (face and edge) into the base piece's coordinate system.
    This ensures proper alignment when the pieces are joined.
    
    The transformation works by:
    1. The target contact face becomes opposite to the base contact face
    2. The edge is transformed using cross product with "top" to maintain
       consistent orientation across the connection
    
    Args:
        target_face: Face on the target piece (should be the contact face)
        target_edge: Edge on the target piece defining orientation
        base_contact_face: Face on the base piece where connection occurs
        target_contact_face: Face on the target piece where connection occurs
        
    Returns:
        Tuple of (transformed_face, transformed_edge) in base coordinates
        
    Raises:
        ValueError: If target_face is not part of target_edge
        
    Examples:
        >>> edge = Edge(lhs="bottom", rhs="back")
        >>> face, new_edge = orientation_from_target_to_base_coords(
        ...     target_face="bottom",
        ...     target_edge=edge,
        ...     base_contact_face="top", 
        ...     target_contact_face="bottom"
        ... )
        >>> face
        'bottom'
    """
    # Validate that target_face is part of target_edge
    if target_face not in (target_edge.lhs, target_edge.rhs):
        raise ValueError(f"Target face {target_face} is not part of the target edge {target_edge}")
    
    # For face-to-face contact, the target face in base coords is opposite to base contact
    target_face_in_base_coords = opposite(base_contact_face)
    
    # Special case: when connecting top/bottom faces, preserve the edge faces directly
    if base_contact_face in ("top", "bottom") and target_contact_face in ("top", "bottom"):
        # Find the non-contact face in the edge
        target_pair_face = target_edge.lhs if target_face == target_edge.rhs else target_edge.rhs
        target_pair_face_in_base_coords = target_pair_face
    else:
        # For other connections, use a reference face that's not on the same axis
        # This avoids the cross(top, top) issue
        if target_face_in_base_coords in ("top", "bottom"):
            reference = "front"
        elif target_face_in_base_coords in ("left", "right"):
            reference = "top"
        else:  # front/back
            reference = "top"
        
        if target_face == target_edge.lhs:
            # Target face is on left side - compute right side using cross product
            target_pair_face_in_base_coords = cross(reference, target_face_in_base_coords)
        else:
            # Target face is on right side - compute left side using cross product
            target_pair_face_in_base_coords = cross(target_face_in_base_coords, reference)
    
    # Reconstruct the edge in base coordinates preserving the relative positions
    if target_face == target_edge.lhs:
        target_edge_in_base_coords = Edge(lhs=target_face_in_base_coords, rhs=target_pair_face_in_base_coords)
    else:
        target_edge_in_base_coords = Edge(lhs=target_pair_face_in_base_coords, rhs=target_face_in_base_coords)
    
    return target_face_in_base_coords, target_edge_in_base_coords
