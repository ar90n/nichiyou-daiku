"""Tests for advanced geometry calculations."""

import pytest
import numpy as np
from nichiyou_daiku.core.geometry import (
    calculate_distance,
    calculate_point_to_line_distance,
    calculate_angle_between_vectors,
    calculate_angle_between_faces,
    calculate_dihedral_angle,
    check_line_intersection,
    check_plane_intersection,
    transform_to_world_coordinates,
    transform_to_local_coordinates,
    project_point_onto_plane,
    calculate_closest_points_between_lines,
)
from nichiyou_daiku.core.lumber import Face, LumberPiece, LumberType


class TestDistanceCalculations:
    """Test distance calculation methods."""

    def test_calculate_distance_3d_points(self):
        """Test calculating distance between two 3D points."""
        point1 = (0.0, 0.0, 0.0)
        point2 = (3.0, 4.0, 0.0)
        distance = calculate_distance(point1, point2)
        assert abs(distance - 5.0) < 1e-10

    def test_calculate_distance_same_point(self):
        """Test distance when points are the same."""
        point = (1.0, 2.0, 3.0)
        distance = calculate_distance(point, point)
        assert distance == 0.0

    def test_calculate_distance_negative_coordinates(self):
        """Test distance with negative coordinates."""
        point1 = (-1.0, -2.0, -3.0)
        point2 = (1.0, 2.0, 3.0)
        distance = calculate_distance(point1, point2)
        expected = (2**2 + 4**2 + 6**2) ** 0.5
        assert abs(distance - expected) < 1e-10

    def test_calculate_point_to_line_distance(self):
        """Test calculating distance from point to line."""
        # Line along X-axis passing through origin
        line_point = (0.0, 0.0, 0.0)
        line_direction = (1.0, 0.0, 0.0)
        
        # Point above the line
        point = (5.0, 3.0, 4.0)
        distance = calculate_point_to_line_distance(point, line_point, line_direction)
        assert abs(distance - 5.0) < 1e-10  # Distance is sqrt(3^2 + 4^2) = 5

    def test_calculate_point_to_line_distance_on_line(self):
        """Test distance when point is on the line."""
        line_point = (0.0, 0.0, 0.0)
        line_direction = (1.0, 1.0, 1.0)
        point = (2.0, 2.0, 2.0)  # Point on the line
        distance = calculate_point_to_line_distance(point, line_point, line_direction)
        assert abs(distance) < 1e-10


class TestAngleCalculations:
    """Test angle calculation methods."""

    def test_calculate_angle_between_vectors(self):
        """Test calculating angle between two vectors."""
        vec1 = (1.0, 0.0, 0.0)
        vec2 = (0.0, 1.0, 0.0)
        angle = calculate_angle_between_vectors(vec1, vec2)
        assert abs(angle - 90.0) < 1e-10

    def test_calculate_angle_parallel_vectors(self):
        """Test angle between parallel vectors."""
        vec1 = (1.0, 0.0, 0.0)
        vec2 = (2.0, 0.0, 0.0)
        angle = calculate_angle_between_vectors(vec1, vec2)
        assert abs(angle) < 1e-10

    def test_calculate_angle_opposite_vectors(self):
        """Test angle between opposite vectors."""
        vec1 = (1.0, 0.0, 0.0)
        vec2 = (-1.0, 0.0, 0.0)
        angle = calculate_angle_between_vectors(vec1, vec2)
        assert abs(angle - 180.0) < 1e-10

    def test_calculate_angle_between_faces(self):
        """Test calculating angle between two faces of lumber pieces."""
        piece1 = LumberPiece("piece1", LumberType.LUMBER_2X4, 1000.0)
        piece2 = LumberPiece("piece2", LumberType.LUMBER_2X4, 1000.0)
        
        # Both pieces at origin with no rotation
        pos1 = (0.0, 0.0, 0.0)
        rot1 = (0.0, 0.0, 0.0)
        pos2 = (0.0, 0.0, 0.0)
        rot2 = (0.0, 0.0, 0.0)
        
        # TOP faces are parallel
        angle = calculate_angle_between_faces(
            piece1, Face.TOP, pos1, rot1,
            piece2, Face.TOP, pos2, rot2
        )
        assert abs(angle) < 1e-10
        
        # TOP and FRONT faces are perpendicular
        angle = calculate_angle_between_faces(
            piece1, Face.TOP, pos1, rot1,
            piece2, Face.FRONT, pos2, rot2
        )
        assert abs(angle - 90.0) < 1e-10

    def test_calculate_dihedral_angle(self):
        """Test calculating dihedral angle between two planes."""
        # Two perpendicular planes
        normal1 = (0.0, 0.0, 1.0)  # XY plane
        normal2 = (1.0, 0.0, 0.0)  # YZ plane
        angle = calculate_dihedral_angle(normal1, normal2)
        assert abs(angle - 90.0) < 1e-10


