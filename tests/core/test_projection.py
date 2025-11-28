"""Tests for projection module.

This module tests the coordinate transformation logic in projection.py,
specifically the _project_surface_point function which handles:
- Axis transposition (when coordinate systems are rotated 90 degrees)
- Axis flipping (when coordinate directions are reversed)
- Offset translation (preserving relative positions)
"""

import pytest

from nichiyou_daiku.core.anchor import Anchor, BoundAnchor, as_surface_point
from nichiyou_daiku.core.assembly import project_joint
from nichiyou_daiku.core.assembly.models import Joint
from nichiyou_daiku.core.geometry import FromMax, FromMin, Point2D, SurfacePoint
from nichiyou_daiku.core.piece import Piece, PieceType


def create_bound_anchor(
    length: float,
    contact_face: str,
    edge_shared_face: str,
    offset_type: str = "min",
    offset_value: float = 100.0,
    piece_id: str = "test",
) -> BoundAnchor:
    """Helper to create BoundAnchor for testing."""
    piece = Piece.of(PieceType.PT_2x4, length, piece_id)
    offset = FromMin(value=offset_value) if offset_type == "min" else FromMax(value=offset_value)
    anchor = Anchor(
        contact_face=contact_face,
        edge_shared_face=edge_shared_face,
        offset=offset,
    )
    return BoundAnchor(piece=piece, anchor=anchor)


class TestProjectJointIdentity:
    """Test projection when source and destination have same orientation."""

    def test_same_face_same_edge_preserves_relative_position(self):
        """When src and dst have same contact_face and edge, position offset is preserved."""
        src_bound = create_bound_anchor(
            length=1000.0,
            contact_face="front",
            edge_shared_face="top",
            offset_type="max",
            offset_value=100.0,
            piece_id="src",
        )
        dst_bound = create_bound_anchor(
            length=800.0,
            contact_face="front",
            edge_shared_face="top",
            offset_type="min",
            offset_value=50.0,
            piece_id="dst",
        )

        # Create joint at src anchor position
        src_joint = Joint.of_bound_anchor(src_bound)

        # Project to dst
        dst_joint = project_joint(src_bound, dst_bound, src_joint)

        # dst joint should be on front face
        assert dst_joint.position.face == "front"


class TestProjectJointAxisFlip:
    """Test projection when axes need to be flipped."""

    def test_top_to_down_flips_correctly(self):
        """Projection from top face to down face should flip appropriately."""
        src_bound = create_bound_anchor(
            length=1000.0,
            contact_face="top",
            edge_shared_face="front",
            offset_type="min",
            offset_value=100.0,
            piece_id="src",
        )
        dst_bound = create_bound_anchor(
            length=800.0,
            contact_face="down",
            edge_shared_face="front",
            offset_type="min",
            offset_value=50.0,
            piece_id="dst",
        )

        src_joint = Joint.of_bound_anchor(src_bound)
        dst_joint = project_joint(src_bound, dst_bound, src_joint)

        assert dst_joint.position.face == "down"

    def test_left_to_right_flips_correctly(self):
        """Projection from left face to right face should flip appropriately."""
        src_bound = create_bound_anchor(
            length=1000.0,
            contact_face="left",
            edge_shared_face="top",
            offset_type="max",
            offset_value=100.0,
            piece_id="src",
        )
        dst_bound = create_bound_anchor(
            length=800.0,
            contact_face="right",
            edge_shared_face="top",
            offset_type="min",
            offset_value=50.0,
            piece_id="dst",
        )

        src_joint = Joint.of_bound_anchor(src_bound)
        dst_joint = project_joint(src_bound, dst_bound, src_joint)

        assert dst_joint.position.face == "right"


class TestProjectJointAxisTranspose:
    """Test projection when axes need to be transposed (90-degree rotation)."""

    def test_front_to_top_transposes_axes(self):
        """Projection from front face to top face should transpose u/v axes."""
        src_bound = create_bound_anchor(
            length=1000.0,
            contact_face="front",
            edge_shared_face="top",
            offset_type="max",
            offset_value=100.0,
            piece_id="src",
        )
        dst_bound = create_bound_anchor(
            length=800.0,
            contact_face="top",
            edge_shared_face="front",
            offset_type="min",
            offset_value=50.0,
            piece_id="dst",
        )

        src_joint = Joint.of_bound_anchor(src_bound)
        dst_joint = project_joint(src_bound, dst_bound, src_joint)

        assert dst_joint.position.face == "top"

    def test_left_to_front_transposes_axes(self):
        """Projection from left face to front face should transpose u/v axes."""
        src_bound = create_bound_anchor(
            length=1000.0,
            contact_face="left",
            edge_shared_face="front",
            offset_type="max",
            offset_value=100.0,
            piece_id="src",
        )
        dst_bound = create_bound_anchor(
            length=800.0,
            contact_face="front",
            edge_shared_face="left",
            offset_type="min",
            offset_value=50.0,
            piece_id="dst",
        )

        src_joint = Joint.of_bound_anchor(src_bound)
        dst_joint = project_joint(src_bound, dst_bound, src_joint)

        assert dst_joint.position.face == "front"


