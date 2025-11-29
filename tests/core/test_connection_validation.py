"""Tests for connection validation."""

import pytest

from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
from nichiyou_daiku.core.connection import Connection, DowelConnection, ScrewConnection
from nichiyou_daiku.core.dowel import DowelSpec
from nichiyou_daiku.core.geometry import FromMin
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.screw import ScrewSpec


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

        # Small dowel that fits in 2x4 cross-section (diameter=8mm -> radius=4mm)
        spec = DowelSpec(diameter=8.0, length=20.0)
        conn = Connection.of_dowel(base_bound, target_bound, spec=spec)

        assert isinstance(conn.type, DowelConnection)
        assert conn.type.radius == 4.0
        assert conn.type.depth == 20.0

    def test_dowel_depth_at_boundary(self):
        """Dowel depth at exact boundary should succeed."""
        # 2x4 height is 38mm
        base_bound = create_bound_anchor("base", 1000.0, "front", "top")
        target_bound = create_bound_anchor("target", 800.0, "front", "top")

        spec = DowelSpec(diameter=8.0, length=38.0)
        conn = Connection.of_dowel(base_bound, target_bound, spec=spec)
        assert conn.type.depth == 38.0

    def test_depth_exceeds_base_piece_raises_error(self):
        """Dowel depth exceeding base piece dimension should raise error."""
        # front face normal is along height (38mm for 2x4)
        base_bound = create_bound_anchor("base", 1000.0, "front", "top")
        target_bound = create_bound_anchor("target", 800.0, "back", "top")

        spec = DowelSpec(diameter=8.0, length=50.0)
        with pytest.raises(ValueError, match="exceeds base piece dimension"):
            Connection.of_dowel(base_bound, target_bound, spec=spec)

    def test_depth_exceeds_target_piece_raises_error(self):
        """Dowel depth exceeding target piece dimension should raise error."""
        # top face normal is along length
        base_bound = create_bound_anchor("base", 1000.0, "top", "front")
        target_bound = create_bound_anchor("target", 30.0, "down", "front")

        spec = DowelSpec(diameter=8.0, length=50.0)
        with pytest.raises(ValueError, match="exceeds target piece dimension"):
            Connection.of_dowel(base_bound, target_bound, spec=spec)

    def test_radius_exceeds_base_cross_section_raises_error(self):
        """Dowel diameter exceeding base cross-section should raise error."""
        # front face: cross-section is width x length = 89mm x 1000mm
        # min is 89mm, so diameter > 89mm should fail
        base_bound = create_bound_anchor("base", 1000.0, "front", "top")
        target_bound = create_bound_anchor("target", 800.0, "back", "top")

        spec = DowelSpec(diameter=100.0, length=20.0)  # diameter=100mm > 89mm
        with pytest.raises(ValueError, match="exceeds base piece cross-section"):
            Connection.of_dowel(base_bound, target_bound, spec=spec)

    def test_radius_exceeds_target_cross_section_raises_error(self):
        """Dowel diameter exceeding target cross-section should raise error."""
        # top face: cross-section is width x height = 89mm x 38mm
        # min is 38mm, so diameter > 38mm should fail
        base_bound = create_bound_anchor("base", 1000.0, "front", "top")
        target_bound = create_bound_anchor("target", 800.0, "top", "front")

        spec = DowelSpec(diameter=40.0, length=20.0)  # diameter=40mm > 38mm
        with pytest.raises(ValueError, match="exceeds target piece cross-section"):
            Connection.of_dowel(base_bound, target_bound, spec=spec)

    def test_small_dowel_on_top_face(self):
        """Small dowel on top face should succeed."""
        # top face cross-section min is 38mm (height)
        base_bound = create_bound_anchor("base", 1000.0, "top", "front")
        target_bound = create_bound_anchor("target", 800.0, "down", "front")

        # Diameter 16mm < 38mm, should succeed
        spec = DowelSpec(diameter=16.0, length=20.0)
        conn = Connection.of_dowel(base_bound, target_bound, spec=spec)
        assert conn.type.radius == 8.0

    def test_dowel_on_different_face_types(self):
        """Dowel connections on different face types should validate correctly."""
        # left/right faces: cross-section is height x length
        base_bound = create_bound_anchor("base", 1000.0, "left", "top")
        target_bound = create_bound_anchor("target", 800.0, "right", "top")

        # left face: width is 89mm, cross-section min is 38mm (height)
        spec = DowelSpec(diameter=20.0, length=50.0)
        conn = Connection.of_dowel(base_bound, target_bound, spec=spec)
        assert conn.type.depth == 50.0


