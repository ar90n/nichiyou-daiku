"""Tests for geometry utility classes and functions."""

import pytest
import numpy as np
from nichiyou_daiku.core.geometry import (
    EdgePoint,
    FaceLocation,
    get_face_normal,
    get_face_tangents,
    calculate_rotation_matrix,
    transform_point,
    EdgeType,
)
from nichiyou_daiku.core.lumber import Face


class TestEdgePoint:
    """Test EdgePoint dataclass."""

    def test_edge_position_creation(self):
        """Test creating an edge position."""
        edge = EdgePoint(face1=Face.TOP, face2=Face.FRONT, position=0.5)
        assert edge.face1 == Face.TOP
        assert edge.face2 == Face.FRONT
        assert edge.position == 0.5

    def test_edge_position_default(self):
        """Test edge position with default position."""
        edge = EdgePoint(face1=Face.LEFT, face2=Face.BACK)
        assert edge.position == 0.0

    def test_edge_position_immutable(self):
        """Test that edge position is immutable."""
        edge = EdgePoint(Face.TOP, Face.RIGHT, 0.75)
        with pytest.raises(AttributeError):
            edge.position = 0.25

    def test_get_edge_type(self):
        """Test determining edge type from faces."""
        # Length-wise edges (parallel to length/X axis)
        assert EdgePoint(Face.TOP, Face.RIGHT).get_edge_type() == EdgeType.WIDTH_WISE
        assert EdgePoint(Face.BOTTOM, Face.LEFT).get_edge_type() == EdgeType.WIDTH_WISE

        # Height-wise edges (parallel to height/Z axis)
        assert EdgePoint(Face.FRONT, Face.RIGHT).get_edge_type() == EdgeType.HEIGHT_WISE
        assert EdgePoint(Face.BACK, Face.LEFT).get_edge_type() == EdgeType.HEIGHT_WISE

        # Width-wise edges (parallel to width/Y axis)
        assert EdgePoint(Face.TOP, Face.FRONT).get_edge_type() == EdgeType.LENGTH_WISE
        assert EdgePoint(Face.BOTTOM, Face.BACK).get_edge_type() == EdgeType.LENGTH_WISE

    def test_get_edge_type_invalid(self):
        """Test that invalid face combinations raise ValueError."""
        # Opposite faces don't form an edge
        with pytest.raises(ValueError, match="do not form a valid edge"):
            EdgePoint(Face.TOP, Face.BOTTOM).get_edge_type()

        # Same face doesn't form an edge
        with pytest.raises(ValueError, match="do not form a valid edge"):
            EdgePoint(Face.FRONT, Face.FRONT).get_edge_type()


class TestFaceLocation:
    """Test FaceLocation dataclass."""

    def test_face_location_creation(self):
        """Test creating a face location."""
        loc = FaceLocation(face=Face.TOP, u_position=0.25, v_position=0.75)
        assert loc.face == Face.TOP
        assert loc.u_position == 0.25
        assert loc.v_position == 0.75

    def test_face_location_defaults(self):
        """Test face location with default positions."""
        loc = FaceLocation(face=Face.FRONT)
        assert loc.u_position == 0.5
        assert loc.v_position == 0.5

    def test_face_location_immutable(self):
        """Test that face location is immutable."""
        loc = FaceLocation(Face.RIGHT, 0.1, 0.9)
        with pytest.raises(AttributeError):
            loc.u_position = 0.5

    def test_face_location_validation(self):
        """Test that face location validates position ranges."""
        # Valid locations
        FaceLocation(Face.TOP, 0.0, 0.0)  # Corner
        FaceLocation(Face.TOP, 1.0, 1.0)  # Opposite corner
        FaceLocation(Face.TOP, 0.5, 0.5)  # Center

        # Invalid locations should raise ValueError
        with pytest.raises(ValueError):
            FaceLocation(Face.TOP, -0.1, 0.5)
        with pytest.raises(ValueError):
            FaceLocation(Face.TOP, 0.5, 1.1)


class TestFaceNormal:
    """Test face normal calculation."""

    def test_get_face_normal_standard_faces(self):
        """Test getting normal vectors for standard faces."""
        # Test each face normal
        assert get_face_normal(Face.TOP) == (0.0, 0.0, 1.0)
        assert get_face_normal(Face.BOTTOM) == (0.0, 0.0, -1.0)
        assert get_face_normal(Face.RIGHT) == (0.0, 1.0, 0.0)
        assert get_face_normal(Face.LEFT) == (0.0, -1.0, 0.0)
        assert get_face_normal(Face.FRONT) == (1.0, 0.0, 0.0)
        assert get_face_normal(Face.BACK) == (-1.0, 0.0, 0.0)

    def test_face_normal_unit_vectors(self):
        """Test that all face normals are unit vectors."""
        for face in Face:
            normal = get_face_normal(face)
            magnitude = sum(n**2 for n in normal) ** 0.5
            assert abs(magnitude - 1.0) < 1e-10


