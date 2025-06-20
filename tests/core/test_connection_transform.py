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
        
        # Case 1: Base top contacts target bottom
        # Target edge: (bottom, right) -> direction is "back" (cross product)
        # Transform: back in target coords -> back in base coords (when top contacts bottom)
        # Base pair face: cross(top, back) = right
        target = Anchor(
            face="bottom",
            edge_point=EdgePoint(edge=Edge(lhs="bottom", rhs="right"), value=10)
        )
        base = BasePosition(face="top", offset=FromTopOffset(value=50))
        
        conn = Connection.of(base, target)
        
        # Expected: base edge should be (right, top) for FromTopOffset
        assert conn.base.edge_point.edge.lhs == "right"
        assert conn.base.edge_point.edge.rhs == "top"
        assert conn.base.edge_point.value == 50
        
    def test_should_handle_different_face_contacts(self):
        """Should handle various base-target face contact combinations."""
        
        # Case 2: Base front contacts target top
        # Target edge: (top, right) -> direction is "front" (cross product)
        # Transform: front in target coords -> top in base coords (when front contacts top)
        # Base pair face: cross(front, top) = right
        target = Anchor(
            face="top",
            edge_point=EdgePoint(edge=Edge(lhs="top", rhs="right"), value=20)
        )
        base = BasePosition(face="front", offset=FromTopOffset(value=30))
        
        conn = Connection.of(base, target)
        
        # Expected: base edge should be (right, front) for FromTopOffset
        assert conn.base.edge_point.edge.lhs == "right"
        assert conn.base.edge_point.edge.rhs == "front"
        assert conn.base.edge_point.value == 30
        
    def test_should_handle_complex_transformations(self):
        """Should handle complex coordinate transformations correctly."""
        
        # Case 3: Base left contacts target right
        # Target edge: (right, top) -> direction is "back" (cross product)
        # Transform: back in target coords -> front in base coords (when left contacts right)
        # Base pair face: cross(left, front) = bottom
        target = Anchor(
            face="right",
            edge_point=EdgePoint(edge=Edge(lhs="right", rhs="top"), value=15)
        )
        base = BasePosition(face="left", offset=FromTopOffset(value=25))
        
        conn = Connection.of(base, target)
        
        # Expected: base edge should be (bottom, left) for FromTopOffset
        assert conn.base.edge_point.edge.lhs == "bottom"
        assert conn.base.edge_point.edge.rhs == "left"
        assert conn.base.edge_point.value == 25