"""Tests for geometry module."""

import pytest
from pydantic import ValidationError

from nichiyou_daiku.core.geometry import (
    Shape2D,
    Shape3D,
    Point3D,
    Vector3D,
)


class TestMillimeters:
    """Test Millimeters type validation."""

    # Basic validation is covered in doctests

    def test_should_reject_negative_values(self):
        """Millimeters should reject negative values but allow zero."""
        # Valid shapes with positive dimensions
        Shape2D(width=10, height=20)  # This should work

        # Zero should now work
        shape_with_zero = Shape2D(width=0, height=20)
        assert shape_with_zero.width == 0

        # Negative should fail
        with pytest.raises(ValidationError):
            Shape2D(width=-10, height=20)


class TestShape2D:
    """Test Shape2D model."""

    # Basic creation is covered in doctests

    def test_should_validate_non_negative_dimensions(self):
        """Should validate that dimensions are non-negative."""
        # Valid shape
        shape = Shape2D(width=10.5, height=20.3)
        assert shape.width == 10.5
        assert shape.height == 20.3

        # Zero width should work
        shape_zero = Shape2D(width=0, height=20)
        assert shape_zero.width == 0

        # Negative height should fail
        with pytest.raises(ValidationError) as exc_info:
            Shape2D(width=10, height=-5)
        assert "greater than or equal to 0" in str(exc_info.value)

    # Immutability is covered in doctests


class TestShape3D:
    """Test Shape3D model."""

    # Basic creation is covered in doctests

    def test_should_validate_all_dimensions_non_negative(self):
        """Should validate that all dimensions are non-negative."""
        # Valid shape
        shape = Shape3D(width=10, height=20, length=30)
        assert shape.width == 10
        assert shape.height == 20
        assert shape.length == 30

        # Zero dimensions should work
        shape_zero = Shape3D(width=10, height=0, length=30)
        assert shape_zero.height == 0

        # Negative width should fail
        with pytest.raises(ValidationError):
            Shape3D(width=-10, height=20, length=30)

        # Negative length should fail
        with pytest.raises(ValidationError):
            Shape3D(width=10, height=20, length=-30)


class TestPoint3D:
    """Test Point3D model."""

    # Basic creation is covered in doctests

    def test_should_accept_zero_and_negative_coordinates(self):
        """Point3D should accept zero and negative coordinates."""
        # Zero coordinates
        point1 = Point3D(x=0.0, y=0.0, z=0.0)
        assert point1.x == 0.0
        assert point1.y == 0.0
        assert point1.z == 0.0

        # Negative coordinates
        point2 = Point3D(x=-10.0, y=-20.0, z=-30.0)
        assert point2.x == -10.0
        assert point2.y == -20.0
        assert point2.z == -30.0

        # Mixed coordinates
        point3 = Point3D(x=10.0, y=-5.0, z=0.0)
        assert point3.x == 10.0
        assert point3.y == -5.0
        assert point3.z == 0.0


class TestVector3D:
    """Test Vector3D model."""

    # Basic creation is covered in doctests

    def test_should_accept_negative_and_zero_values(self):
        """Vector3D should accept negative and zero values (unlike Point3D)."""
        # Vectors can have negative components
        vector = Vector3D(x=-10.5, y=0, z=5.5)
        assert vector.x == -10.5
        assert vector.y == 0
        assert vector.z == 5.5

        # Unit vectors
        unit_x = Vector3D(x=1, y=0, z=0)
        unit_y = Vector3D(x=0, y=1, z=0)
        unit_z = Vector3D(x=0, y=0, z=1)

        assert unit_x.x == 1 and unit_x.y == 0 and unit_x.z == 0
        assert unit_y.x == 0 and unit_y.y == 1 and unit_y.z == 0
        assert unit_z.x == 0 and unit_z.y == 0 and unit_z.z == 1

    def test_should_handle_normalized_vectors(self):
        """Should handle normalized direction vectors."""
        import math

        # 45 degree angle in XY plane
        vector = Vector3D(x=0.707, y=0.707, z=0)
        magnitude = math.sqrt(vector.x**2 + vector.y**2 + vector.z**2)
        assert abs(magnitude - 1.0) < 0.01  # Approximately unit length


class TestEdgeValidation:
    def test_same_faces_are_rejected(self):
        from nichiyou_daiku.core.geometry import Edge

        with pytest.raises(ValueError, match="must be different"):
            Edge(lhs="top", rhs="top")

    def test_opposite_faces_are_rejected(self):
        from nichiyou_daiku.core.geometry import Edge

        with pytest.raises(ValueError, match="not adjacent"):
            Edge(lhs="top", rhs="down")


class TestOffsetSerialization:
    def test_from_min_survives_json_round_trip(self):
        from nichiyou_daiku.core.anchor import Anchor
        from nichiyou_daiku.core.geometry import FromMin

        anchor = Anchor(
            contact_face="front", edge_shared_face="left", offset=FromMin(value=100)
        )
        restored = Anchor.model_validate_json(anchor.model_dump_json())
        assert restored == anchor

    def test_from_max_survives_json_round_trip(self):
        from nichiyou_daiku.core.anchor import Anchor
        from nichiyou_daiku.core.geometry import FromMax

        anchor = Anchor(
            contact_face="front", edge_shared_face="left", offset=FromMax(value=100)
        )
        restored = Anchor.model_validate_json(anchor.model_dump_json())
        assert restored == anchor


class TestOrientation3DFromEuler:
    @pytest.mark.parametrize(
        "angles", [(0, 0, 90), (90, 45, 0), (30, 60, 120), (-45, 10, 200)]
    )
    def test_up_is_rotated_y_axis_and_orthogonal(self, angles):
        import math

        from nichiyou_daiku.core.geometry import Orientation3D

        rx, ry, rz = (math.radians(a) for a in angles)

        def rotate(v):
            x, y, z = v
            # R = Rx @ Ry @ Rz, matching the direction formula
            x, y = (
                x * math.cos(rz) - y * math.sin(rz),
                x * math.sin(rz) + y * math.cos(rz),
            )
            x, z = (
                x * math.cos(ry) + z * math.sin(ry),
                -x * math.sin(ry) + z * math.cos(ry),
            )
            y, z = (
                y * math.cos(rx) - z * math.sin(rx),
                y * math.sin(rx) + z * math.cos(rx),
            )
            return (x, y, z)

        orientation = Orientation3D.of(*angles)
        up = (orientation.up.x, orientation.up.y, orientation.up.z)
        direction = (
            orientation.direction.x,
            orientation.direction.y,
            orientation.direction.z,
        )
        assert direction == pytest.approx(rotate((0, 0, 1)), abs=1e-9)
        assert up == pytest.approx(rotate((0, 1, 0)), abs=1e-9)


class TestOrientation3DOrthogonalization:
    def test_up_is_orthogonal_to_non_unit_direction(self):
        from nichiyou_daiku.core.geometry import Orientation3D

        orientation = Orientation3D(
            direction=Vector3D(x=0.0, y=0.0, z=2.0), up=Vector3D(x=0.0, y=1.0, z=1.0)
        )
        d, u = orientation.direction, orientation.up
        assert d.x * u.x + d.y * u.y + d.z * u.z == pytest.approx(0.0, abs=1e-9)
