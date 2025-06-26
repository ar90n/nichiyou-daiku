"""Test that orientation is properly preserved through transformations."""

import pytest
from nichiyou_daiku.core.assembly import Assembly, Joint, Connection as AssemblyConnection
from nichiyou_daiku.core.connection import Connection, BasePosition, FromTopOffset, Anchor
from nichiyou_daiku.core.geometry import (
    Point3D, Vector3D, Orientation3D, Edge, EdgePoint, Box,
    cross as cross_face
)
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.piece import Piece, PieceType


class TestOrientationPreservation:
    """Test that orientation (direction and up) is preserved in assemblies."""
    
    def test_orientation_preserved_in_joints(self):
        """Joints should maintain full 3D orientation with direction and up vectors."""
        # Create a joint with specific orientation
        orientation = Orientation3D.of(
            direction=Vector3D(x=1.0, y=0.0, z=0.0),  # X direction
            up=Vector3D(x=0.0, y=1.0, z=0.0)  # Y up
        )
        joint = Joint(
            position=Point3D(x=100, y=50, z=25),
            orientation=orientation
        )
        
        # Check that orientation is preserved
        assert joint.orientation.direction.x == 1.0
        assert joint.orientation.up.y == 1.0
        
        # Euler angle conversion test removed - function doesn't exist
    
    def test_assembly_connection_preserves_orientation(self):
        """Assembly connections should preserve orientation through coordinate transformations."""
        # Create two pieces
        p1 = Piece.of(PieceType.PT_2x4, 1000.0, "base")
        p2 = Piece.of(PieceType.PT_2x4, 800.0, "target")
        
        # Create connection where orientation matters
        # Base: left face with position
        # Target: right face with edge (right, bottom) -> up = front
        conn = Connection.of(
            base=BasePosition(face="left", offset=FromTopOffset(value=100)),
            target=Anchor(
                face="right",
                edge_point=EdgePoint(edge=Edge(lhs="right", rhs="bottom"), value=50)
            )
        )
        
        # Create model and assembly
        from nichiyou_daiku.core.model import PiecePair
        model = Model.of(
            pieces=[p1, p2], 
            connections=[(PiecePair(base=p1, target=p2), conn)]
        )
        assembly = Assembly.of(model)
        
        # Get the connection from assembly
        asm_conn = assembly.connections[("base", "target")]
        
        # Check base joint
        base_joint = asm_conn.joint1
        # The base edge was determined by the algorithm
        base_edge_up = cross_face(conn.base.edge_point.edge.lhs, conn.base.edge_point.edge.rhs)
        
        # Check target joint  
        target_joint = asm_conn.joint2
        target_edge_up = cross_face(conn.target.edge_point.edge.lhs, conn.target.edge_point.edge.rhs)
        
        # Both should have proper orientations
        assert isinstance(base_joint.orientation, Orientation3D)
        assert isinstance(target_joint.orientation, Orientation3D)
        
        # The orientations should be set correctly based on faces and edges
        # Base: face=left -> direction=(0,-1,0), edge determines up
        assert base_joint.orientation.direction == Vector3D(x=0.0, y=-1.0, z=0.0)
        
        # Target: face=right -> direction=(0,1,0), edge determines up
        assert target_joint.orientation.direction == Vector3D(x=0.0, y=1.0, z=0.0)
    
    def test_complex_orientation_scenario(self):
        """Test a complex scenario with multiple orientations."""
        # Create three pieces forming an L-shape with specific orientations
        p1 = Piece.of(PieceType.PT_2x4, 1000.0, "vertical")
        p2 = Piece.of(PieceType.PT_2x4, 800.0, "horizontal")
        p3 = Piece.of(PieceType.PT_2x4, 600.0, "brace")
        
        # Connection 1: vertical top to horizontal bottom
        # This tests top-bottom contact with orientation preservation
        conn1 = Connection.of(
            base=BasePosition(face="front", offset=FromTopOffset(value=50)),
            target=Anchor(
                face="bottom",
                edge_point=EdgePoint(edge=Edge(lhs="bottom", rhs="front"), value=100)
            )
        )
        
        # Connection 2: horizontal right to brace left  
        # This tests left-right contact with different orientations
        conn2 = Connection.of(
            base=BasePosition(face="right", offset=FromTopOffset(value=200)),
            target=Anchor(
                face="left",
                edge_point=EdgePoint(edge=Edge(lhs="left", rhs="top"), value=150)
            )
        )
        
        from nichiyou_daiku.core.model import PiecePair
        model = Model.of(
            pieces=[p1, p2, p3],
            connections=[
                (PiecePair(base=p1, target=p2), conn1),
                (PiecePair(base=p2, target=p3), conn2)
            ]
        )
        assembly = Assembly.of(model)
        
        # Verify all connections have proper orientations
        for conn_key, conn in assembly.connections.items():
            assert isinstance(conn.joint1.orientation, Orientation3D)
            assert isinstance(conn.joint2.orientation, Orientation3D)
            
            # Check that direction vectors are unit vectors
            dir1 = conn.joint1.orientation.direction
            dir1_mag = (dir1.x**2 + dir1.y**2 + dir1.z**2)**0.5
            assert abs(dir1_mag - 1.0) < 1e-6
            
            dir2 = conn.joint2.orientation.direction
            dir2_mag = (dir2.x**2 + dir2.y**2 + dir2.z**2)**0.5
            assert abs(dir2_mag - 1.0) < 1e-6
            
            # Check that up vectors are unit vectors and orthogonal to direction
            up1 = conn.joint1.orientation.up
            up1_mag = (up1.x**2 + up1.y**2 + up1.z**2)**0.5
            assert abs(up1_mag - 1.0) < 1e-6
            
            # Dot product should be ~0 for orthogonal vectors
            dot1 = dir1.x * up1.x + dir1.y * up1.y + dir1.z * up1.z
            assert abs(dot1) < 1e-6
    
    def test_orientation_from_face_and_edge(self):
        """Test creating orientation from face and edge."""
        # Test various face/edge combinations
        test_cases = [
            ("top", Edge(lhs="top", rhs="front"), Vector3D(x=1, y=0, z=0), Vector3D(x=0, y=-1, z=0)),
            ("front", Edge(lhs="front", rhs="right"), Vector3D(x=0, y=0, z=1), Vector3D(x=-1, y=0, z=0)),
            ("left", Edge(lhs="left", rhs="bottom"), Vector3D(x=0, y=-1, z=0), Vector3D(x=0, y=0, z=-1)),
        ]
        
        for face, edge, expected_dir, expected_up in test_cases:
            orient = Orientation3D.of(face=face, edge=edge)
            
            # Check direction matches face normal
            assert orient.direction.x == expected_dir.x
            assert orient.direction.y == expected_dir.y
            assert orient.direction.z == expected_dir.z
            
            # Check up matches edge direction
            assert abs(orient.up.x - expected_up.x) < 1e-6
            assert abs(orient.up.y - expected_up.y) < 1e-6
            assert abs(orient.up.z - expected_up.z) < 1e-6
    
    def test_orientation_alignment_to_top(self):
        """Test that orientation aligns to TOP for non-top/bottom base faces."""
        from nichiyou_daiku.core.geometry import orientation_from_target_to_base_coords
        
        # Test case: base face is front (up should be TOP)
        target_edge = Edge(lhs="back", rhs="left")
        face, edge = orientation_from_target_to_base_coords(
            target_face="back",
            target_edge=target_edge,
            base_contact_face="front",
            target_contact_face="back"
        )
        
        # The resulting edge should produce up = TOP
        result_up = cross_face(edge.lhs, edge.rhs)
        assert result_up == "top", f"Expected up=top, got up={result_up}"
        
        # Test another case: base face is left
        target_edge2 = Edge(lhs="right", rhs="bottom")
        face2, edge2 = orientation_from_target_to_base_coords(
            target_face="right",
            target_edge=target_edge2,
            base_contact_face="left",
            target_contact_face="right"
        )
        
        result_up2 = cross_face(edge2.lhs, edge2.rhs)
        assert result_up2 == "top", f"Expected up=top, got up={result_up2}"