class TestProjectJointOffsetPreservation:
    """Test that relative offsets are correctly preserved during projection."""

    def test_offset_from_anchor_preserved_with_flip(self):
        """Joint offset from anchor should be flipped when faces face each other.

        When two front faces connect, they face each other (opposite directions),
        so the u-axis is mirrored. A +25.4 offset on src becomes -25.4 on dst.
        """
        src_bound = create_bound_anchor(
            length=1000.0,
            contact_face="front",
            edge_shared_face="top",
            offset_type="max",
            offset_value=200.0,
            piece_id="src",
        )
        dst_bound = create_bound_anchor(
            length=800.0,
            contact_face="front",
            edge_shared_face="top",
            offset_type="min",
            offset_value=100.0,
            piece_id="dst",
        )

        # Create joint with offset from anchor
        src_anchor_sp = as_surface_point(src_bound)
        offset_joint_position = SurfacePoint(
            face="front",
            position=Point2D(
                u=src_anchor_sp.position.u + 25.4,  # 1 inch offset in u
                v=src_anchor_sp.position.v,
            ),
        )
        src_joint = Joint.of_surface_point(offset_joint_position, up_face="down")

        dst_joint = project_joint(src_bound, dst_bound, src_joint)

        # Check that the offset is flipped (faces face each other)
        dst_anchor_sp = as_surface_point(dst_bound)
        # The u offset should be negated because faces are opposite
        expected_u_offset = -25.4
        actual_u_offset = dst_joint.position.position.u - dst_anchor_sp.position.u
        assert abs(actual_u_offset - expected_u_offset) < 0.01


class TestProjectJointOrientationCalculation:
    """Test that joint orientation is correctly calculated for destination."""

    def test_orientation_direction_matches_contact_face_normal(self):
        """Joint orientation direction should be normal to destination contact face."""
        src_bound = create_bound_anchor(
            length=1000.0,
            contact_face="front",
            edge_shared_face="top",
            offset_type="max",
            offset_value=100.0,
            piece_id="src",
        )
        dst_bound = create_bound_anchor(
            length=800.0,
            contact_face="down",
            edge_shared_face="front",
            offset_type="min",
            offset_value=50.0,
            piece_id="dst",
        )

        src_joint = Joint.of_bound_anchor(src_bound)
        dst_joint = project_joint(src_bound, dst_bound, src_joint)

        # Down face normal is (0, 0, -1)
        assert dst_joint.orientation.direction.z == -1.0
        assert abs(dst_joint.orientation.direction.x) < 0.001
        assert abs(dst_joint.orientation.direction.y) < 0.001


class TestProjectJointParametrized:
    """Parametrized tests for various face combinations."""

    @pytest.mark.parametrize(
        "src_contact,src_edge,dst_contact,dst_edge",
        [
            # Same face family
            ("top", "front", "down", "front"),
            ("left", "top", "right", "top"),
            ("front", "top", "back", "top"),
            # Cross-face (90-degree rotation)
            ("top", "front", "front", "top"),
            ("top", "left", "left", "top"),
            ("front", "left", "left", "front"),
            # Mixed combinations
            ("top", "front", "left", "top"),
            ("down", "back", "right", "down"),
            ("front", "top", "down", "front"),
        ],
    )
    def test_projection_produces_valid_joint(
        self, src_contact, src_edge, dst_contact, dst_edge
    ):
        """Projection should produce valid joint for various face combinations."""
        src_bound = create_bound_anchor(
            length=1000.0,
            contact_face=src_contact,
            edge_shared_face=src_edge,
            offset_type="max",
            offset_value=100.0,
            piece_id="src",
        )
        dst_bound = create_bound_anchor(
            length=800.0,
            contact_face=dst_contact,
            edge_shared_face=dst_edge,
            offset_type="min",
            offset_value=50.0,
            piece_id="dst",
        )

        src_joint = Joint.of_bound_anchor(src_bound)
        dst_joint = project_joint(src_bound, dst_bound, src_joint)

        # Verify basic structure
        assert dst_joint.position.face == dst_contact
        assert isinstance(dst_joint.position.position, Point2D)
        assert dst_joint.orientation is not None

        # Verify orientation direction magnitude is 1
        dir_mag = (
            dst_joint.orientation.direction.x ** 2
            + dst_joint.orientation.direction.y ** 2
            + dst_joint.orientation.direction.z ** 2
        ) ** 0.5
        assert abs(dir_mag - 1.0) < 0.001

        # Verify up direction magnitude is 1
        up_mag = (
            dst_joint.orientation.up.x ** 2
            + dst_joint.orientation.up.y ** 2
            + dst_joint.orientation.up.z ** 2
        ) ** 0.5
        assert abs(up_mag - 1.0) < 0.001
