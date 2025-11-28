"""Tests for anchor validation."""

import pytest

from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.geometry import FromMin, FromMax
from nichiyou_daiku.core.piece import Piece, PieceType


class TestAnchorValidation:
    """Anchor.of() validation tests."""

    def test_adjacent_faces_valid(self):
        """Adjacent face combinations should succeed."""
        anchor = Anchor.of("front", "top", FromMin(value=0))
        assert anchor.contact_face == "front"
        assert anchor.edge_shared_face == "top"

    def test_all_valid_adjacent_combinations(self):
        """All valid adjacent face combinations should succeed."""
        valid_combinations = [
            ("top", "front"),
            ("top", "back"),
            ("top", "left"),
            ("top", "right"),
            ("down", "front"),
            ("down", "back"),
            ("down", "left"),
            ("down", "right"),
            ("front", "top"),
            ("front", "down"),
            ("front", "left"),
            ("front", "right"),
            ("back", "top"),
            ("back", "down"),
            ("back", "left"),
            ("back", "right"),
            ("left", "top"),
            ("left", "down"),
            ("left", "front"),
            ("left", "back"),
            ("right", "top"),
            ("right", "down"),
            ("right", "front"),
            ("right", "back"),
        ]
        for contact, edge_shared in valid_combinations:
            anchor = Anchor.of(contact, edge_shared, FromMin(value=0))
            assert anchor.contact_face == contact
            assert anchor.edge_shared_face == edge_shared

    def test_same_face_raises_error(self):
        """Same face for contact and edge_shared should raise error."""
        with pytest.raises(ValueError, match="must be adjacent"):
            Anchor.of("front", "front", FromMin(value=0))

    def test_opposite_faces_raises_error(self):
        """Opposite faces should raise error."""
        opposite_pairs = [
            ("top", "down"),
            ("down", "top"),
            ("left", "right"),
            ("right", "left"),
            ("front", "back"),
            ("back", "front"),
        ]
        for contact, edge_shared in opposite_pairs:
            with pytest.raises(ValueError, match="must be adjacent"):
                Anchor.of(contact, edge_shared, FromMin(value=0))


class TestBoundAnchorValidation:
    """BoundAnchor.of() validation tests.

    Edge directions for 2x4 (width=89mm, height=38mm, length=variable):
    Determined by cross(contact_face, edge_shared_face):
    - front+top → width (89mm)
    - front+left → length
    - top+front → width (89mm)
    - top+left → height (38mm)
    - left+top → height (38mm)
    - left+front → length
    """

    def test_valid_offset_along_length(self):
        """Valid offset along length should succeed."""
        piece = Piece.of(PieceType.PT_2x4, 1000.0, "test")
        # front+left edge runs along length (1000mm)
        anchor = Anchor.of("front", "left", FromMin(value=500))
        bound = BoundAnchor.of(piece, anchor)
        assert bound.piece == piece
        assert bound.anchor == anchor

    def test_valid_offset_along_width(self):
        """Valid offset along width should succeed."""
        piece = Piece.of(PieceType.PT_2x4, 1000.0, "test")
        # front+top edge runs along width (89mm)
        anchor = Anchor.of("front", "top", FromMin(value=50))
        bound = BoundAnchor.of(piece, anchor)
        assert bound.piece == piece

    def test_valid_offset_along_height(self):
        """Valid offset along height should succeed."""
        piece = Piece.of(PieceType.PT_2x4, 1000.0, "test")
        # top+left edge runs along height (38mm)
        anchor = Anchor.of("top", "left", FromMin(value=20))
        bound = BoundAnchor.of(piece, anchor)
        assert bound.piece == piece

    def test_valid_offset_from_max(self):
        """Valid offset from max should succeed."""
        piece = Piece.of(PieceType.PT_2x4, 1000.0, "test")
        # front+left edge runs along length (1000mm)
        anchor = Anchor.of("front", "left", FromMax(value=500))
        bound = BoundAnchor.of(piece, anchor)
        assert bound.piece == piece

    def test_offset_at_boundary_length(self):
        """Offset exactly at length boundary should succeed."""
        piece = Piece.of(PieceType.PT_2x4, 1000.0, "test")
        # front+left edge runs along length (1000mm)
        anchor = Anchor.of("front", "left", FromMin(value=1000))
        bound = BoundAnchor.of(piece, anchor)
        assert bound.piece == piece

    def test_offset_at_boundary_width(self):
        """Offset exactly at width boundary should succeed."""
        piece = Piece.of(PieceType.PT_2x4, 1000.0, "test")
        # front+top edge runs along width (89mm)
        anchor = Anchor.of("front", "top", FromMin(value=89))
        bound = BoundAnchor.of(piece, anchor)
        assert bound.piece == piece

    def test_offset_at_boundary_height(self):
        """Offset exactly at height boundary should succeed."""
        piece = Piece.of(PieceType.PT_2x4, 1000.0, "test")
        # top+left edge runs along height (38mm)
        anchor = Anchor.of("top", "left", FromMin(value=38))
        bound = BoundAnchor.of(piece, anchor)
        assert bound.piece == piece

    def test_offset_zero_valid(self):
        """Zero offset should succeed."""
        piece = Piece.of(PieceType.PT_2x4, 1000.0, "test")
        anchor = Anchor.of("front", "top", FromMin(value=0))
        bound = BoundAnchor.of(piece, anchor)
        assert bound.piece == piece

    def test_offset_exceeds_length_raises_error(self):
        """Offset exceeding piece length should raise error."""
        piece = Piece.of(PieceType.PT_2x4, 1000.0, "test")
        # front+left edge runs along length (1000mm)
        anchor = Anchor.of("front", "left", FromMin(value=1500))
        with pytest.raises(ValueError, match="exceeds piece dimension"):
            BoundAnchor.of(piece, anchor)

    def test_offset_exceeds_width_raises_error(self):
        """Offset exceeding piece width should raise error."""
        piece = Piece.of(PieceType.PT_2x4, 1000.0, "test")
        # front+top edge runs along width (89mm for 2x4)
        anchor = Anchor.of("front", "top", FromMin(value=100))
        with pytest.raises(ValueError, match="exceeds piece dimension"):
            BoundAnchor.of(piece, anchor)

    def test_offset_exceeds_height_raises_error(self):
        """Offset exceeding piece height should raise error."""
        piece = Piece.of(PieceType.PT_2x4, 1000.0, "test")
        # top+left edge runs along height (38mm for 2x4)
        anchor = Anchor.of("top", "left", FromMin(value=50))
        with pytest.raises(ValueError, match="exceeds piece dimension"):
            BoundAnchor.of(piece, anchor)
