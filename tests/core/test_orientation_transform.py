"""Tests for orientation transformation in connections."""

import pytest
from nichiyou_daiku.core.connection import Connection, BasePosition, Anchor
from nichiyou_daiku.core.geometry import Edge, EdgePoint, Vector3D, cross as cross_face, FromMax, FromMin
from nichiyou_daiku.core.assembly import Joint, Assembly
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.model import Model, PiecePair


class TestOrientationTransform:
    """Test orientation preservation in connections."""
    
    def test_should_preserve_orientation_alignment(self):
        """Should preserve relative orientation when pieces connect."""
        # Create two pieces
        vertical = Piece.of(PieceType.PT_2x4, 600.0)
        horizontal = Piece.of(PieceType.PT_2x4, 400.0)
        
        # Create connection - horizontal piece on side of vertical
        connection = Connection.of(
            BasePosition(face="left", offset=FromMax(value=1.0)),
            Anchor(face="right", edge_point=EdgePoint(edge=Edge(lhs="right", rhs="back"), offset=FromMin(value=1.0)))
        )
        
        # Build assembly
        model = Model.of(
            [vertical, horizontal],
            [(PiecePair(base=vertical, target=horizontal), connection)]
        )
        assembly = Assembly.of(model)
        
        # Get joints - pieces have default IDs p0, p1
        key = list(assembly.connections.keys())[0]
        joint1 = assembly.connections[key].joint1
        joint2 = assembly.connections[key].joint2
        
        # Verify face normals are opposite (base face normal = -target face normal)
        dir1 = joint1.orientation.direction
        dir2 = joint2.orientation.direction
        
        # They should point in opposite directions
        assert abs(dir1.x + dir2.x) < 1e-6
        assert abs(dir1.y + dir2.y) < 1e-6
        assert abs(dir1.z + dir2.z) < 1e-6
        
    def test_edge_alignment_in_connection(self):
        """Test that edges align properly in connections."""
        # Create connection where edges should align
        target = Anchor(
            face="back",
            edge_point=EdgePoint(edge=Edge(lhs="back", rhs="left"), offset=FromMin(value=10))
        )
        base = BasePosition(face="front", offset=FromMax(value=10))
        
        conn = Connection.of(base, target)
        
        # Base edge should include the base face
        assert base.face in (conn.base.edge_point.edge.lhs, conn.base.edge_point.edge.rhs)
        
        # Values should match
        assert conn.base.edge_point.offset.value == base.offset.value
        assert conn.target.edge_point.offset.value == target.edge_point.offset.value