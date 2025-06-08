"""Tests for geometry calculation methods."""

import numpy as np
from nichiyou_daiku.core.geometry import (
    calculate_distance,
    calculate_angle_between_vectors,
    calculate_point_to_line_distance,
    check_line_intersection,
    calculate_angle_between_faces,
    calculate_dihedral_angle,
    transform_to_world_coordinates,
    transform_to_local_coordinates,
    project_point_onto_plane,
)
from nichiyou_daiku.core.lumber import Face, LumberPiece, LumberType


class TestDistanceCalculations:
    """Test distance calculation functions."""

    def test_calculate_distance_same_point(self):
        """Test distance between same point is zero."""
        point = (1.0, 2.0, 3.0)
        assert calculate_distance(point, point) == 0.0

    def test_calculate_distance_unit_distance(self):
        """Test distance calculation for unit distances."""
        p1 = (0.0, 0.0, 0.0)
        p2 = (1.0, 0.0, 0.0)
        assert calculate_distance(p1, p2) == 1.0

        p3 = (0.0, 1.0, 0.0)
        assert calculate_distance(p1, p3) == 1.0

        p4 = (0.0, 0.0, 1.0)
        assert calculate_distance(p1, p4) == 1.0

    def test_calculate_distance_3d(self):
        """Test 3D distance calculation."""
        p1 = (1.0, 2.0, 3.0)
        p2 = (4.0, 6.0, 8.0)
        # sqrt((4-1)^2 + (6-2)^2 + (8-3)^2) = sqrt(9 + 16 + 25) = sqrt(50)
        expected = np.sqrt(50)
        assert abs(calculate_distance(p1, p2) - expected) < 1e-10

    def test_point_to_line_distance(self):
        """Test distance from point to line."""
        # Line along X-axis through origin
        line_point = (0.0, 0.0, 0.0)
        line_direction = (1.0, 0.0, 0.0)

        # Point directly above line
        point = (5.0, 3.0, 0.0)
        distance = calculate_point_to_line_distance(point, line_point, line_direction)
        assert abs(distance - 3.0) < 1e-10

        # Point at angle
        point2 = (0.0, 3.0, 4.0)
        distance2 = calculate_point_to_line_distance(point2, line_point, line_direction)
        assert abs(distance2 - 5.0) < 1e-10  # 3-4-5 triangle


class TestAngleCalculations:
    """Test angle calculation functions."""

    def test_angle_between_parallel_vectors(self):
        """Test angle between parallel vectors is 0."""
        v1 = (1.0, 0.0, 0.0)
        v2 = (2.0, 0.0, 0.0)
        angle = calculate_angle_between_vectors(v1, v2)
        assert abs(angle) < 1e-10

    def test_angle_between_perpendicular_vectors(self):
        """Test angle between perpendicular vectors is 90 degrees."""
        v1 = (1.0, 0.0, 0.0)
        v2 = (0.0, 1.0, 0.0)
        angle = calculate_angle_between_vectors(v1, v2)
        assert abs(angle - 90.0) < 1e-10

    def test_angle_between_opposite_vectors(self):
        """Test angle between opposite vectors is 180 degrees."""
        v1 = (1.0, 0.0, 0.0)
        v2 = (-1.0, 0.0, 0.0)
        angle = calculate_angle_between_vectors(v1, v2)
        assert abs(angle - 180.0) < 1e-10

    def test_angle_between_45_degree_vectors(self):
        """Test angle calculation for 45 degree angle."""
        v1 = (1.0, 0.0, 0.0)
        v2 = (1.0, 1.0, 0.0)
        angle = calculate_angle_between_vectors(v1, v2)
        assert abs(angle - 45.0) < 1e-10

    def test_angle_between_faces(self):
        """Test angle calculation between lumber faces."""
        # Create two lumber pieces
        piece1 = LumberPiece("p1", LumberType.LUMBER_2X4, 1000)
        piece2 = LumberPiece("p2", LumberType.LUMBER_2X4, 1000)

        # Angle between same faces should be 0
        angle = calculate_angle_between_faces(
            piece1,
            Face.TOP,
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            piece2,
            Face.TOP,
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
        )
        assert abs(angle) < 1e-10

        # Angle between perpendicular faces should be 90
        angle2 = calculate_angle_between_faces(
            piece1,
            Face.TOP,
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            piece2,
            Face.FRONT,
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
        )
        assert abs(angle2 - 90.0) < 1e-10

    def test_dihedral_angle(self):
        """Test dihedral angle calculation."""
        # Two perpendicular planes
        normal1 = (1.0, 0.0, 0.0)
        normal2 = (0.0, 1.0, 0.0)
        angle = calculate_dihedral_angle(normal1, normal2)
        assert abs(angle - 90.0) < 1e-10

        # Two parallel planes
        normal3 = (0.0, 0.0, 1.0)
        normal4 = (0.0, 0.0, 1.0)
        angle2 = calculate_dihedral_angle(normal3, normal4)
        assert abs(angle2) < 1e-10


