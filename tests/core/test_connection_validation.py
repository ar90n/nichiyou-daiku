"""Tests for connection validation."""

import pytest

from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.connection import Connection, DowelConnection
from nichiyou_daiku.core.geometry import FromMin
from nichiyou_daiku.core.piece import Piece, PieceType


def create_bound_anchor(
    piece_id: str,
    length: float,
    contact_face: str,
    edge_shared_face: str,
    offset_value: float | None = None,
) -> BoundAnchor:
    """Helper to create a BoundAnchor for testing.

    Args:
        piece_id: ID for the piece
        length: Piece length in mm
        contact_face: Face that makes contact
        edge_shared_face: Face that shares the edge
        offset_value: Offset value (defaults to 0 if None)

    Returns:
        BoundAnchor instance
    """
    piece = Piece.of(PieceType.PT_2x4, length, piece_id)
    # Use 0 as default to avoid exceeding dimension limits
    value = offset_value if offset_value is not None else 0.0
    anchor = Anchor.of(contact_face, edge_shared_face, FromMin(value=value))
    return BoundAnchor.of(piece, anchor)


class TestDowelConnectionValidation:
    """Connection.of_dowel() validation tests."""

    def test_valid_dowel_connection(self):
        """Valid dowel connection should succeed."""
        base_bound = create_bound_anchor("base", 1000.0, "front", "top")
        target_bound = create_bound_anchor("target", 800.0, "back", "top")

        # Small dowel that fits in 2x4 cross-section
        conn = Connection.of_dowel(base_bound, target_bound, radius=4.0, depth=20.0)

        assert isinstance(conn.type, DowelConnection)
        assert conn.type.radius == 4.0
        assert conn.type.depth == 20.0

    def test_dowel_depth_at_boundary(self):
        """Dowel depth at exact boundary should succeed."""
        # 2x4 height is 38mm
        base_bound = create_bound_anchor("base", 1000.0, "front", "top")
        target_bound = create_bound_anchor("target", 800.0, "front", "top")

        conn = Connection.of_dowel(base_bound, target_bound, radius=4.0, depth=38.0)
        assert conn.type.depth == 38.0

    def test_depth_exceeds_base_piece_raises_error(self):
        """Dowel depth exceeding base piece dimension should raise error."""
        # front face normal is along height (38mm for 2x4)
        base_bound = create_bound_anchor("base", 1000.0, "front", "top")
        target_bound = create_bound_anchor("target", 800.0, "back", "top")

        with pytest.raises(ValueError, match="exceeds base piece dimension"):
            Connection.of_dowel(base_bound, target_bound, radius=4.0, depth=50.0)

    def test_depth_exceeds_target_piece_raises_error(self):
        """Dowel depth exceeding target piece dimension should raise error."""
        # top face normal is along length
        base_bound = create_bound_anchor("base", 1000.0, "top", "front")
        target_bound = create_bound_anchor("target", 30.0, "down", "front")

        with pytest.raises(ValueError, match="exceeds target piece dimension"):
            Connection.of_dowel(base_bound, target_bound, radius=4.0, depth=50.0)

    def test_radius_exceeds_base_cross_section_raises_error(self):
        """Dowel diameter exceeding base cross-section should raise error."""
        # front face: cross-section is width x length = 89mm x 1000mm
        # min is 89mm, so diameter > 89mm should fail
        base_bound = create_bound_anchor("base", 1000.0, "front", "top")
        target_bound = create_bound_anchor("target", 800.0, "back", "top")

        with pytest.raises(ValueError, match="exceeds base piece cross-section"):
            Connection.of_dowel(base_bound, target_bound, radius=50.0, depth=20.0)

    def test_radius_exceeds_target_cross_section_raises_error(self):
        """Dowel diameter exceeding target cross-section should raise error."""
        # top face: cross-section is width x height = 89mm x 38mm
        # min is 38mm, so diameter > 38mm should fail
        base_bound = create_bound_anchor("base", 1000.0, "front", "top")
        target_bound = create_bound_anchor("target", 800.0, "top", "front")

        with pytest.raises(ValueError, match="exceeds target piece cross-section"):
            Connection.of_dowel(base_bound, target_bound, radius=20.0, depth=20.0)

    def test_small_dowel_on_top_face(self):
        """Small dowel on top face should succeed."""
        # top face cross-section min is 38mm (height)
        base_bound = create_bound_anchor("base", 1000.0, "top", "front")
        target_bound = create_bound_anchor("target", 800.0, "down", "front")

        # Diameter 16mm < 38mm, should succeed
        conn = Connection.of_dowel(base_bound, target_bound, radius=8.0, depth=20.0)
        assert conn.type.radius == 8.0

    def test_dowel_on_different_face_types(self):
        """Dowel connections on different face types should validate correctly."""
        # left/right faces: cross-section is height x length
        base_bound = create_bound_anchor("base", 1000.0, "left", "top")
        target_bound = create_bound_anchor("target", 800.0, "right", "top")

        # left face: width is 89mm, cross-section min is 38mm (height)
        conn = Connection.of_dowel(base_bound, target_bound, radius=10.0, depth=50.0)
        assert conn.type.depth == 50.0
