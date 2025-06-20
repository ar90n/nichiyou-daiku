"""3D coordinate types for woodworking.

This module provides types for representing positions and directions in 3D space.
"""
from typing import overload

from pydantic import BaseModel

from .box import Box
from .corner import Corner
from .edge import EdgePoint, Edge
from .face import cross as cross_face, Face


class Point3D(BaseModel, frozen=True):
    """3D point in space.

    Represents a position in 3D space. Unlike dimensions, coordinates
    can be negative or zero.

    Attributes:
        x: X coordinate
        y: Y coordinate
        z: Z coordinate

    Examples:
        >>> origin = Point3D(x=0.0, y=0.0, z=0.0)
        >>> origin.x
        0.0
        >>> # Negative coordinates are allowed
        >>> point = Point3D(x=-10.0, y=20.0, z=-5.0)
        >>> point.x
        -10.0
    """

    x: float
    y: float
    z: float

    @overload
    @classmethod
    def of(cls, box: Box, corner: Corner) -> "Point3D": ...
    @overload
    @classmethod
    def of(cls, box: Box, edge_point: EdgePoint) -> "Point3D": ...
    @classmethod
    def of(
        cls, box: Box, source: Corner | EdgePoint
    ) -> "Point3D":
        """Create a 3D point from a box and a corner or edge point.
        
        Args:
            box: The bounding box
            point: Either a corner or an edge point
            
        Returns:
            Point3D at the specified position
        """
        if isinstance(source, Corner):
            return cls._of_corner(box, source)
        elif isinstance(source, EdgePoint):
            return cls._of_edge_point(box, source)
        else:
            raise TypeError(f"Unsupported point type: {type(source)}")


    @classmethod
    def _of_corner(cls, box: Box, corner: Corner) -> "Point3D":
        """Create a 3D point from a box corner.
        
        Args:
            box: The bounding box
            corner: The corner to get position of
            
        Returns:
            Point3D at the specified corner
        """
        # X-axis is height (top/bottom faces)
        x = 0.0 if corner.face_top_bottom == "bottom" else box.shape.length
        # Y-axis is width (left/right faces)
        y = 0.0 if corner.face_right_left == "left" else box.shape.width
        # Z-axis is length (front/back faces)
        z = 0.0 if corner.face_front_back == "back" else box.shape.height
        return cls(x=x, y=y, z=z)
    
    @classmethod
    def _of_edge_point(cls, box: Box, edge_point: EdgePoint) -> "Point3D":
        """Create a 3D point from an edge point.
        
        Args:
            box: The bounding box
            edge_point: The point along an edge
            
        Returns:
            Point3D at the specified edge point
        """
        origin_corner = Corner.origin_of(edge_point.edge)
        origin = cls._of_corner(box, origin_corner)
        direction = Vector3D.of(edge_point.edge)
        return cls(
            x=origin.x + direction.x * edge_point.value,
            y=origin.y + direction.y * edge_point.value,
            z=origin.z + direction.z * edge_point.value
        )


class Vector3D(BaseModel, frozen=True):
    """3D vector for directions and displacements.

    Represents a direction or displacement in 3D space. Components can be
    any float value including negative and zero.

    Attributes:
        x: X component
        y: Y component
        z: Z component

    Examples:
        >>> # Unit vector in Z direction
        >>> up = Vector3D(x=0.0, y=0.0, z=1.0)
        >>> up.z
        1.0
        >>> # Opposite direction
        >>> down = Vector3D(x=0.0, y=0.0, z=-1.0)
        >>> down.z
        -1.0
        >>> # Diagonal vector
        >>> diag = Vector3D(x=0.707, y=0.707, z=0.0)
        >>> import math
        >>> magnitude = math.sqrt(diag.x**2 + diag.y**2 + diag.z**2)
        >>> abs(magnitude - 1.0) < 0.01  # Approximately unit length
        True
    """

    x: float
    y: float
    z: float

    @classmethod
    def of(cls, edge: Edge) -> 'Vector3D':
        """Create a vector from an edge.

        Given an edge defined by two faces, this method returns a vector
        representing the direction of the edge.

        Args:
            edge: Edge formed by two faces

        Returns:
            Vector3D representing the direction of the edge

        Examples:
            >>> edge = Edge(lhs="top", rhs="front")
            >>> vector = Vector3D.of(edge)
            >>> vector.x, vector.y, vector.z
            (0.0, 1.0, 0.0)
        """
        result_face = cross_face(edge.lhs, edge.rhs)
        return cls.normal_of(result_face)

    @classmethod
    def normal_of(cls, face: Face) -> 'Vector3D':
        """Get the normal vector for a face.

        Returns a unit vector pointing outward from the specified face.

        Args:
            face: The face to get the normal for (e.g., "top", "bottom", "left", "right", "front", "back")

        Returns:
            Vector3D representing the normal direction

        Examples:
            >>> normal = Vector3D.normal_of("top")
            >>> normal.x
            1.0
        """
        match face:
            case "top":
                return cls(x=1.0, y=0.0, z=0.0)
            case "bottom":
                return cls(x=-1.0, y=0.0, z=0.0)
            case "left":
                return cls(x=0.0, y=-1.0, z=0.0)
            case "right":
                return cls(x=0.0, y=1.0, z=0.0)
            case "front":
                return cls(x=0.0, y=0.0, z=1.0)
            case "back":
                return cls(x=0.0, y=0.0, z=-1.0)
        raise ValueError(f"Invalid face: {face}")