class TestIntersectionDetection:
    """Test intersection detection methods."""

    def test_check_line_intersection_2d(self):
        """Test checking if two lines intersect in 2D (projected)."""
        # Two intersecting lines
        line1_start = (0.0, 0.0, 0.0)
        line1_end = (10.0, 10.0, 0.0)
        line2_start = (0.0, 10.0, 0.0)
        line2_end = (10.0, 0.0, 0.0)
        
        intersects, point = check_line_intersection(
            line1_start, line1_end, line2_start, line2_end
        )
        assert intersects is True
        assert point is not None
        assert abs(point[0] - 5.0) < 1e-10
        assert abs(point[1] - 5.0) < 1e-10

    def test_check_line_intersection_parallel(self):
        """Test parallel lines don't intersect."""
        line1_start = (0.0, 0.0, 0.0)
        line1_end = (10.0, 0.0, 0.0)
        line2_start = (0.0, 1.0, 0.0)
        line2_end = (10.0, 1.0, 0.0)
        
        intersects, point = check_line_intersection(
            line1_start, line1_end, line2_start, line2_end
        )
        assert intersects is False
        assert point is None

    def test_check_plane_intersection(self):
        """Test checking if a line intersects a plane."""
        # Plane at z=5, normal pointing up
        plane_point = (0.0, 0.0, 5.0)
        plane_normal = (0.0, 0.0, 1.0)
        
        # Line going through the plane
        line_point = (0.0, 0.0, 0.0)
        line_direction = (0.0, 0.0, 1.0)
        
        intersects, point = check_plane_intersection(
            line_point, line_direction, plane_point, plane_normal
        )
        assert intersects is True
        assert point is not None
        assert abs(point[2] - 5.0) < 1e-10

    def test_check_plane_intersection_parallel(self):
        """Test line parallel to plane doesn't intersect."""
        plane_point = (0.0, 0.0, 5.0)
        plane_normal = (0.0, 0.0, 1.0)
        
        # Line parallel to plane
        line_point = (0.0, 0.0, 0.0)
        line_direction = (1.0, 0.0, 0.0)
        
        intersects, point = check_plane_intersection(
            line_point, line_direction, plane_point, plane_normal
        )
        assert intersects is False
        assert point is None


class TestCoordinateTransformations:
    """Test coordinate system transformation methods."""

    def test_transform_to_world_coordinates(self):
        """Test transforming from local to world coordinates."""
        # Local point at (1, 0, 0)
        local_point = (1.0, 0.0, 0.0)
        
        # Object at world position (10, 20, 30) with 90° Z rotation
        position = (10.0, 20.0, 30.0)
        rotation = (0.0, 0.0, 90.0)
        
        world_point = transform_to_world_coordinates(local_point, position, rotation)
        
        # After 90° Z rotation, (1,0,0) becomes (0,1,0), then offset
        expected = (10.0, 21.0, 30.0)
        np.testing.assert_array_almost_equal(world_point, expected)

    def test_transform_to_local_coordinates(self):
        """Test transforming from world to local coordinates."""
        # World point at (10, 21, 30)
        world_point = (10.0, 21.0, 30.0)
        
        # Object at world position (10, 20, 30) with 90° Z rotation
        position = (10.0, 20.0, 30.0)
        rotation = (0.0, 0.0, 90.0)
        
        local_point = transform_to_local_coordinates(world_point, position, rotation)
        
        # Should get back (1, 0, 0) in local coordinates
        expected = (1.0, 0.0, 0.0)
        np.testing.assert_array_almost_equal(local_point, expected)

    def test_coordinate_transform_round_trip(self):
        """Test that transforming to world and back gives original point."""
        local_point = (3.0, 4.0, 5.0)
        position = (100.0, 200.0, 300.0)
        rotation = (45.0, 30.0, 60.0)
        
        world_point = transform_to_world_coordinates(local_point, position, rotation)
        back_to_local = transform_to_local_coordinates(world_point, position, rotation)
        
        np.testing.assert_array_almost_equal(local_point, back_to_local)


class TestProjectionCalculations:
    """Test projection calculation methods."""

    def test_project_point_onto_plane(self):
        """Test projecting a point onto a plane."""
        # XY plane at z=0
        plane_point = (0.0, 0.0, 0.0)
        plane_normal = (0.0, 0.0, 1.0)
        
        # Point above the plane
        point = (3.0, 4.0, 5.0)
        
        projected = project_point_onto_plane(point, plane_point, plane_normal)
        expected = (3.0, 4.0, 0.0)
        np.testing.assert_array_almost_equal(projected, expected)

    def test_project_point_already_on_plane(self):
        """Test projecting a point that's already on the plane."""
        plane_point = (0.0, 0.0, 0.0)
        plane_normal = (1.0, 1.0, 1.0)  # Not normalized, should be handled
        
        # Point on the plane
        point = (1.0, 1.0, -2.0)  # 1*1 + 1*1 + 1*(-2) = 0
        
        projected = project_point_onto_plane(point, plane_point, plane_normal)
        np.testing.assert_array_almost_equal(projected, point)


class TestLineCalculations:
    """Test line-related calculation methods."""

    def test_calculate_closest_points_between_lines(self):
        """Test finding closest points between two skew lines."""
        # Line 1: along X axis at origin
        line1_point = (0.0, 0.0, 0.0)
        line1_dir = (1.0, 0.0, 0.0)
        
        # Line 2: along Y axis at z=1
        line2_point = (0.0, 0.0, 1.0)
        line2_dir = (0.0, 1.0, 0.0)
        
        point1, point2 = calculate_closest_points_between_lines(
            line1_point, line1_dir, line2_point, line2_dir
        )
        
        # Closest points should be at origin and (0, 0, 1)
        np.testing.assert_array_almost_equal(point1, (0.0, 0.0, 0.0))
        np.testing.assert_array_almost_equal(point2, (0.0, 0.0, 1.0))

    def test_calculate_closest_points_parallel_lines(self):
        """Test closest points for parallel lines."""
        # Two parallel lines along X axis
        line1_point = (0.0, 0.0, 0.0)
        line1_dir = (1.0, 0.0, 0.0)
        
        line2_point = (0.0, 1.0, 0.0)
        line2_dir = (1.0, 0.0, 0.0)
        
        point1, point2 = calculate_closest_points_between_lines(
            line1_point, line1_dir, line2_point, line2_dir
        )
        
        # For parallel lines, any pair with same x coordinate works
        # Should return the input points as closest
        np.testing.assert_array_almost_equal(point1, line1_point)
        np.testing.assert_array_almost_equal(point2, line2_point)