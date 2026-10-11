"""3D coordinate types for woodworking.

This module provides types for representing positions and directions in 3D space.
"""

from typing import overload, Union

from pydantic import BaseModel

from .box import Box
from .corner import Corner
from .edge import EdgePoint, Edge
from .face import (
    cross as cross_face,
    Face,
    is_back_to_front_axis,
    is_down_to_top_axis,
    is_left_to_right_axis,
)
from .offset import evaluate as eval_offset
from .dimensions import Millimeters


def edge_length_of(box: Box, edge: Edge) -> Millimeters:
    """Length of the box edge where the two faces of ``edge`` meet."""
    third_face = cross_face(edge.lhs, edge.rhs)
    # Z-axis (down to top): length
    if is_down_to_top_axis(third_face):
        return box.shape.length
    # X-axis (left to right): width
    if is_left_to_right_axis(third_face):
        return box.shape.width
    # Y-axis (back to front): height
    if is_back_to_front_axis(third_face):
        return box.shape.height

    raise RuntimeError("Unreachable code reached")


class Point2D(BaseModel, frozen=True):
    """2D point in space.

    Represents a position in 2D space.

    Attributes:
        u: U coordinate
        v: V coordinate

    Examples:
        >>> origin = Point2D(u=0.0, v=0.0)
        >>> origin.u
        0.0
    """

    u: float
    v: float


