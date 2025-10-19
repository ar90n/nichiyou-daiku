"""3D coordinate types for woodworking.

This module provides types for representing positions and directions in 3D space.
"""

import math
from typing import overload, cast, Union

from pydantic import BaseModel, field_validator

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


def _edge_legnth_of(box: Box, edge: Edge) -> Millimeters:
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

        # Convert EdgePoint to Point3D using standard logic
        point_3d = Point3D._of_edge_point(box, edge_point)

        # Project Point3D to face's 2D coordinates
        # The projection simply drops the coordinate perpendicular to the face
        # Face coordinate systems (must match _of_surface_point):
        # - top/down: u=X, v=Y (drop Z)
        # - left/right: u=Y, v=Z (drop X)
        # - front/back: u=X, v=Z (drop Y)

        if face in ("top", "down"):
            u = point_3d.x
            v = point_3d.y
        elif face in ("left", "right"):
            u = point_3d.y
            v = point_3d.z
        elif face in ("front", "back"):
            u = point_3d.x
            v = point_3d.z
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
    def of(
        cls, box: Box, source: Union[Corner, EdgePoint, SurfacePoint]
    ) -> "Point3D":
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
            _edge_legnth_of(box, edge_point.edge), edge_point.offset
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
        # based on which face we're on

        if face == "top":
            # Top face: u=X, v=Y, Z=length
            return cls(x=u, y=v, z=box.shape.length)
        elif face == "down":
            # Down face: u=X, v=Y, Z=0
            return cls(x=u, y=v, z=0.0)
        elif face == "left":
            # Left face: u=Y, v=Z, X=0
            return cls(x=0.0, y=u, z=v)
        elif face == "right":
            # Right face: u=Y, v=Z, X=width
            return cls(x=box.shape.width, y=u, z=v)
        elif face == "front":
            # Front face: u=X, v=Z, Y=height
            return cls(x=u, y=box.shape.height, z=v)
        elif face == "back":
            # Back face: u=X, v=Z, Y=0
            return cls(x=u, y=0.0, z=v)
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
            (0.0, -1.0, 0.0)
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