class TestIntersections:
    """Test intersection detection functions."""

    def test_line_intersection_2d_cross(self):
        """Test intersection of two lines that cross."""
        # Line 1: from (-1, 0, 0) to (1, 0, 0)
        p1 = (-1.0, 0.0, 0.0)
        p2 = (1.0, 0.0, 0.0)

        # Line 2: from (0, -1, 0) to (0, 1, 0)
        p3 = (0.0, -1.0, 0.0)
        p4 = (0.0, 1.0, 0.0)

        intersects, point = check_line_intersection(p1, p2, p3, p4)
        assert intersects
        assert point is not None
        assert abs(point[0]) < 1e-10
        assert abs(point[1]) < 1e-10
        assert abs(point[2]) < 1e-10

    def test_line_intersection_parallel(self):
        """Test parallel lines don't intersect."""
        # Line 1: along X axis at y=0
        p1 = (0.0, 0.0, 0.0)
        p2 = (1.0, 0.0, 0.0)

        # Line 2: along X axis at y=1
        p3 = (0.0, 1.0, 0.0)
        p4 = (1.0, 1.0, 0.0)

        intersects, point = check_line_intersection(p1, p2, p3, p4)
        assert not intersects
        assert point is None

    def test_line_intersection_skew(self):
        """Test skew lines in 3D don't intersect."""
        # Line 1: along X axis at z=0
        p1 = (0.0, 0.0, 0.0)
        p2 = (1.0, 0.0, 0.0)

        # Line 2: along Y axis at z=1
        p3 = (0.0, 0.0, 1.0)
        p4 = (0.0, 1.0, 1.0)

        intersects, point = check_line_intersection(p1, p2, p3, p4, tolerance=0.1)
        assert not intersects


class TestCoordinateTransformations:
    """Test coordinate transformation functions."""

    def test_transform_to_world_identity(self):
        """Test world transform with identity matrix."""
        local_point = (1.0, 2.0, 3.0)
        rotation = (0.0, 0.0, 0.0)  # No rotation
        position = (0.0, 0.0, 0.0)

        world_point = transform_to_world_coordinates(local_point, position, rotation)
        assert world_point == local_point

    def test_transform_to_world_translation(self):
        """Test world transform with translation only."""
        local_point = (1.0, 2.0, 3.0)
        rotation = (0.0, 0.0, 0.0)  # No rotation
        position = (10.0, 20.0, 30.0)

        world_point = transform_to_world_coordinates(local_point, position, rotation)
        assert world_point == (11.0, 22.0, 33.0)

    def test_transform_to_world_rotation(self):
        """Test world transform with 90 degree rotation."""
        local_point = (1.0, 0.0, 0.0)
        rotation = (0.0, 0.0, 90.0)  # 90 deg around Z
        position = (0.0, 0.0, 0.0)

        world_point = transform_to_world_coordinates(local_point, position, rotation)
        assert abs(world_point[0]) < 1e-10
        assert abs(world_point[1] - 1.0) < 1e-10
        assert abs(world_point[2]) < 1e-10

    def test_transform_to_local_inverse(self):
        """Test local transform is inverse of world transform."""
        local_point = (1.0, 2.0, 3.0)
        rotation = (30.0, 45.0, 60.0)
        position = (10.0, 20.0, 30.0)

        # Transform to world then back to local
        world_point = transform_to_world_coordinates(local_point, position, rotation)
        back_to_local = transform_to_local_coordinates(world_point, position, rotation)

        # Should get back original point
        assert abs(back_to_local[0] - local_point[0]) < 1e-10
        assert abs(back_to_local[1] - local_point[1]) < 1e-10
        assert abs(back_to_local[2] - local_point[2]) < 1e-10


class TestProjections:
    """Test projection functions."""

    def test_project_point_onto_xy_plane(self):
        """Test projecting point onto XY plane."""
        point = (1.0, 2.0, 3.0)
        plane_normal = (0.0, 0.0, 1.0)
        plane_point = (0.0, 0.0, 0.0)

        projected = project_point_onto_plane(point, plane_normal, plane_point)
        assert projected == (1.0, 2.0, 0.0)

    def test_project_point_onto_tilted_plane(self):
        """Test projecting onto a tilted plane."""
        point = (2.0, 0.0, 2.0)
        # 45 degree tilted plane with normal (1, 0, 1) normalized
        plane_normal = (1.0 / np.sqrt(2), 0.0, 1.0 / np.sqrt(2))
        plane_point = (0.0, 0.0, 0.0)

        projected = project_point_onto_plane(point, plane_normal, plane_point)
        # Point should be on the plane
        to_projected = (
            projected[0] - plane_point[0],
            projected[1] - plane_point[1],
            projected[2] - plane_point[2],
        )
        dot_product = sum(t * n for t, n in zip(to_projected, plane_normal))
        assert abs(dot_product) < 1e-10

    def test_project_point_with_zero_normal(self):
        """Test projecting with zero normal vector returns original point."""
        point = (1.0, 2.0, 3.0)
        plane_normal = (0.0, 0.0, 0.0)  # Zero normal
        plane_point = (0.0, 0.0, 0.0)

        projected = project_point_onto_plane(point, plane_normal, plane_point)
        assert projected == point