class SurfacePoint(BaseModel, frozen=True):
    """A point on a piece's surface.

    Represents a 2D position on a specific face of a piece.

    Attributes:
        face: The face where the point is located
        position: 2D coordinates on the face surface

    Examples:
        >>> from nichiyou_daiku.core.geometry import Point2D
        >>> sp = SurfacePoint(face="top", position=Point2D(u=50.0, v=25.0))
        >>> sp.face
        'top'
        >>> sp.position.u
        50.0
    """

    face: Face
    position: Point2D

    @classmethod
    def of(cls, box: Box, face: Face, edge_point: EdgePoint) -> "SurfacePoint":
        """Create a SurfacePoint from a face and edge point.

        Converts an EdgePoint (edge + offset) to 2D coordinates on the specified face.

        This method uses the same logic as Point3D._of_edge_point() to ensure
        that Point3D.of(box, edge_point) and Point3D.of(box, SurfacePoint.of(box, face, edge_point))
        produce the same result.

        Args:
            box: The bounding box (needed to determine coordinate system)
            face: The face where the point is located
            edge_point: Point along an edge

        Returns:
            SurfacePoint with 2D coordinates on the face
        """
        edge = edge_point.edge

        # Verify the edge belongs to the specified face
        if edge.lhs != face and edge.rhs != face:
            raise ValueError(f"Edge {edge} does not belong to face {face}")

        return cls.from_point(box, face, Point3D._of_edge_point(box, edge_point))

    @classmethod
    def from_point(cls, box: Box, face: Face, point: "Point3D") -> "SurfacePoint":
        """Express a point lying on ``face`` in that face's 2D coordinates.

        Inverse of ``Point3D.of(box, surface_point)``.

        Args:
            box: The piece's box
            face: The face the point lies on
            point: The point in the piece's local coordinates

        Returns:
            SurfacePoint with 2D coordinates centred on the face
        """
        # Face frames are right-handed (u x v = outward normal), centred on the face:
        # - top:   u=+X, v=+Y
        # - down:  u=-X, v=+Y
        # - left:  u=-Y, v=+Z
        # - right: u=+Y, v=+Z
        # - front: u=-X, v=+Z
        # - back:  u=+X, v=+Z
        width, height, length = box.shape.width, box.shape.height, box.shape.length
        if face == "top":
            u, v = point.x - width / 2, point.y - height / 2
        elif face == "down":
            u, v = width / 2 - point.x, point.y - height / 2
        elif face == "left":
            u, v = height / 2 - point.y, point.z - length / 2
        elif face == "right":
            u, v = point.y - height / 2, point.z - length / 2
        elif face == "front":
            u, v = width / 2 - point.x, point.z - length / 2
        elif face == "back":
            u, v = point.x - width / 2, point.z - length / 2
        else:
            raise ValueError(f"Invalid face: {face}")
        return cls(face=face, position=Point2D(u=u, v=v))


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
    def of(cls, box: Box, source: Corner) -> "Point3D": ...
    @overload
    @classmethod
    def of(cls, box: Box, source: EdgePoint) -> "Point3D": ...
    @overload
    @classmethod
    def of(cls, box: Box, source: SurfacePoint) -> "Point3D": ...
    @classmethod
    def of(cls, box: Box, source: Union[Corner, EdgePoint, SurfacePoint]) -> "Point3D":
        """Create a 3D point from a box and a corner, edge point, or surface point.

        Args:
            box: The bounding box
            source: Either a corner, edge point, or surface point

        Returns:
            Point3D at the specified position
        """
        if isinstance(source, Corner):
            return cls._of_corner(box, source)
        if isinstance(source, EdgePoint):
            return cls._of_edge_point(box, source)
        if isinstance(source, SurfacePoint):
            return cls._of_surface_point(box, source)
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
        # X-axis: left to right (width)
        x = 0.0 if corner.face_right_left == "left" else box.shape.width
        # Y-axis: back to front (height)
        y = 0.0 if corner.face_front_back == "back" else box.shape.height
        # Z-axis: down to top (length)
        z = 0.0 if corner.face_top_down == "down" else box.shape.length
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
        offset_length = eval_offset(
            edge_length_of(box, edge_point.edge), edge_point.offset
        )

        return cls(
            x=origin.x + direction.x * offset_length,
            y=origin.y + direction.y * offset_length,
            z=origin.z + direction.z * offset_length,
        )

    @classmethod
    def _of_surface_point(cls, box: Box, surface_point: SurfacePoint) -> "Point3D":
        """Create a 3D point from a surface point.

        Args:
            box: The bounding box
            surface_point: The point on a face surface

        Returns:
            Point3D at the specified surface point
        """
        face = surface_point.face
        u = surface_point.position.u
        v = surface_point.position.v

        # Map 2D coordinates (u, v) to 3D coordinates (x, y, z)
        # SurfacePoint uses face center as origin, so add center offsets
        #
        # RIGHT-HANDED coordinate systems (u × v = direction):
        # Each face has: right = cross(up, direction), u = right, v = up
        #
        # - top:   u=+X, v=+Y (unchanged)
        # - down:  u=-X, v=+Y (u-axis flipped)
        # - left:  u=-Y, v=+Z (u-axis flipped)
        # - right: u=+Y, v=+Z (unchanged)
        # - front: u=-X, v=+Z (u-axis flipped)
        # - back:  u=+X, v=+Z (unchanged)

        if face == "top":
            # Top face: direction=+Z, up=+Y, right=+X → u=+X, v=+Y
            return cls(
                x=u + box.shape.width / 2,
                y=v + box.shape.height / 2,
                z=box.shape.length,
            )
        elif face == "down":
            # Down face: direction=-Z, up=+Y, right=-X → u=-X, v=+Y
            return cls(x=-u + box.shape.width / 2, y=v + box.shape.height / 2, z=0.0)
        elif face == "left":
            # Left face: direction=-X, up=+Z, right=-Y → u=-Y, v=+Z
            return cls(x=0.0, y=-u + box.shape.height / 2, z=v + box.shape.length / 2)
        elif face == "right":
            # Right face: direction=+X, up=+Z, right=+Y → u=+Y, v=+Z
            return cls(
                x=box.shape.width,
                y=u + box.shape.height / 2,
                z=v + box.shape.length / 2,
            )
        elif face == "front":
            # Front face: direction=+Y, up=+Z, right=-X → u=-X, v=+Z
            return cls(
                x=-u + box.shape.width / 2,
                y=box.shape.height,
                z=v + box.shape.length / 2,
            )
        elif face == "back":
            # Back face: direction=-Y, up=+Z, right=+X → u=+X, v=+Z
            return cls(x=u + box.shape.width / 2, y=0.0, z=v + box.shape.length / 2)
        else:
            raise ValueError(f"Invalid face: {face}")


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
    def of(cls, edge: Edge) -> "Vector3D":
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
            (-1.0, 0.0, 0.0)
        """
        result_face = cross_face(edge.lhs, edge.rhs)
        return cls.normal_of(result_face)

    @classmethod
    def normal_of(cls, face: Face) -> "Vector3D":
        """Get the normal vector for a face.

        Returns a unit vector pointing outward from the specified face.

        Args:
            face: The face to get the normal for (e.g., "top", "down", "left", "right", "front", "back")

        Returns:
            Vector3D representing the normal direction

        Examples:
            >>> normal = Vector3D.normal_of("top")
            >>> normal.z
            1.0
        """
        match face:
            case "left":
                return cls(x=-1.0, y=0.0, z=0.0)
            case "right":
                return cls(x=1.0, y=0.0, z=0.0)
            case "back":
                return cls(x=0.0, y=-1.0, z=0.0)
            case "front":
                return cls(x=0.0, y=1.0, z=0.0)
            case "down":
                return cls(x=0.0, y=0.0, z=-1.0)
            case "top":
                return cls(x=0.0, y=0.0, z=1.0)
        raise ValueError(f"Invalid face: {face}")