class Orientation3D(BaseModel, frozen=True):
    """3D orientation represented by direction and up vectors.

    Represents a complete 3D orientation using two orthogonal vectors.
    The direction vector is the primary axis (Z-axis in local coordinates),
    and the up vector defines the Y-axis in local coordinates.

    Attributes:
        direction: Primary direction vector (local Z-axis)
        up: Up vector (local Y-axis), orthogonalized to direction

    Examples:
        >>> # Standard upright orientation
        >>> orient = Orientation3D.of(
        ...     direction=Vector3D(x=0.0, y=0.0, z=1.0),
        ...     up=Vector3D(x=0.0, y=1.0, z=0.0)
        ... )
        >>> orient.direction.z
        1.0
        >>> # From face and edge
        >>> orient2 = Orientation3D.of(face="top", edge=Edge(lhs="top", rhs="front"))
        >>> orient2.direction.x
        1.0
    """

    direction: Vector3D
    up: Vector3D

    @field_validator("up")
    @classmethod
    def orthogonalize_up(cls, up: Vector3D, info) -> Vector3D:
        """Ensure up vector is orthogonal to direction."""
        if "direction" not in info.data:
            return up

        direction = info.data["direction"]

        # Calculate dot product
        dot = direction.x * up.x + direction.y * up.y + direction.z * up.z

        # Orthogonalize: up_ortho = up - (up·direction) * direction
        up_ortho_x = up.x - dot * direction.x
        up_ortho_y = up.y - dot * direction.y
        up_ortho_z = up.z - dot * direction.z

        # Normalize
        magnitude = math.sqrt(up_ortho_x**2 + up_ortho_y**2 + up_ortho_z**2)
        if magnitude < 1e-6:
            raise ValueError("Up vector is parallel to direction vector")

        return Vector3D(
            x=up_ortho_x / magnitude, y=up_ortho_y / magnitude, z=up_ortho_z / magnitude
        )

    @overload
    @classmethod
    def of(cls, direction: Vector3D, up: Vector3D) -> "Orientation3D": ...

    @overload
    @classmethod
    def of(cls, face: Face, edge: Edge) -> "Orientation3D": ...

    @overload
    @classmethod
    def of(cls, euler_x: float, euler_y: float, euler_z: float) -> "Orientation3D": ...

    @classmethod
    def of(cls, *args, **kwargs) -> "Orientation3D":
        """Create an Orientation3D from various inputs.

        Can be called with:
        - direction and up vectors
        - face and edge
        - euler angles (in degrees)
        """
        if (
            len(args) == 2
            and isinstance(args[0], Vector3D)
            and isinstance(args[1], Vector3D)
        ):
            return cls._from_vectors(args[0], args[1])
        elif "direction" in kwargs and "up" in kwargs:
            return cls._from_vectors(kwargs["direction"], kwargs["up"])
        elif len(args) == 2 and isinstance(args[0], str) and isinstance(args[1], Edge):
            return cls._from_face_and_edge(cast(Face, args[0]), args[1])
        elif "face" in kwargs and "edge" in kwargs:
            return cls._from_face_and_edge(kwargs["face"], kwargs["edge"])
        elif len(args) == 3:
            if all(isinstance(arg, (int, float)) for arg in args):
                return cls._from_euler_angles(
                    float(cast(float, args[0])),
                    float(cast(float, args[1])),
                    float(cast(float, args[2])),
                )
            else:
                raise TypeError("Euler angles must be numbers")
        elif "euler_x" in kwargs and "euler_y" in kwargs and "euler_z" in kwargs:
            return cls._from_euler_angles(
                float(kwargs["euler_x"]),
                float(kwargs["euler_y"]),
                float(kwargs["euler_z"]),
            )
        else:
            raise TypeError(f"Invalid arguments for Orientation3D.of: {args}, {kwargs}")

    @classmethod
    def _from_vectors(cls, direction: Vector3D, up: Vector3D) -> "Orientation3D":
        """Create from direction and up vectors."""
        # Normalize direction
        dir_mag = math.sqrt(direction.x**2 + direction.y**2 + direction.z**2)
        if dir_mag < 1e-6:
            raise ValueError("Direction vector has zero magnitude")

        norm_direction = Vector3D(
            x=direction.x / dir_mag, y=direction.y / dir_mag, z=direction.z / dir_mag
        )

        return cls(direction=norm_direction, up=up)

    @classmethod
    def _from_face_and_edge(cls, face: Face, edge: Edge) -> "Orientation3D":
        """Create from face normal and edge direction."""
        direction = Vector3D.normal_of(face)
        edge_dir = Vector3D.of(edge)

        # The edge direction serves as the up vector
        return cls(direction=direction, up=edge_dir)

    @classmethod
    def _from_euler_angles(
        cls, euler_x: float, euler_y: float, euler_z: float
    ) -> "Orientation3D":
        """Create from Euler angles (in degrees)."""
        # Convert to radians
        rx = math.radians(euler_x)
        ry = math.radians(euler_y)
        rz = math.radians(euler_z)

        # Calculate rotation matrices
        # Rotation around X
        cx, sx = math.cos(rx), math.sin(rx)
        # Rotation around Y
        cy, sy = math.cos(ry), math.sin(ry)
        # Rotation around Z
        cz, sz = math.cos(rz), math.sin(rz)

        # Combined rotation matrix (ZYX order)
        # Direction vector is the transformed Z-axis
        direction = Vector3D(x=sy, y=-sx * cy, z=cx * cy)

        # Up vector is the transformed Y-axis
        up = Vector3D(x=sz * cy + cz * sx * sy, y=cz * cx, z=-sz * sy + cz * sx * cy)

        return cls(direction=direction, up=up)