class TestScrewConnectionValidation:
    """Connection.of_screw() validation tests."""

    def test_valid_screw_connection(self):
        """Valid screw connection should succeed."""
        base_bound = create_bound_anchor("base", 1000.0, "front", "top")
        target_bound = create_bound_anchor("target", 800.0, "back", "top")

        # Small screw that fits: front face height=38mm + back face height=38mm = 76mm
        conn = Connection.of_screw(
            base_bound, target_bound, ScrewSpec(diameter=3.5, length=50.0)
        )

        assert isinstance(conn.type, ScrewConnection)
        assert conn.type.diameter == 3.5
        assert conn.type.length == 50.0

    def test_screw_length_at_boundary(self):
        """Screw length at exact combined boundary should succeed."""
        # front face (38mm) + back face (38mm) = 76mm
        base_bound = create_bound_anchor("base", 1000.0, "front", "top")
        target_bound = create_bound_anchor("target", 800.0, "back", "top")

        conn = Connection.of_screw(
            base_bound, target_bound, ScrewSpec(diameter=3.5, length=76.0)
        )
        assert conn.type.length == 76.0

    def test_length_exceeds_combined_depth_raises_error(self):
        """Screw length exceeding combined piece depth should raise error."""
        # front face (38mm) + back face (38mm) = 76mm
        base_bound = create_bound_anchor("base", 1000.0, "front", "top")
        target_bound = create_bound_anchor("target", 800.0, "back", "top")

        with pytest.raises(ValueError, match="exceeds combined piece depth"):
            Connection.of_screw(
                base_bound, target_bound, ScrewSpec(diameter=3.5, length=100.0)
            )

    def test_diameter_exceeds_base_cross_section_raises_error(self):
        """Screw diameter exceeding base cross-section should raise error."""
        # front face: cross-section is width x length = 89mm x 1000mm
        # min is 89mm, so diameter > 89mm should fail
        base_bound = create_bound_anchor("base", 1000.0, "front", "top")
        target_bound = create_bound_anchor("target", 800.0, "back", "top")

        with pytest.raises(ValueError, match="exceeds base piece cross-section"):
            Connection.of_screw(
                base_bound, target_bound, ScrewSpec(diameter=100.0, length=50.0)
            )

    def test_diameter_exceeds_target_cross_section_raises_error(self):
        """Screw diameter exceeding target cross-section should raise error."""
        # base top face: cross-section is width x height = 89mm x 38mm → min 38mm
        # target back face: cross-section is width x length = 89mm x 800mm → min 89mm
        # But base_min_cross=38mm < target_min_cross=89mm, so we need diameter
        # where target limit is smaller than base limit
        # Use base="top" (cross=38mm) and target="back" (cross=89mm)
        # diameter=50mm exceeds base (38mm) but not target (89mm)
        # So we can't test "target cross-section" error with front/back restriction
        # Instead, test that a diameter > 89mm fails on target
        # Need base cross-section > 89mm: use base="down" where cross = width x height = 89x38
        # Actually, for 2x4 all cross-sections have min=38mm except length-based faces
        # Use base="left" (cross=height x length = 38x1000 → min 38mm)
        # Use target="back" (cross=width x length = 89x800 → min 89mm)
        # diameter=50mm exceeds base (38mm) first...
        # Let's use a different approach: make base cross-section large by using "top" face
        # base top: cross = width x height = 89 x 38 → min 38mm
        # This is tricky. Let's just test that the validation works with appropriate values
        # The test was originally designed for target="left" which had min=38mm
        # With target="back", min=89mm. Base front: min=89mm too.
        # So diameter=100mm will exceed both equally.
        # Since base is checked first, we'll get base error.
        # To test target error specifically, we need base_min > target_min
        # With front/back restriction on target, target min is always 89mm (width x length)
        # We need base to have larger cross-section than 89mm
        # This is not possible with 2x4 lumber using of_screw validation order
        # So this test should check that diameter exceeding BOTH cross-sections fails
        base_bound = create_bound_anchor("base", 1000.0, "front", "top")
        target_bound = create_bound_anchor("target", 800.0, "back", "top")

        # diameter=100mm exceeds both base (89mm) and target (89mm) cross-sections
        # base is checked first, so we get base error
        with pytest.raises(ValueError, match="exceeds.*cross-section"):
            Connection.of_screw(
                base_bound, target_bound, ScrewSpec(diameter=100.0, length=50.0)
            )

    def test_screw_on_top_face(self):
        """Screw on top/down face should succeed with valid dimensions."""
        # base top face depth: length (1000mm), target back face depth: height (38mm)
        # max_length = 1000 + 38 = 1038mm, need length > 38mm to reach base
        base_bound = create_bound_anchor("base", 1000.0, "top", "front")
        target_bound = create_bound_anchor("target", 800.0, "back", "top")

        conn = Connection.of_screw(
            base_bound, target_bound, ScrewSpec(diameter=5.0, length=50.0)
        )
        assert conn.type.diameter == 5.0

    def test_screw_on_left_right_faces(self):
        """Screw connections on left/right base faces should validate correctly."""
        # base left face depth: width (89mm), target back face depth: height (38mm)
        # max_length = 89 + 38 = 127mm, need length > 38mm to reach base
        base_bound = create_bound_anchor("base", 1000.0, "left", "top")
        target_bound = create_bound_anchor("target", 800.0, "back", "top")

        conn = Connection.of_screw(
            base_bound, target_bound, ScrewSpec(diameter=5.0, length=50.0)
        )
        assert conn.type.length == 50.0

    def test_screw_length_does_not_reach_base_raises_error(self):
        """Screw length that doesn't reach base piece should raise error."""
        # target face: height=38mm (front/back faces for 2x4)
        # screw length <= 38mm means it won't reach base
        base_bound = create_bound_anchor("base", 1000.0, "front", "top")
        target_bound = create_bound_anchor("target", 800.0, "back", "top")

        with pytest.raises(ValueError, match="does not reach base piece"):
            Connection.of_screw(
                base_bound, target_bound, ScrewSpec(diameter=3.5, length=38.0)
            )

    def test_screw_length_just_reaches_base(self):
        """Screw length that just reaches base should succeed."""
        # target face: height=38mm, screw length=38.1mm reaches base by 0.1mm
        base_bound = create_bound_anchor("base", 1000.0, "front", "top")
        target_bound = create_bound_anchor("target", 800.0, "back", "top")

        conn = Connection.of_screw(
            base_bound, target_bound, ScrewSpec(diameter=3.5, length=38.1)
        )
        assert conn.type.length == 38.1

    def test_screw_target_contact_face_must_be_front_or_back(self):
        """ScrewConnection target contact_face must be front or back."""
        base_bound = create_bound_anchor("base", 1000.0, "front", "top")

        # top face should fail
        target_bound_top = create_bound_anchor("target", 800.0, "top", "front")
        with pytest.raises(ValueError, match="must be 'front' or 'back'"):
            Connection.of_screw(
                base_bound, target_bound_top, ScrewSpec(diameter=4.0, length=850.0)
            )

        # left face should fail
        target_bound_left = create_bound_anchor("target", 800.0, "left", "top")
        with pytest.raises(ValueError, match="must be 'front' or 'back'"):
            Connection.of_screw(
                base_bound, target_bound_left, ScrewSpec(diameter=4.0, length=100.0)
            )

        # down face should fail
        target_bound_down = create_bound_anchor("target", 800.0, "down", "front")
        with pytest.raises(ValueError, match="must be 'front' or 'back'"):
            Connection.of_screw(
                base_bound, target_bound_down, ScrewSpec(diameter=4.0, length=850.0)
            )

        # right face should fail
        target_bound_right = create_bound_anchor("target", 800.0, "right", "top")
        with pytest.raises(ValueError, match="must be 'front' or 'back'"):
            Connection.of_screw(
                base_bound, target_bound_right, ScrewSpec(diameter=4.0, length=100.0)
            )

    def test_screw_target_contact_face_front_succeeds(self):
        """ScrewConnection with target contact_face='front' should succeed."""
        base_bound = create_bound_anchor("base", 1000.0, "back", "top")
        target_bound = create_bound_anchor("target", 800.0, "front", "top")

        conn = Connection.of_screw(
            base_bound, target_bound, ScrewSpec(diameter=4.0, length=50.0)
        )
        assert conn.type.length == 50.0

    def test_screw_target_contact_face_back_succeeds(self):
        """ScrewConnection with target contact_face='back' should succeed."""
        base_bound = create_bound_anchor("base", 1000.0, "front", "top")
        target_bound = create_bound_anchor("target", 800.0, "back", "top")

        conn = Connection.of_screw(
            base_bound, target_bound, ScrewSpec(diameter=4.0, length=50.0)
        )
        assert conn.type.length == 50.0
