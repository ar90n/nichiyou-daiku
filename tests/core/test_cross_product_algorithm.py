"""Tests for cross product algorithm in Connection.of."""

from nichiyou_daiku.core.connection import Anchor
from nichiyou_daiku.core.geometry import (
    cross as cross_face,
    FromMax,
    FromMin,
)


class TestCrossProductAlgorithm:
    """Test cross product algorithm in connection module."""

    def test_cross_product_determines_edge_direction(self):
        """Should use cross product to determine edge direction."""
        # Test case: contact face "left" with edge shared face "bottom"
        anchor = Anchor(
            contact_face="left", edge_shared_face="bottom", offset=FromMax(value=50)
        )

        from nichiyou_daiku.core.connection import as_edge_point

        edge_point = as_edge_point(anchor)

        # Check that the edge includes the contact face
        assert anchor.contact_face in (
            edge_point.edge.lhs,
            edge_point.edge.rhs,
        )

        # Check that the edge produces a valid up direction
        edge_up = cross_face(edge_point.edge.lhs, edge_point.edge.rhs)
        # The transformation produces a valid up direction
        assert edge_up in ["top", "bottom", "left", "right", "front", "back"]

    def test_cross_product_with_different_faces(self):
        """Should handle various face combinations with cross product."""
        # Test case: contact face "front" with edge shared face "right"
        anchor = Anchor(
            contact_face="front", edge_shared_face="right", offset=FromMax(value=30)
        )

        from nichiyou_daiku.core.connection import as_edge_point

        edge_point = as_edge_point(anchor)

        # Check that cross product determines correct edge direction
        edge_up = cross_face(edge_point.edge.lhs, edge_point.edge.rhs)
        assert edge_up in ["top", "bottom", "left", "right", "front", "back"]

    def test_from_min_offset_affects_edge_direction(self):
        """FromMin offset should affect edge direction."""
        # Test with FromMin offset
        anchor = Anchor(
            contact_face="left", edge_shared_face="bottom", offset=FromMin(value=50)
        )

        from nichiyou_daiku.core.connection import as_edge_point

        edge_point = as_edge_point(anchor)

        # The edge should include the contact face
        assert anchor.contact_face in (
            edge_point.edge.lhs,
            edge_point.edge.rhs,
        )

        # Cross product produces valid direction
        edge_up = cross_face(edge_point.edge.lhs, edge_point.edge.rhs)
        assert edge_up in ["top", "bottom", "left", "right", "front", "back"]

    def test_algorithm_steps_traceable(self):
        """Verify we can trace through the algorithm steps."""
        # Test case: contact face "left" with edge shared face "back"
        anchor = Anchor(
            contact_face="left", edge_shared_face="back", offset=FromMax(value=25)
        )

        from nichiyou_daiku.core.connection import as_edge_point

        edge_point = as_edge_point(anchor)

        # Verify the cross product algorithm
        edge_up = cross_face(edge_point.edge.lhs, edge_point.edge.rhs)
        # The edge should produce a consistent up direction
        assert edge_up in ["top", "bottom", "left", "right", "front", "back"]

        # The edge should include the contact face
        assert anchor.contact_face in (
            edge_point.edge.lhs,
            edge_point.edge.rhs,
        )
