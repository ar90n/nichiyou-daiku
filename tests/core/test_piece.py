"""Tests for piece module."""

import pytest

from nichiyou_daiku.core.piece import (
    PieceType,
    Piece,
    get_shape,
)
from nichiyou_daiku.core.geometry import Face


class TestPieceType:
    """Test PieceType enum."""

    # Basic enum functionality is covered in doctests

    # PieceType.of() creation is covered in doctests

    # Error handling for unsupported types is covered in doctests


class TestPiece:
    """Test Piece model."""

    # Basic creation is covered in doctests

    # Piece.of() method is covered in doctests

    # UUID generation is covered in doctests

    def test_should_validate_positive_length(self):
        """Should validate that length is positive."""
        # Valid length
        piece = Piece.of(PieceType.PT_2x4, 100.0)
        assert piece.length == 100.0

        # Negative length should fail
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Piece(id="test", type=PieceType.PT_2x4, length=-100)


class TestFace:
    """Test Face literal type."""

    def test_should_have_all_six_faces(self):
        """Should support all six faces of a rectangular piece."""
        # Test Face literal values
        faces: list[Face] = ["top", "down", "left", "right", "front", "back"]
        assert len(faces) == 6

        # Test that each is a valid Face string
        for face in faces:
            # This will pass type checking
            f: Face = face
            assert isinstance(f, str)
            assert f in ["top", "down", "left", "right", "front", "back"]


class TestGetShape:
    """Test get_shape overloaded function."""

    # Shape retrieval from PieceType is covered in doctests

    # Shape retrieval from Piece is covered in doctests

    def test_should_handle_different_lengths(self):
        """Should return correct 3D shape for different piece lengths."""
        lengths = [500.0, 1000.0, 1500.0, 2000.0]

        for length in lengths:
            piece = Piece.of(PieceType.PT_2x4, length)
            shape = get_shape(piece)
            assert shape.length == length
            assert shape.width == 89.0
            assert shape.height == 38.0


class TestPieceLength:
    def test_zero_length_is_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Piece(id="z", type=PieceType.PT_2x4, length=0)

    def test_infinite_length_is_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Piece(id="inf", type=PieceType.PT_2x4, length=float("inf"))


# Actual SPF sizes in mm: (width, thickness)
CROSS_SECTIONS = {
    "1x4": (89.0, 19.0),
    "1x6": (140.0, 19.0),
    "1x8": (184.0, 19.0),
    "2x2": (38.0, 38.0),
    "2x4": (89.0, 38.0),
    "2x6": (140.0, 38.0),
}


class TestLumberTypes:
    @pytest.mark.parametrize(("name", "size"), CROSS_SECTIONS.items())
    def test_cross_section_is_width_by_thickness(self, name, size):
        shape = get_shape(PieceType.of(name))
        assert (shape.width, shape.height) == size

    def test_every_type_has_a_cross_section(self):
        assert {piece_type.value for piece_type in PieceType} == set(CROSS_SECTIONS)

    def test_unsupported_type_is_rejected(self):
        with pytest.raises(ValueError, match="Unsupported piece type: 4x4"):
            PieceType.of("4x4")
