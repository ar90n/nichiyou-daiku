"""Geometry utilities for woodworking calculations.

This module provides geometric transformations and spatial calculations
for lumber pieces, including face normals, edge classifications, and
3D transformations.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Set, Tuple, NewType
import numpy as np

from nichiyou_daiku.core.lumber import Face

# Type aliases
Normal3D = NewType("Normal3D", Tuple[float, float, float])
RotationMatrix = NewType("RotationMatrix", np.ndarray)
Degrees = NewType("Degrees", float)


class EdgeType(Enum):
    """Type of edge based on its orientation."""

    HORIZONTAL = "horizontal"  # Parallel to length
    VERTICAL = "vertical"  # Parallel to height
    WIDTH = "width"  # Parallel to width


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
        <EdgeType.HORIZONTAL: 'horizontal'>
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

    # Define edge classifications
    edge_classifications: Dict[EdgeType, list[Set[Face]]] = {
        EdgeType.HORIZONTAL: [
            {Face.TOP, Face.RIGHT},
            {Face.TOP, Face.LEFT},
            {Face.BOTTOM, Face.RIGHT},
            {Face.BOTTOM, Face.LEFT},
        ],
        EdgeType.VERTICAL: [
            {Face.FRONT, Face.RIGHT},
            {Face.FRONT, Face.LEFT},
            {Face.BACK, Face.RIGHT},
            {Face.BACK, Face.LEFT},
        ],
        EdgeType.WIDTH: [
            {Face.TOP, Face.FRONT},
            {Face.TOP, Face.BACK},
            {Face.BOTTOM, Face.FRONT},
            {Face.BOTTOM, Face.BACK},
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
