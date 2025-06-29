"""Tests for Connection.of coordinate transformation logic."""

from nichiyou_daiku.core.connection import (
    Connection,
    Anchor,
    as_edge_point,
)
from nichiyou_daiku.core.geometry import Edge, EdgePoint, FromMax, FromMin


class TestConnectionTransform:
    """Test Connection transformation logic."""

    def test_should_transform_anchor_to_edge_point(self):
        """Should correctly transform anchor to edge point."""

        # Case 1: Anchor with left contact face and bottom edge shared face
        anchor = Anchor(
            contact_face="left",
            edge_shared_face="bottom",
            offset=FromMax(value=50)
        )

        edge_point = as_edge_point(anchor)

        # Edge should include the contact face "left"
        assert anchor.contact_face in (
            edge_point.edge.lhs,
            edge_point.edge.rhs,
        )
        assert edge_point.offset.value == 50

    def test_should_handle_different_face_contacts(self):
        """Should handle various contact face combinations."""

        # Case 2: Anchor with front contact face and right edge shared face
        anchor = Anchor(
            contact_face="front",
            edge_shared_face="right",
            offset=FromMax(value=30)
        )

        edge_point = as_edge_point(anchor)

        # Edge should include the contact face "front"
        assert anchor.contact_face in (
            edge_point.edge.lhs,
            edge_point.edge.rhs,
        )
        assert edge_point.offset.value == 30

    def test_should_handle_complex_transformations(self):
        """Should handle complex coordinate transformations correctly."""

        # Case 3: Anchor with left contact face and top edge shared face
        anchor = Anchor(
            contact_face="left",
            edge_shared_face="top",
            offset=FromMax(value=25)
        )

        edge_point = as_edge_point(anchor)

        # Edge should include the contact face "left"
        assert anchor.contact_face in (
            edge_point.edge.lhs,
            edge_point.edge.rhs,
        )
        assert edge_point.offset.value == 25
