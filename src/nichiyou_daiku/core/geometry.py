"""Geometry utilities for woodworking calculations.

This module provides geometric transformations and spatial calculations
for lumber pieces, including face normals, edge classifications, and
3D transformations.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Set, Tuple, Optional
import numpy as np

from nichiyou_daiku.core.lumber import Face, LumberPiece

# Type aliases
Normal3D = Tuple[float, float, float]
RotationMatrix = np.ndarray
Degrees = float
Point3D = Tuple[float, float, float]
Vector3D = Tuple[float, float, float]
Line3D = Tuple[Point3D, Vector3D]  # Point and direction


class EdgeType(Enum):
    """Type of edge based on its orientation."""

    LENGTH_WISE = "length_wise"  # Along the length axis (X)
    WIDTH_WISE = "width_wise"    # Along the width axis (Y)
    HEIGHT_WISE = "height_wise"  # Along the height axis (Z)


@dataclass(frozen=True)
class EdgePosition:
    """Position of an edge where two faces meet.

    Attributes:
        face1: First face forming the edge
        face2: Second face forming the edge
        position: Normalized position along the edge (0.0 to 1.0)
    """

    face1: Face
    face2: Face
    position: float = 0.0

    def get_edge_type(self) -> EdgeType:
        """Determine the type of edge based on the two faces.

        Returns:
            EdgeType indicating the orientation of the edge

        >>> edge = EdgePosition(Face.TOP, Face.RIGHT)
        >>> edge.get_edge_type()
        <EdgeType.WIDTH_WISE: 'width_wise'>
        """
        return _classify_edge_type(self.face1, self.face2)


@dataclass(frozen=True)
class FaceLocation:
    """Location on a face using normalized UV coordinates.

    Attributes:
        face: The face this location is on
        u_position: Horizontal position (0.0=left/back, 1.0=right/front)
        v_position: Vertical position (0.0=bottom, 1.0=top)
    """

    face: Face
    u_position: float = 0.5
    v_position: float = 0.5

    def __post_init__(self):
        """Validate position ranges."""
        _validate_normalized_value(self.u_position, "u_position")
        _validate_normalized_value(self.v_position, "v_position")


def get_face_normal(face: Face) -> Tuple[float, float, float]:
    """Get the normal vector for a face.

    Args:
        face: The face to get the normal for

    Returns:
        Unit normal vector (nx, ny, nz) pointing outward from the face

    >>> get_face_normal(Face.TOP)
    (0.0, 0.0, 1.0)
    >>> get_face_normal(Face.FRONT)
    (1.0, 0.0, 0.0)
    """
    normals = {
        Face.TOP: (0.0, 0.0, 1.0),
        Face.BOTTOM: (0.0, 0.0, -1.0),
        Face.RIGHT: (0.0, 1.0, 0.0),
        Face.LEFT: (0.0, -1.0, 0.0),
        Face.FRONT: (1.0, 0.0, 0.0),
        Face.BACK: (-1.0, 0.0, 0.0),
    }
    return normals[face]


def calculate_rotation_matrix(rx: float, ry: float, rz: float) -> np.ndarray:
    """Calculate 3D rotation matrix from Euler angles.

    Args:
        rx: Rotation around X-axis in degrees
        ry: Rotation around Y-axis in degrees
        rz: Rotation around Z-axis in degrees

    Returns:
        3x3 rotation matrix

    >>> matrix = calculate_rotation_matrix(0.0, 0.0, 0.0)
    >>> np.allclose(matrix, np.eye(3))
    True
    """
    # Convert degrees to radians
    rx_rad = np.radians(rx)
    ry_rad = np.radians(ry)
    rz_rad = np.radians(rz)

    # Rotation matrices for each axis
    Rx = np.array(
        [
            [1, 0, 0],
            [0, np.cos(rx_rad), -np.sin(rx_rad)],
            [0, np.sin(rx_rad), np.cos(rx_rad)],
        ]
    )

    Ry = np.array(
        [
            [np.cos(ry_rad), 0, np.sin(ry_rad)],
            [0, 1, 0],
            [-np.sin(ry_rad), 0, np.cos(ry_rad)],
        ]
    )

    Rz = np.array(
        [
            [np.cos(rz_rad), -np.sin(rz_rad), 0],
            [np.sin(rz_rad), np.cos(rz_rad), 0],
            [0, 0, 1],
        ]
    )

    # Combined rotation: Rz * Ry * Rx
    return Rz @ Ry @ Rx


def transform_point(
    point: Tuple[float, float, float],
    rotation_matrix: np.ndarray,
    offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> Tuple[float, float, float]:
    """Transform a 3D point using rotation and translation.

    Args:
        point: Original point (x, y, z)
        rotation_matrix: 3x3 rotation matrix
        offset: Translation offset (dx, dy, dz)

    Returns:
        Transformed point (x', y', z')

    >>> point = (1.0, 0.0, 0.0)
    >>> matrix = np.eye(3)
    >>> transform_point(point, matrix)
    (1.0, 0.0, 0.0)
    """
    # Convert to numpy array for matrix multiplication
    p = np.array(point)

    # Apply rotation
    rotated = rotation_matrix @ p

    # Apply translation
    result = rotated + np.array(offset)

    # Convert back to tuple with explicit typing
    x, y, z = result
    return (float(x), float(y), float(z))


# Module-level helper functions following functional programming approach


def _classify_edge_type(face1: Face, face2: Face) -> EdgeType:
    """Classify the type of edge formed by two faces.

    Args:
        face1: First face
        face2: Second face

    Returns:
        EdgeType classification

    Raises:
        ValueError: If faces don't form a valid edge
    """
    face_set = {face1, face2}

    # Define edge classifications based on axis orientation
    edge_classifications: Dict[EdgeType, list[Set[Face]]] = {
        EdgeType.LENGTH_WISE: [  # Edges along X axis (length)
            {Face.TOP, Face.FRONT},
            {Face.TOP, Face.BACK},
            {Face.BOTTOM, Face.FRONT},
            {Face.BOTTOM, Face.BACK},
            {Face.RIGHT, Face.LEFT},  # Also runs along length
        ],
        EdgeType.WIDTH_WISE: [  # Edges along Y axis (width)
            {Face.TOP, Face.RIGHT},
            {Face.TOP, Face.LEFT},
            {Face.BOTTOM, Face.RIGHT},
            {Face.BOTTOM, Face.LEFT},
            {Face.FRONT, Face.BACK},  # Also runs along width
        ],
        EdgeType.HEIGHT_WISE: [  # Edges along Z axis (height)
            {Face.FRONT, Face.RIGHT},
            {Face.FRONT, Face.LEFT},
            {Face.BACK, Face.RIGHT},
            {Face.BACK, Face.LEFT},
        ],
    }

    # Find matching edge type
    for edge_type, face_pairs in edge_classifications.items():
        if face_set in face_pairs:
            return edge_type

    raise ValueError(f"Faces {face1} and {face2} do not form a valid edge")


def _validate_normalized_value(value: float, name: str) -> None:
    """Validate that a value is in the normalized range [0.0, 1.0].

    Args:
        value: The value to validate
        name: Name of the value for error messages

    Raises:
        ValueError: If value is outside [0.0, 1.0]
    """
    if not (0.0 <= value <= 1.0):
        raise ValueError(f"{name} must be between 0.0 and 1.0, got {value}")


def get_face_tangents(
    face: Face,
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """Get the two tangent vectors for a face (U and V directions).

    Args:
        face: The face to get tangents for

    Returns:
        Tuple of (u_tangent, v_tangent) unit vectors
    """
    tangents: Dict[
        Face, Tuple[Tuple[float, float, float], Tuple[float, float, float]]
    ] = {
        Face.TOP: ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),  # U=X, V=Y
        Face.BOTTOM: ((1.0, 0.0, 0.0), (0.0, -1.0, 0.0)),  # U=X, V=-Y
        Face.RIGHT: ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),  # U=X, V=Z
        Face.LEFT: ((-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),  # U=-X, V=Z
        Face.FRONT: ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),  # U=Y, V=Z
        Face.BACK: ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),  # U=-Y, V=Z
    }
    return tangents[face]


# Distance calculation functions


def calculate_distance(point1: Point3D, point2: Point3D) -> float:
    """Calculate Euclidean distance between two 3D points.

    Args:
        point1: First point (x, y, z)
        point2: Second point (x, y, z)

    Returns:
        Distance between the points

    >>> calculate_distance((0, 0, 0), (3, 4, 0))
    5.0
    """
    p1 = np.array(point1)
    p2 = np.array(point2)
    return float(np.linalg.norm(p2 - p1))


def calculate_point_to_line_distance(
    point: Point3D, line_point: Point3D, line_direction: Vector3D
) -> float:
    """Calculate shortest distance from a point to a line in 3D.

    Args:
        point: The point to measure from
        line_point: A point on the line
        line_direction: Direction vector of the line

    Returns:
        Shortest distance from point to line

    >>> calculate_point_to_line_distance((0, 3, 4), (0, 0, 0), (1, 0, 0))
    5.0
    """
    p = np.array(point)
    l0 = np.array(line_point)
    l_dir = np.array(line_direction)

    # Normalize line direction
    l_dir = l_dir / np.linalg.norm(l_dir)

    # Vector from line point to point
    w = p - l0

    # Project w onto line direction
    c = np.dot(w, l_dir)

    # Point on line closest to p
    closest = l0 + c * l_dir

    # Distance is magnitude of difference
    return float(np.linalg.norm(p - closest))


# Angle calculation functions


def calculate_angle_between_vectors(vec1: Vector3D, vec2: Vector3D) -> float:
    """Calculate angle between two vectors in degrees.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Angle in degrees (0 to 180)

    >>> calculate_angle_between_vectors((1, 0, 0), (0, 1, 0))
    90.0
    """
    v1 = np.array(vec1)
    v2 = np.array(vec2)

    # Normalize vectors
    v1_norm = v1 / np.linalg.norm(v1)
    v2_norm = v2 / np.linalg.norm(v2)

    # Calculate angle using dot product
    cos_angle = np.clip(np.dot(v1_norm, v2_norm), -1.0, 1.0)
    angle_rad = np.arccos(cos_angle)

    return float(np.degrees(angle_rad))


def calculate_angle_between_faces(
    piece1: LumberPiece,
    face1: Face,
    pos1: Tuple[float, float, float],
    rot1: Tuple[float, float, float],
    piece2: LumberPiece,
    face2: Face,
    pos2: Tuple[float, float, float],
    rot2: Tuple[float, float, float],
) -> float:
    """Calculate angle between two faces of lumber pieces.

    Args:
        piece1: First lumber piece
        face1: Face on first piece
        pos1: World position of first piece
        rot1: World rotation of first piece (degrees)
        piece2: Second lumber piece
        face2: Face on second piece
        pos2: World position of second piece
        rot2: World rotation of second piece (degrees)

    Returns:
        Angle between faces in degrees (0 to 180)
    """
    # Get face normals in local coordinates
    normal1_local = get_face_normal(face1)
    normal2_local = get_face_normal(face2)

    # Transform to world coordinates
    rot_matrix1 = calculate_rotation_matrix(rot1[0], rot1[1], rot1[2])
    rot_matrix2 = calculate_rotation_matrix(rot2[0], rot2[1], rot2[2])

    normal1_world = rot_matrix1 @ np.array(normal1_local)
    normal2_world = rot_matrix2 @ np.array(normal2_local)

    # Calculate angle between normals
    return calculate_angle_between_vectors(
        (float(normal1_world[0]), float(normal1_world[1]), float(normal1_world[2])),
        (float(normal2_world[0]), float(normal2_world[1]), float(normal2_world[2])),
    )


def calculate_dihedral_angle(normal1: Vector3D, normal2: Vector3D) -> float:
    """Calculate dihedral angle between two planes given their normals.

    Args:
        normal1: Normal vector of first plane
        normal2: Normal vector of second plane

    Returns:
        Dihedral angle in degrees (0 to 180)

    >>> calculate_dihedral_angle((0, 0, 1), (1, 0, 0))
    90.0
    """
    return calculate_angle_between_vectors(normal1, normal2)


# Intersection detection functions


def check_line_intersection(
    line1_start: Point3D,
    line1_end: Point3D,
    line2_start: Point3D,
    line2_end: Point3D,
    tolerance: float = 1e-10,
) -> Tuple[bool, Optional[Point3D]]:
    """Check if two line segments intersect in 3D.

    Args:
        line1_start: Start point of first line segment
        line1_end: End point of first line segment
        line2_start: Start point of second line segment
        line2_end: End point of second line segment
        tolerance: Maximum distance between lines to consider intersection

    Returns:
        Tuple of (intersects, intersection_point)

    Note: This uses a threshold for determining intersection in 3D space
    """
    # Convert to numpy arrays
    p1 = np.array(line1_start)
    p2 = np.array(line1_end)
    p3 = np.array(line2_start)
    p4 = np.array(line2_end)

    # Direction vectors
    d1 = p2 - p1
    d2 = p4 - p3

    # Vector between line starts
    w = p1 - p3

    # Calculate parameters for closest points
    a = np.dot(d1, d1)
    b = np.dot(d1, d2)
    c = np.dot(d2, d2)
    d = np.dot(d1, w)
    e = np.dot(d2, w)

    denom = a * c - b * b

    # Check if lines are parallel
    if abs(denom) < 1e-10:
        return False, None

    # Calculate parameters
    s = (b * e - c * d) / denom
    t = (a * e - b * d) / denom

    # Check if intersection is within line segments
    if 0 <= s <= 1 and 0 <= t <= 1:
        # Calculate closest points
        point1 = p1 + s * d1
        point2 = p3 + t * d2

        # Check if points are close enough to be considered intersecting
        distance = np.linalg.norm(point2 - point1)
        if distance < tolerance:
            intersection_arr = (point1 + point2) / 2
            intersection = (
                float(intersection_arr[0]),
                float(intersection_arr[1]),
                float(intersection_arr[2]),
            )
            return True, intersection

    return False, None


def check_plane_intersection(
    line_point: Point3D,
    line_direction: Vector3D,
    plane_point: Point3D,
    plane_normal: Vector3D,
) -> Tuple[bool, Optional[Point3D]]:
    """Check if a line intersects a plane.

    Args:
        line_point: A point on the line
        line_direction: Direction vector of the line
        plane_point: A point on the plane
        plane_normal: Normal vector of the plane

    Returns:
        Tuple of (intersects, intersection_point)
    """
    l0 = np.array(line_point)
    line_dir = np.array(line_direction)
    p0 = np.array(plane_point)
    n = np.array(plane_normal)

    # Normalize vectors
    line_dir = line_dir / np.linalg.norm(line_dir)
    n = n / np.linalg.norm(n)

    # Check if line is parallel to plane
    denom = np.dot(line_dir, n)
    if abs(denom) < 1e-10:
        return False, None

    # Calculate intersection parameter
    t = np.dot((p0 - l0), n) / denom

    # Calculate intersection point
    intersection = l0 + t * line_dir

    return True, (
        float(intersection[0]),
        float(intersection[1]),
        float(intersection[2]),
    )


# Coordinate transformation functions


def transform_to_world_coordinates(
    local_point: Point3D,
    position: Tuple[float, float, float],
    rotation: Tuple[float, float, float],
) -> Point3D:
    """Transform a point from local to world coordinates.

    Args:
        local_point: Point in local coordinates
        position: World position of the object
        rotation: World rotation of the object (rx, ry, rz in degrees)

    Returns:
        Point in world coordinates
    """
    # Get rotation matrix
    rot_matrix = calculate_rotation_matrix(rotation[0], rotation[1], rotation[2])

    # Apply transformation
    world_point = transform_point(local_point, rot_matrix, position)

    return world_point


def transform_to_local_coordinates(
    world_point: Point3D,
    position: Tuple[float, float, float],
    rotation: Tuple[float, float, float],
) -> Point3D:
    """Transform a point from world to local coordinates.

    Args:
        world_point: Point in world coordinates
        position: World position of the object
        rotation: World rotation of the object (rx, ry, rz in degrees)

    Returns:
        Point in local coordinates
    """
    # Get rotation matrix and its inverse (transpose for orthogonal matrix)
    rot_matrix = calculate_rotation_matrix(rotation[0], rotation[1], rotation[2])
    inv_rot_matrix = rot_matrix.T

    # Translate to object origin
    translated = np.array(world_point) - np.array(position)

    # Apply inverse rotation
    local = inv_rot_matrix @ translated

    return (float(local[0]), float(local[1]), float(local[2]))


# Projection functions


def project_point_onto_plane(
    point: Point3D, plane_normal: Vector3D, plane_point: Point3D
) -> Point3D:
    """Project a point onto a plane.

    Args:
        point: The point to project
        plane_normal: Normal vector of the plane
        plane_point: A point on the plane

    Returns:
        Projected point on the plane

    >>> project_point_onto_plane((3, 4, 5), (0, 0, 1), (0, 0, 0))
    (3.0, 4.0, 0.0)
    """
    p = np.array(point)
    p0 = np.array(plane_point)
    n = np.array(plane_normal)

    # Normalize normal
    norm = np.linalg.norm(n)
    if norm < 1e-10:
        # If normal is zero vector, return original point
        return point
    n = n / norm

    # Vector from plane point to point
    v = p - p0

    # Distance from point to plane
    dist = np.dot(v, n)

    # Projected point
    projected = p - dist * n

    return (float(projected[0]), float(projected[1]), float(projected[2]))


def calculate_closest_points_between_lines(
    line1_point: Point3D,
    line1_dir: Vector3D,
    line2_point: Point3D,
    line2_dir: Vector3D,
) -> Tuple[Point3D, Point3D]:
    """Calculate the closest points between two lines in 3D.

    Args:
        line1_point: A point on the first line
        line1_dir: Direction vector of the first line
        line2_point: A point on the second line
        line2_dir: Direction vector of the second line

    Returns:
        Tuple of (closest_point_on_line1, closest_point_on_line2)
    """
    p1 = np.array(line1_point)
    d1 = np.array(line1_dir)
    p2 = np.array(line2_point)
    d2 = np.array(line2_dir)

    # Normalize directions
    d1 = d1 / np.linalg.norm(d1)
    d2 = d2 / np.linalg.norm(d2)

    # Vector between line points
    w = p1 - p2

    # Calculate parameters
    a = np.dot(d1, d1)  # Should be 1
    b = np.dot(d1, d2)
    c = np.dot(d2, d2)  # Should be 1
    d = np.dot(d1, w)
    e = np.dot(d2, w)

    denom = a * c - b * b

    # Check if lines are parallel
    if abs(denom) < 1e-10:
        # Lines are parallel, return the original points
        return (float(p1[0]), float(p1[1]), float(p1[2])), (
            float(p2[0]),
            float(p2[1]),
            float(p2[2]),
        )

    # Calculate parameters for closest points
    s = (b * e - c * d) / denom
    t = (a * e - b * d) / denom

    # Calculate closest points
    closest1 = p1 + s * d1
    closest2 = p2 + t * d2

    return (
        (float(closest1[0]), float(closest1[1]), float(closest1[2])),
        (float(closest2[0]), float(closest2[1]), float(closest2[2])),
    )
