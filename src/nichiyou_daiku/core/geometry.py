"""Geometry utilities for face coordinate systems.

This module provides utilities for working with face coordinate systems
as defined in the refine.md document.
"""

from typing import Tuple
from nichiyou_daiku.core.lumber import Face

# Type aliases
Point2D = Tuple[float, float]  # (u, v) coordinates on a face
Vector2D = Tuple[float, float]  # 2D vector on a face


def get_face_uv_axes(face: Face) -> Tuple[str, str]:
    """Get the U and V axis definitions for a face.
    
    According to refine.md:
    - TOP, BOTTOM: u-axis: RIGHT -> LEFT, v-axis: BACK -> FRONT
    - FRONT, BACK: u-axis: BOTTOM -> TOP, v-axis: RIGHT -> LEFT  
    - LEFT, RIGHT: u-axis: BOTTOM -> TOP, v-axis: BACK -> FRONT
    
    Args:
        face: The face to get axes for
        
    Returns:
        Tuple of (u_axis_description, v_axis_description)
    """
    axes_map = {
        Face.TOP: ("RIGHT -> LEFT", "BACK -> FRONT"),
        Face.BOTTOM: ("RIGHT -> LEFT", "BACK -> FRONT"),
        Face.FRONT: ("BOTTOM -> TOP", "RIGHT -> LEFT"),
        Face.BACK: ("BOTTOM -> TOP", "RIGHT -> LEFT"),
        Face.LEFT: ("BOTTOM -> TOP", "BACK -> FRONT"),
        Face.RIGHT: ("BOTTOM -> TOP", "BACK -> FRONT"),
    }
    return axes_map[face]


def get_face_dimensions(face: Face, lumber_width: float, lumber_height: float, lumber_length: float) -> Tuple[float, float]:
    """Get the dimensions of a face in the UV coordinate system.
    
    According to refine.md for 2x4:
    - TOP, BOTTOM: 38.0 x 89.0
    - FRONT, BACK: 89.0 x length
    - LEFT, RIGHT: 38.0 x length
    
    Args:
        face: The face to get dimensions for
        lumber_width: Width of the lumber (38.0 for 2x4)
        lumber_height: Height of the lumber (89.0 for 2x4)
        lumber_length: Length of the lumber piece
        
    Returns:
        Tuple of (u_dimension, v_dimension) in mm
    """
    dimensions_map = {
        Face.TOP: (lumber_width, lumber_height),
        Face.BOTTOM: (lumber_width, lumber_height),
        Face.FRONT: (lumber_height, lumber_length),
        Face.BACK: (lumber_height, lumber_length),
        Face.LEFT: (lumber_width, lumber_length),
        Face.RIGHT: (lumber_width, lumber_length),
    }
    return dimensions_map[face]


def offset_to_uv(face: Face, offset: float) -> Point2D:
    """Convert a joint offset to UV coordinates on a face.
    
    The offset is along the U-axis from the face center.
    
    Args:
        face: The face
        offset: Offset from center along U-axis in mm
        
    Returns:
        (u, v) coordinates where (0, 0) is the face center
    """
    return (offset, 0.0)


def validate_offset_on_face(
    face: Face, 
    offset: float, 
    lumber_width: float, 
    lumber_height: float, 
    lumber_length: float
) -> bool:
    """Check if an offset is within the bounds of a face.
    
    Args:
        face: The face to check
        offset: Offset from center along U-axis
        lumber_width: Width of the lumber
        lumber_height: Height of the lumber  
        lumber_length: Length of the lumber
        
    Returns:
        True if offset is within face bounds
    """
    u_dim, _ = get_face_dimensions(face, lumber_width, lumber_height, lumber_length)
    max_offset = u_dim / 2.0
    return abs(offset) <= max_offset


