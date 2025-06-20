"""Corner types for lumber pieces.

This module provides types for representing corners formed by the intersection
of three faces on a lumber piece.
"""

from typing import Literal
from pydantic import BaseModel

from .face import Face, cross, has_back_to_front_axis, has_left_to_right_axis, has_bottom_to_top_axis
from .edge import Edge


class Corner(BaseModel, frozen=True):
    """Corner formed by three faces.
    
    Represents a corner formed by the intersection of three faces.

    Attributes:
        face_x: Face in the X direction (must be top or bottom)
        face_y: Face in the Y direction (must be left or right)
        face_z: Face in the Z direction (must be front or back)

    Examples:
        >>> corner = Corner(face_top_bottom="top", face_right_left="left", face_front_back="front")
        >>> corner.face_top_bottom
        'top'
        >>> corner.face_right_left
        'left'
        >>> corner.face_front_back
        'front'
    """     

    face_top_bottom: Literal["top", "bottom"]
    face_right_left: Literal["left", "right"]
    face_front_back: Literal["front", "back"]

    @classmethod
    def of(cls, face: Face, edge: Edge) -> "Corner":
        """Create a corner from a face and an edge.

        Given a face and an edge, this method determines the third face
        that completes the corner.

        Args:
            face: One of the three faces
            edge: Edge formed by two of the faces

        Returns:
            Corner object with the three faces

        Examples:
            >>> edge = Edge(lhs="top", rhs="front")
            >>> corner = Corner.of("left", edge)
            >>> corner.face_top_bottom
            'top'
            >>> corner.face_right_left
            'left'
            >>> corner.face_front_back
            'front'
        """
        # Determine which face goes in which position
        faces = {edge.lhs, edge.rhs, face}
        
        # Find face_x (top or bottom)
        face_top_bottom = next((f for f in faces if has_bottom_to_top_axis(f)), None)
        if not face_top_bottom:
            raise ValueError("Corner must include either top or bottom face")
            
        # Find face_y (left or right)
        face_right_left = next((f for f in faces if has_left_to_right_axis(f)), None)
        if not face_right_left:
            raise ValueError("Corner must include either left or right face")
            
        # Find face_z (front or back)
        face_front_back = next((f for f in faces if has_back_to_front_axis(f)), None)
        if not face_front_back:
            raise ValueError("Corner must include either front or back face")
            
        return cls(face_top_bottom=face_top_bottom, face_right_left=face_right_left, face_front_back=face_front_back)
    
    @classmethod
    def origin_of(cls, edge: Edge) -> "Corner":
        """Create a corner from an edge.

        Given an edge, this method creates a corner with the edge's faces
        and a third face that is perpendicular to the edge.

        Args:
            edge: Edge formed by two faces

        Returns:
            Corner object with the three faces

        Examples:
            >>> edge = Edge(lhs="top", rhs="front")
            >>> corner = Corner.origin_of(edge)
            >>> corner.face_top_bottom
            'top'
            >>> corner.face_right_left
            'left'
            >>> corner.face_front_back
            'front'
        """
        third_face = cross(edge.rhs, edge.lhs)
        return cls.of(third_face, edge)