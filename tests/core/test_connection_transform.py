"""Tests for Connection.of coordinate transformation logic."""

import pytest
from nichiyou_daiku.core.connection import (
    Connection,
    BasePosition,
    FromTopOffset,
    Anchor,
)
from nichiyou_daiku.core.geometry import Edge, EdgePoint


class TestConnectionTransform:
    """Test Connection.of transformation logic."""
    
    def test_should_transform_target_edge_to_base_coordinates(self):
        """Should correctly transform target edge direction to base coordinates."""
        
        # Case 1: Base left contacts target right
        # Target edge: (right, bottom)
        # When left contacts right: right->right, bottom->top
        # Since base face is "left", edge is adjusted to include it
        target = Anchor(
            face="right",
            edge_point=EdgePoint(edge=Edge(lhs="right", rhs="bottom"), value=10)
        )
        base = BasePosition(face="left", offset=FromTopOffset(value=50))
        
        conn = Connection.of(base, target)
        
        # Base edge must include the base face "left"
        assert base.face in (conn.base.edge_point.edge.lhs, conn.base.edge_point.edge.rhs)
        assert conn.base.edge_point.value == 50
        
    def test_should_handle_different_face_contacts(self):
        """Should handle various base-target face contact combinations."""
        
        # Case 2: Base front contacts target top
        # Target edge: (top, right)
        # Edge must include base face "front"
        target = Anchor(
            face="top",
            edge_point=EdgePoint(edge=Edge(lhs="top", rhs="right"), value=20)
        )
        base = BasePosition(face="front", offset=FromTopOffset(value=30))
        
        conn = Connection.of(base, target)
        
        # Base edge must include the base face "front"
        assert base.face in (conn.base.edge_point.edge.lhs, conn.base.edge_point.edge.rhs)
        assert conn.base.edge_point.value == 30
        
    def test_should_handle_complex_transformations(self):
        """Should handle complex coordinate transformations correctly."""
        
        # Case 3: Base left contacts target right
        # Target edge: (right, top)
        # Edge must include base face "left"
        target = Anchor(
            face="right",
            edge_point=EdgePoint(edge=Edge(lhs="right", rhs="top"), value=15)
        )
        base = BasePosition(face="left", offset=FromTopOffset(value=25))
        
        conn = Connection.of(base, target)
        
        # Base edge must include the base face "left"
        assert base.face in (conn.base.edge_point.edge.lhs, conn.base.edge_point.edge.rhs)
        assert conn.base.edge_point.value == 25