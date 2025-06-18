"""Tests for lumber data models."""

import pytest
from nichiyou_daiku.core.lumber import (
    LumberType,
    LumberDimensions,
    LumberPiece,
    Face,
)


class TestLumberType:
    """Test LumberType enum."""

    def test_lumber_type_values(self):
        """Test that lumber types have correct values."""
        assert LumberType.LUMBER_1X4.value == "1x4"
        assert LumberType.LUMBER_1X8.value == "1x8"
        assert LumberType.LUMBER_1X16.value == "1x16"
        assert LumberType.LUMBER_2X4.value == "2x4"
        assert LumberType.LUMBER_2X8.value == "2x8"
        assert LumberType.LUMBER_2X16.value == "2x16"

    def test_lumber_type_members(self):
        """Test that all expected lumber types exist."""
        expected_types = [
            "LUMBER_1X4",
            "LUMBER_1X8",
            "LUMBER_1X16",
            "LUMBER_2X4",
            "LUMBER_2X8",
            "LUMBER_2X16",
        ]
        for lumber_type in expected_types:
            assert hasattr(LumberType, lumber_type)


class TestLumberSpec:
    """Test LumberSpec dataclass."""

    def test_lumber_spec_creation(self):
        """Test creating a lumber specification."""
        spec = LumberDimensions(width=19, height=89)
        assert spec.width == 19
        assert spec.height == 89

    def test_lumber_spec_immutable(self):
        """Test that lumber spec is immutable."""
        spec = LumberDimensions(width=19, height=89)
        with pytest.raises(AttributeError):
            spec.width = 25


class TestLumberPiece:
    """Test LumberPiece class."""

    def test_lumber_piece_creation(self):
        """Test creating a lumber piece."""
        piece = LumberPiece(id="test1", lumber_type=LumberType.LUMBER_2X4, length=1000)
        assert piece.id == "test1"
        assert piece.lumber_type == LumberType.LUMBER_2X4
        assert piece.length == 1000

    def test_get_dimensions_1x4_lumber(self):
        """Test dimension calculation for 1x4 lumber."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_1X4, length=1000)
        width, height, length = piece.get_dimensions()
        assert width == 19  # 1x material is 19mm thick
        assert height == 89  # 4" nominal is 89mm tall
        assert length == 1000

    def test_get_dimensions_1x8_lumber(self):
        """Test dimension calculation for 1x8 lumber."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_1X8, length=500)
        width, height, length = piece.get_dimensions()
        assert width == 19  # 1x material is 19mm thick
        assert height == 184  # 8" nominal is 184mm tall
        assert length == 500

    def test_get_dimensions_1x16_lumber(self):
        """Test dimension calculation for 1x16 lumber."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_1X16, length=2000)
        width, height, length = piece.get_dimensions()
        assert width == 19  # 1x material is 19mm thick
        assert height == 387  # 16" nominal is 387mm tall
        assert length == 2000

    def test_get_dimensions_2x4_lumber(self):
        """Test dimension calculation for 2x4 lumber."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_2X4, length=1000)
        width, height, length = piece.get_dimensions()
        assert width == 38  # 2x material is 38mm thick
        assert height == 89  # 4" nominal is 89mm tall
        assert length == 1000

    def test_get_dimensions_2x8_lumber(self):
        """Test dimension calculation for 2x8 lumber."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_2X8, length=1500)
        width, height, length = piece.get_dimensions()
        assert width == 38  # 2x material is 38mm thick
        assert height == 184  # 8" nominal is 184mm tall
        assert length == 1500

    def test_get_dimensions_2x16_lumber(self):
        """Test dimension calculation for 2x16 lumber."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_2X16, length=3000)
        width, height, length = piece.get_dimensions()
        assert width == 38  # 2x material is 38mm thick
        assert height == 387  # 16" nominal is 387mm tall
        assert length == 3000

    def test_get_face_center_local_top_face(self):
        """Test getting local center of top face."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_2X4, length=1000)
        center = piece.get_face_center_local(Face.TOP)
        assert center == (0, 0, 44.5)  # Half of 89mm height

    def test_get_face_center_local_bottom_face(self):
        """Test getting local center of bottom face."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_2X4, length=1000)
        center = piece.get_face_center_local(Face.BOTTOM)
        assert center == (0, 0, -44.5)  # Negative half of 89mm height

    def test_get_face_center_local_front_face(self):
        """Test getting local center of front face."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_2X4, length=1000)
        center = piece.get_face_center_local(Face.FRONT)
        assert center == (500, 0, 0)  # Half of 1000mm length

    def test_get_face_center_local_back_face(self):
        """Test getting local center of back face."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_2X4, length=1000)
        center = piece.get_face_center_local(Face.BACK)
        assert center == (-500, 0, 0)  # Negative half of 1000mm length

    def test_get_face_center_local_right_face(self):
        """Test getting local center of right face."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_2X4, length=1000)
        center = piece.get_face_center_local(Face.RIGHT)
        assert center == (0, 19, 0)  # Half of 38mm width

    def test_get_face_center_local_left_face(self):
        """Test getting local center of left face."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_2X4, length=1000)
        center = piece.get_face_center_local(Face.LEFT)
        assert center == (0, -19, 0)  # Negative half of 38mm width

    def test_get_face_center_local_different_sizes(self):
        """Test face centers for different lumber sizes."""
        # Test 1x8
        piece_1x8 = LumberPiece(
            id="test", lumber_type=LumberType.LUMBER_1X8, length=500
        )
        center = piece_1x8.get_face_center_local(Face.TOP)
        assert center == (0, 0, 92)  # Half of 184mm height

        # Test 2x16
        piece_2x16 = LumberPiece(
            id="test", lumber_type=LumberType.LUMBER_2X16, length=2000
        )
        center = piece_2x16.get_face_center_local(Face.TOP)
        assert center == (0, 0, 193.5)  # Half of 387mm height

    def test_lumber_piece_immutable_attributes(self):
        """Test that lumber piece core attributes are immutable."""
        piece = LumberPiece(id="test", lumber_type=LumberType.LUMBER_2X4, length=1000)
        with pytest.raises(AttributeError):
            piece.id = "new_id"
        with pytest.raises(AttributeError):
            piece.lumber_type = LumberType.LUMBER_1X4
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
