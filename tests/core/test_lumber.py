"""Tests for lumber data models."""

import pytest
from nichiyou_daiku.core.lumber import (
    LumberType,
    LumberSpec,
    LumberPiece,
    Face,
)


class TestLumberType:
    """Test LumberType enum."""

    def test_lumber_type_values(self):
        """Test that lumber types have correct values."""
        assert LumberType.LUMBER_1X.value == "1x"
        assert LumberType.LUMBER_2X.value == "2x"

    def test_lumber_type_members(self):
        """Test that all expected lumber types exist."""
        assert hasattr(LumberType, "LUMBER_1X")
        assert hasattr(LumberType, "LUMBER_2X")


class TestLumberSpec:
    """Test LumberSpec dataclass."""

    def test_lumber_spec_creation(self):
        """Test creating a lumber specification."""
        spec = LumberSpec(width=19, height=38)
        assert spec.width == 19
        assert spec.height == 38

    def test_lumber_spec_immutable(self):
        """Test that lumber spec is immutable."""
        spec = LumberSpec(width=19, height=38)
        with pytest.raises(AttributeError):
            spec.width = 25


class TestLumberPiece:
    """Test LumberPiece class."""

    def test_lumber_piece_creation(self):
        """Test creating a lumber piece with default position."""
        piece = LumberPiece(id="test1", lumber_type=LumberType.LUMBER_2X, length=1000)
        assert piece.id == "test1"
        assert piece.lumber_type == LumberType.LUMBER_2X
        assert piece.length == 1000
        assert piece.position == (0.0, 0.0, 0.0)
        assert piece.rotation == (0.0, 0.0, 0.0)

    def test_lumber_piece_with_position(self):
        """Test creating a lumber piece with custom position."""
        piece = LumberPiece(
            id="test2",
            lumber_type=LumberType.LUMBER_1X,
            length=500,
            position=(100, 200, 300),
        )
        assert piece.position == (100, 200, 300)

    def test_get_dimensions_2x_lumber(self):
        """Test dimension calculation for 2x lumber."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_2X, length=1000)
        width, height, length = piece.get_dimensions()
        assert width == 38  # 2x material is 38mm wide
        assert height == 89  # 2x material is 89mm tall
        assert length == 1000

    def test_get_dimensions_1x_lumber(self):
        """Test dimension calculation for 1x lumber."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_1X, length=500)
        width, height, length = piece.get_dimensions()
        assert width == 19  # 1x material is 19mm wide
        assert height == 38  # 1x material is 38mm tall
        assert length == 500

    def test_get_face_center_3d_top_face(self):
        """Test getting 3D center of top face."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_2X, length=1000)
        center = piece.get_face_center_3d(Face.TOP)
        assert center == (0, 0, 44.5)  # Half of 89mm height

    def test_get_face_center_3d_bottom_face(self):
        """Test getting 3D center of bottom face."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_2X, length=1000)
        center = piece.get_face_center_3d(Face.BOTTOM)
        assert center == (0, 0, -44.5)  # Negative half of 89mm height

    def test_get_face_center_3d_front_face(self):
        """Test getting 3D center of front face."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_2X, length=1000)
        center = piece.get_face_center_3d(Face.FRONT)
        assert center == (500, 0, 0)  # Half of 1000mm length

    def test_get_face_center_3d_back_face(self):
        """Test getting 3D center of back face."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_2X, length=1000)
        center = piece.get_face_center_3d(Face.BACK)
        assert center == (-500, 0, 0)  # Negative half of 1000mm length

    def test_get_face_center_3d_right_face(self):
        """Test getting 3D center of right face."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_2X, length=1000)
        center = piece.get_face_center_3d(Face.RIGHT)
        assert center == (0, 19, 0)  # Half of 38mm width

    def test_get_face_center_3d_left_face(self):
        """Test getting 3D center of left face."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_2X, length=1000)
        center = piece.get_face_center_3d(Face.LEFT)
        assert center == (0, -19, 0)  # Negative half of 38mm width

    def test_get_face_center_3d_with_position_offset(self):
        """Test face center calculation with position offset."""
        piece = LumberPiece(
            id="test",
            lumber_type=LumberType.LUMBER_1X,
            length=500,
            position=(100, 200, 300),
        )
        center = piece.get_face_center_3d(Face.TOP)
        assert center == (100, 200, 319)  # 300 + 38/2 (half height of 1x lumber)

    def test_lumber_piece_immutable_attributes(self):
        """Test that lumber piece core attributes are immutable."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_2X, length=1000)
        with pytest.raises(AttributeError):
            piece.id = "new_id"
        with pytest.raises(AttributeError):
            piece.lumber_type = LumberType.LUMBER_1X
        with pytest.raises(AttributeError):
            piece.length = 2000


class TestFace:
    """Test Face enum."""

    def test_face_enum_values(self):
        """Test that Face enum has all expected values."""
        assert Face.TOP.value == "top"
        assert Face.BOTTOM.value == "bottom"
        assert Face.LEFT.value == "left"
        assert Face.RIGHT.value == "right"
        assert Face.FRONT.value == "front"
        assert Face.BACK.value == "back"

    def test_face_enum_members(self):
        """Test that all expected faces exist."""
        expected_faces = ["TOP", "BOTTOM", "LEFT", "RIGHT", "FRONT", "BACK"]
        for face in expected_faces:
            assert hasattr(Face, face)
