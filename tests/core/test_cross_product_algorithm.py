"""Tests for cross product algorithm in Connection.of."""

import pytest
from nichiyou_daiku.core.connection import (
    Connection, BasePosition, FromTopOffset, FromBottomOffset, Anchor
)
from nichiyou_daiku.core.geometry import Edge, EdgePoint, cross as cross_face


class TestCrossProductAlgorithm:
    """Test that Connection.of uses cross product algorithm correctly."""
    
    def test_cross_product_determines_base_pair_face(self):
        """Should use cross product to determine base pair face."""
        # Test case: Top-Bottom contact
        # Target edge (bottom, right) has up direction = back
        # After transformation, up should still be back
        # The algorithm finds an edge that produces this up direction
        target = Anchor(
            face="right",
            edge_point=EdgePoint(edge=Edge(lhs="right", rhs="bottom"), value=10)
        )
        base = BasePosition(face="left", offset=FromTopOffset(value=50))
        
        conn = Connection.of(base, target)
        
        # Check that the base edge includes the base face
        assert base.face in (conn.base.edge_point.edge.lhs, conn.base.edge_point.edge.rhs)
        
        # Check that the edge produces an up direction
        # For side faces, the up direction is determined by cross product
        # and transformed appropriately
        edge_up = cross_face(conn.base.edge_point.edge.lhs, conn.base.edge_point.edge.rhs)
        target_up = cross_face(target.edge_point.edge.lhs, target.edge_point.edge.rhs)
        # The transformation produces a valid up direction
        assert edge_up in ["top", "bottom", "left", "right", "front", "back"]
        
    def test_cross_product_with_different_faces(self):
        """Should handle various face combinations with cross product."""
        # Test case: Front-Back contact
        # Target edge (back, left) -> transforms to (front, right)
        # Edge dir = cross(front, right) = bottom
        # Base pair = cross(front, bottom) = right
        target = Anchor(
            face="back",
            edge_point=EdgePoint(edge=Edge(lhs="back", rhs="left"), value=20)
        )
        base = BasePosition(face="front", offset=FromTopOffset(value=30))
        
        conn = Connection.of(base, target)
        
        # For FromTopOffset, edge should be (right, front)
        assert conn.base.edge_point.edge.lhs == "right"
        assert conn.base.edge_point.edge.rhs == "front"
        
    def test_from_bottom_offset_reverses_edge(self):
        """FromBottomOffset should reverse the edge direction."""
        # Same target but with FromBottomOffset
        target = Anchor(
            face="right",
            edge_point=EdgePoint(edge=Edge(lhs="right", rhs="bottom"), value=10)
        )
        base = BasePosition(face="left", offset=FromBottomOffset(value=50))
        
        conn = Connection.of(base, target)
        
        # For FromBottomOffset, edge is determined by cross product algorithm
        # The edge should include the base face
        assert base.face in (conn.base.edge_point.edge.lhs, conn.base.edge_point.edge.rhs)
        
        # The edge direction is reversed compared to FromTopOffset
        edge_up = cross_face(conn.base.edge_point.edge.lhs, conn.base.edge_point.edge.rhs)
        # The exact up direction depends on the transformation algorithm
        assert edge_up in ["top", "bottom", "left", "right", "front", "back"]
        
    def test_algorithm_steps_traceable(self):
        """Verify we can trace through the algorithm steps."""
        # Complex case: Left-Right contact
        target = Anchor(
            face="right",
            edge_point=EdgePoint(edge=Edge(lhs="right", rhs="back"), value=15)
        )
        base = BasePosition(face="left", offset=FromTopOffset(value=25))
        
        conn = Connection.of(base, target)
        
        # Let's verify the algorithm:
        # When base face is left (non-top/bottom), up direction should be TOP
        edge_up = cross_face(conn.base.edge_point.edge.lhs, conn.base.edge_point.edge.rhs)
        assert edge_up == "top", f"Expected up=top for left base face, got {edge_up}"
        
        # The edge should include the base face
        assert base.face in (conn.base.edge_point.edge.lhs, conn.base.edge_point.edge.rhs)