class TestAdditionalGeometryFunctions:
    """Test additional geometry functions for complete coverage."""

    def test_check_plane_intersection_perpendicular(self):
        """Test line-plane intersection when line is perpendicular to plane."""
        from nichiyou_daiku.core.geometry import check_plane_intersection

        # Line along Z axis
        line_point = (0.0, 0.0, 0.0)
        line_direction = (0.0, 0.0, 1.0)

        # XY plane at z=5
        plane_point = (0.0, 0.0, 5.0)
        plane_normal = (0.0, 0.0, 1.0)

        intersects, point = check_plane_intersection(
            line_point, line_direction, plane_point, plane_normal
        )
        assert intersects
        assert point == (0.0, 0.0, 5.0)

    def test_check_plane_intersection_parallel(self):
        """Test line-plane intersection when line is parallel to plane."""
        from nichiyou_daiku.core.geometry import check_plane_intersection

        # Line along X axis
        line_point = (0.0, 0.0, 0.0)
        line_direction = (1.0, 0.0, 0.0)

        # XY plane at z=5
        plane_point = (0.0, 0.0, 5.0)
        plane_normal = (0.0, 0.0, 1.0)

        intersects, point = check_plane_intersection(
            line_point, line_direction, plane_point, plane_normal
        )
        assert not intersects
        assert point is None

    def test_check_plane_intersection_angled(self):
        """Test line-plane intersection at an angle."""
        from nichiyou_daiku.core.geometry import check_plane_intersection

        # Line from origin at 45 degrees to XY plane
        line_point = (0.0, 0.0, 0.0)
        line_direction = (1.0, 0.0, 1.0)

        # XY plane at z=5
        plane_point = (0.0, 0.0, 5.0)
        plane_normal = (0.0, 0.0, 1.0)

        intersects, point = check_plane_intersection(
            line_point, line_direction, plane_point, plane_normal
        )
        assert intersects
        assert abs(point[0] - 5.0) < 1e-10
        assert abs(point[1]) < 1e-10
        assert abs(point[2] - 5.0) < 1e-10

    def test_calculate_closest_points_between_lines_skew(self):
        """Test closest points between skew lines."""
        from nichiyou_daiku.core.geometry import calculate_closest_points_between_lines

        # Line 1: along X axis at origin
        line1_point = (0.0, 0.0, 0.0)
        line1_dir = (1.0, 0.0, 0.0)

        # Line 2: along Y axis at x=2, z=1
        line2_point = (2.0, 0.0, 1.0)
        line2_dir = (0.0, 1.0, 0.0)

        point1, point2 = calculate_closest_points_between_lines(
            line1_point, line1_dir, line2_point, line2_dir
        )

        # Closest point on line1 should be at (2, 0, 0)
        assert abs(point1[0] - 2.0) < 1e-10
        assert abs(point1[1]) < 1e-10
        assert abs(point1[2]) < 1e-10

        # Closest point on line2 should be at (2, 0, 1)
        assert abs(point2[0] - 2.0) < 1e-10
        assert abs(point2[1]) < 1e-10
        assert abs(point2[2] - 1.0) < 1e-10

    def test_calculate_closest_points_between_lines_parallel(self):
        """Test closest points between parallel lines."""
        from nichiyou_daiku.core.geometry import calculate_closest_points_between_lines

        # Line 1: along X axis at y=0
        line1_point = (0.0, 0.0, 0.0)
        line1_dir = (1.0, 0.0, 0.0)

        # Line 2: along X axis at y=1
        line2_point = (0.0, 1.0, 0.0)
        line2_dir = (1.0, 0.0, 0.0)

        point1, point2 = calculate_closest_points_between_lines(
            line1_point, line1_dir, line2_point, line2_dir
        )

        # Should return the original points since lines are parallel
        assert point1 == (0.0, 0.0, 0.0)
        assert point2 == (0.0, 1.0, 0.0)

    def test_calculate_closest_points_between_lines_intersecting(self):
        """Test closest points between intersecting lines."""
        from nichiyou_daiku.core.geometry import calculate_closest_points_between_lines

        # Line 1: from (-1, 0, 0) to (1, 0, 0)
        line1_point = (0.0, 0.0, 0.0)
        line1_dir = (1.0, 0.0, 0.0)

        # Line 2: from (0, -1, 0) to (0, 1, 0)
        line2_point = (0.0, 0.0, 0.0)
        line2_dir = (0.0, 1.0, 0.0)

        point1, point2 = calculate_closest_points_between_lines(
            line1_point, line1_dir, line2_point, line2_dir
        )

        # Should both be at the intersection point
        assert abs(point1[0]) < 1e-10
        assert abs(point1[1]) < 1e-10
        assert abs(point1[2]) < 1e-10

        assert abs(point2[0]) < 1e-10
        assert abs(point2[1]) < 1e-10
        assert abs(point2[2]) < 1e-10
