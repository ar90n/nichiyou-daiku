"""Tests for Orientation3D class and related functions."""

import math
import pytest
from nichiyou_daiku.core.geometry import (
    Orientation3D, Vector3D, Face, Edge
)


class TestOrientation3D:
    """Test Orientation3D class."""

    def test_should_create_from_direction_and_up_vectors(self):
        """Should create orientation from direction and up vectors."""
        direction = Vector3D(x=0.0, y=0.0, z=1.0)
        up = Vector3D(x=0.0, y=1.0, z=0.0)
        
        orient = Orientation3D.of(direction, up)
        
        assert orient.direction.z == 1.0
        assert orient.up.y == 1.0

    def test_should_normalize_direction_vector(self):
        """Should normalize the direction vector."""
        direction = Vector3D(x=2.0, y=0.0, z=0.0)
        up = Vector3D(x=0.0, y=1.0, z=0.0)
        
        orient = Orientation3D.of(direction, up)
        
        assert orient.direction.x == 1.0
        assert orient.direction.y == 0.0
        assert orient.direction.z == 0.0

    def test_should_orthogonalize_up_vector(self):
        """Should orthogonalize the up vector to be perpendicular to direction."""
        direction = Vector3D(x=1.0, y=0.0, z=0.0)
        up = Vector3D(x=0.5, y=1.0, z=0.0)  # Not perpendicular
        
        orient = Orientation3D.of(direction, up)
        
        # Up should be orthogonalized to (0, 1, 0)
        assert abs(orient.up.x) < 1e-6
        assert orient.up.y == 1.0
        assert orient.up.z == 0.0
        
        # Verify orthogonality
        dot = (orient.direction.x * orient.up.x + 
               orient.direction.y * orient.up.y + 
               orient.direction.z * orient.up.z)
        assert abs(dot) < 1e-6

    def test_should_reject_parallel_vectors(self):
        """Should raise error when up is parallel to direction."""
        direction = Vector3D(x=1.0, y=0.0, z=0.0)
        up = Vector3D(x=2.0, y=0.0, z=0.0)  # Parallel
        
        with pytest.raises(ValueError, match="parallel"):
            Orientation3D.of(direction, up)

    def test_should_create_from_face_and_edge(self):
        """Should create orientation from face and edge."""
        face = "top"
        edge = Edge(lhs="top", rhs="front")
        
        orient = Orientation3D.of(face, edge)
        
        # Direction should be face normal (top = +X)
        assert orient.direction.x == 1.0
        assert orient.direction.y == 0.0
        assert orient.direction.z == 0.0
        
        # Up should be edge direction (top x front = left = -Y)
        assert orient.up.x == 0.0
        assert orient.up.y == -1.0
        assert orient.up.z == 0.0

    def test_should_create_from_euler_angles(self):
        """Should create orientation from Euler angles."""
        # Identity rotation
        orient = Orientation3D.of(0.0, 0.0, 0.0)
        
        assert abs(orient.direction.x) < 1e-6
        assert abs(orient.direction.y) < 1e-6
        assert orient.direction.z == 1.0
        
        assert abs(orient.up.x) < 1e-6
        assert orient.up.y == 1.0
        assert abs(orient.up.z) < 1e-6

    def test_should_handle_90_degree_rotations(self):
        """Should correctly handle 90-degree rotations."""
        # 90 degrees around Y axis
        orient = Orientation3D.of(0.0, 90.0, 0.0)
        
        # Direction should point in +X
        assert abs(orient.direction.x - 1.0) < 1e-6
        assert abs(orient.direction.y) < 1e-6
        assert abs(orient.direction.z) < 1e-6
        
        # Up should still point in +Y
        assert abs(orient.up.x) < 1e-6
        assert abs(orient.up.y - 1.0) < 1e-6
        assert abs(orient.up.z) < 1e-6


# TestAsEulerAngles removed - as_euler_angles function doesn't exist
# class TestAsEulerAngles:
#     """Test as_euler_angles function."""
#     ... tests removed since as_euler_angles doesn't exist