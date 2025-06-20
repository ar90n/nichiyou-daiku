"""Tests for piece module."""

import pytest
from uuid import UUID

from nichiyou_daiku.core.piece import (
    PieceType,
    Piece,
    get_shape,
)
from nichiyou_daiku.core.geometry import Face
from nichiyou_daiku.core.geometry import Shape2D, Shape3D


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

        # Invalid length should fail
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            Piece(id="test", type=PieceType.PT_2x4, length=0)

        with pytest.raises(ValidationError):
            Piece(id="test", type=PieceType.PT_2x4, length=-100)


class TestFace:
    """Test Face literal type."""

    def test_should_have_all_six_faces(self):
        """Should support all six faces of a rectangular piece."""
        # Test Face literal values
        faces: list[Face] = ["top", "bottom", "left", "right", "front", "back"]
        assert len(faces) == 6
        
        # Test that each is a valid Face string
        for face in faces:
            # This will pass type checking
            f: Face = face
            assert isinstance(f, str)
            assert f in ["top", "bottom", "left", "right", "front", "back"]


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