class TestFaceTangents:
    """Test face tangent calculation."""

    def test_get_face_tangents_all_faces(self):
        """Test getting tangent vectors for all faces."""
        # Test TOP face
        u, v = get_face_tangents(Face.TOP)
        assert u == (1.0, 0.0, 0.0)  # X direction
        assert v == (0.0, 1.0, 0.0)  # Y direction

        # Test BOTTOM face
        u, v = get_face_tangents(Face.BOTTOM)
        assert u == (1.0, 0.0, 0.0)  # X direction
        assert v == (0.0, -1.0, 0.0)  # -Y direction

        # Test RIGHT face
        u, v = get_face_tangents(Face.RIGHT)
        assert u == (1.0, 0.0, 0.0)  # X direction
        assert v == (0.0, 0.0, 1.0)  # Z direction

        # Test LEFT face
        u, v = get_face_tangents(Face.LEFT)
        assert u == (-1.0, 0.0, 0.0)  # -X direction
        assert v == (0.0, 0.0, 1.0)  # Z direction

        # Test FRONT face
        u, v = get_face_tangents(Face.FRONT)
        assert u == (0.0, 1.0, 0.0)  # Y direction
        assert v == (0.0, 0.0, 1.0)  # Z direction

        # Test BACK face
        u, v = get_face_tangents(Face.BACK)
        assert u == (0.0, -1.0, 0.0)  # -Y direction
        assert v == (0.0, 0.0, 1.0)  # Z direction

    def test_face_tangents_orthogonal(self):
        """Test that face tangents are orthogonal to the normal."""
        for face in Face:
            normal = get_face_normal(face)
            u_tangent, v_tangent = get_face_tangents(face)

            # Check dot product with normal is zero (orthogonal)
            u_dot_n = sum(u * n for u, n in zip(u_tangent, normal))
            v_dot_n = sum(v * n for v, n in zip(v_tangent, normal))

            assert abs(u_dot_n) < 1e-10
            assert abs(v_dot_n) < 1e-10

    def test_face_tangents_orthogonal_to_each_other(self):
        """Test that U and V tangents are orthogonal to each other."""
        for face in Face:
            u_tangent, v_tangent = get_face_tangents(face)

            # Check dot product is zero (orthogonal)
            dot_product = sum(u * v for u, v in zip(u_tangent, v_tangent))
            assert abs(dot_product) < 1e-10


class TestRotationMatrix:
    """Test rotation matrix calculation."""

    def test_identity_rotation(self):
        """Test that zero rotation gives identity matrix."""
        matrix = calculate_rotation_matrix(0.0, 0.0, 0.0)
        expected = np.eye(3)
        np.testing.assert_array_almost_equal(matrix, expected)

    def test_90_degree_rotations(self):
        """Test 90 degree rotations around each axis."""
        # 90 degree rotation around X axis
        matrix_x = calculate_rotation_matrix(90.0, 0.0, 0.0)
        point = (0.0, 1.0, 0.0)
        rotated = transform_point(point, matrix_x)
        np.testing.assert_array_almost_equal(rotated, (0.0, 0.0, 1.0))

        # 90 degree rotation around Y axis
        matrix_y = calculate_rotation_matrix(0.0, 90.0, 0.0)
        point = (1.0, 0.0, 0.0)
        rotated = transform_point(point, matrix_y)
        np.testing.assert_array_almost_equal(rotated, (0.0, 0.0, -1.0))

        # 90 degree rotation around Z axis
        matrix_z = calculate_rotation_matrix(0.0, 0.0, 90.0)
        point = (1.0, 0.0, 0.0)
        rotated = transform_point(point, matrix_z)
        np.testing.assert_array_almost_equal(rotated, (0.0, 1.0, 0.0))

    def test_combined_rotation(self):
        """Test combined rotations."""
        matrix = calculate_rotation_matrix(45.0, 30.0, 60.0)
        # Matrix should be orthogonal (inverse = transpose)
        inverse = np.linalg.inv(matrix)
        transpose = matrix.T
        np.testing.assert_array_almost_equal(inverse, transpose)

    def test_rotation_preserves_length(self):
        """Test that rotation preserves vector length."""
        matrix = calculate_rotation_matrix(37.0, 53.0, 71.0)
        point = (3.0, 4.0, 5.0)
        rotated = transform_point(point, matrix)

        original_length = sum(p**2 for p in point) ** 0.5
        rotated_length = sum(p**2 for p in rotated) ** 0.5

        assert abs(original_length - rotated_length) < 1e-10


class TestTransformPoint:
    """Test point transformation."""

    def test_transform_identity(self):
        """Test transforming with identity matrix."""
        point = (1.0, 2.0, 3.0)
        matrix = np.eye(3)
        result = transform_point(point, matrix)
        assert result == point

    def test_transform_with_offset(self):
        """Test transforming with offset."""
        point = (1.0, 0.0, 0.0)
        matrix = np.eye(3)  # No rotation
        offset = (10.0, 20.0, 30.0)
        result = transform_point(point, matrix, offset)
        assert result == (11.0, 20.0, 30.0)

    def test_transform_rotation_and_offset(self):
        """Test combined rotation and offset."""
        point = (1.0, 0.0, 0.0)
        # 90 degree rotation around Z
        matrix = calculate_rotation_matrix(0.0, 0.0, 90.0)
        offset = (5.0, 5.0, 5.0)
        result = transform_point(point, matrix, offset)
        np.testing.assert_array_almost_equal(result, (5.0, 6.0, 5.0))


class TestEdgeType:
    """Test EdgeType enum."""

    def test_edge_type_values(self):
        """Test that EdgeType has expected values."""
        assert EdgeType.LENGTH_WISE.value == "length_wise"
        assert EdgeType.WIDTH_WISE.value == "width_wise"
        assert EdgeType.HEIGHT_WISE.value == "height_wise"

    def test_edge_type_members(self):
        """Test that all expected edge types exist."""
        assert hasattr(EdgeType, "LENGTH_WISE")
        assert hasattr(EdgeType, "WIDTH_WISE")
        assert hasattr(EdgeType, "HEIGHT_WISE")
