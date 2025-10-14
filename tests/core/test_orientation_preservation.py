"""Test that orientation is properly preserved through transformations."""

from nichiyou_daiku.core.assembly import (
    Assembly,
    Joint,
)
from nichiyou_daiku.core.connection import Connection, Anchor
from typing import cast
from nichiyou_daiku.core.geometry import (
    Point3D,
    Vector3D,
    Orientation3D,
    Edge,
    FromMax,
    FromMin,
    Face,
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
            up=Vector3D(x=0.0, y=1.0, z=0.0),  # Y up
        )
        joint = Joint(id="test-joint", position=Point3D(x=100, y=50, z=25), orientation=orientation)

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
        # LHS: left contact face with top edge shared face
        # RHS: right contact face with bottom edge shared face
        conn = Connection(
            lhs=Anchor(
                contact_face="left", edge_shared_face="top", offset=FromMax(value=100)
            ),
            rhs=Anchor(
                contact_face="right",
                edge_shared_face="down",
                offset=FromMin(value=50),
            ),
        )

        # Create model and assembly
        from nichiyou_daiku.core.model import PiecePair

        model = Model.of(
            pieces=[p1, p2], connections=[(PiecePair(base=p1, target=p2), conn)]
        )
        assembly = Assembly.of(model)

        # Get the joints from assembly
        # With new structure, joints are dict[str, Joint] and joint_pairs is list[tuple[str, str]]
        assert len(assembly.joint_pairs) == 1
        lhs_joint_id, rhs_joint_id = assembly.joint_pairs[0]

        # Check base joint
        base_joint = assembly.joints[lhs_joint_id]

        # Check target joint
        target_joint = assembly.joints[rhs_joint_id]

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

        # Connection 1: vertical front to horizontal bottom
        # This tests front-bottom contact with orientation preservation
        conn1 = Connection(
            lhs=Anchor(
                contact_face="front", edge_shared_face="top", offset=FromMax(value=50)
            ),
            rhs=Anchor(
                contact_face="down",
                edge_shared_face="front",
                offset=FromMin(value=100),
            ),
        )

        # Connection 2: horizontal right to brace left
        # This tests right-left contact with different orientations
        conn2 = Connection(
            lhs=Anchor(
                contact_face="right", edge_shared_face="top", offset=FromMax(value=200)
            ),
            rhs=Anchor(
                contact_face="left", edge_shared_face="top", offset=FromMin(value=150)
            ),
        )

        from nichiyou_daiku.core.model import PiecePair

        model = Model.of(
            pieces=[p1, p2, p3],
            connections=[
                (PiecePair(base=p1, target=p2), conn1),
                (PiecePair(base=p2, target=p3), conn2),
            ],
        )
        assembly = Assembly.of(model)

        # Verify all joints have proper orientations
        for joint_id, joint in assembly.joints.items():
            assert isinstance(joint.orientation, Orientation3D)

            # Check that direction vectors are unit vectors
            dir_vec = joint.orientation.direction
            dir_mag = (dir_vec.x**2 + dir_vec.y**2 + dir_vec.z**2) ** 0.5
            assert abs(dir_mag - 1.0) < 1e-6

            # Check that up vectors are unit vectors and orthogonal to direction
            up_vec = joint.orientation.up
            up_mag = (up_vec.x**2 + up_vec.y**2 + up_vec.z**2) ** 0.5
            assert abs(up_mag - 1.0) < 1e-6

            # Dot product should be ~0 for orthogonal vectors
            dot_product = dir_vec.x * up_vec.x + dir_vec.y * up_vec.y + dir_vec.z * up_vec.z
            assert abs(dot_product) < 1e-6

    def test_orientation_from_face_and_edge(self):
        """Test creating orientation from face and edge."""
        # Test various face/edge combinations
        test_cases = [
            (
                "top",
                Edge(lhs="top", rhs="front"),
                Vector3D(x=1, y=0, z=0),
                Vector3D(x=0, y=-1, z=0),
            ),
            (
                "front",
                Edge(lhs="front", rhs="right"),
                Vector3D(x=0, y=0, z=1),
                Vector3D(x=-1, y=0, z=0),
            ),
            (
                "left",
                Edge(lhs="left", rhs="down"),
                Vector3D(x=0, y=-1, z=0),
                Vector3D(x=0, y=0, z=-1),
            ),
        ]

        for face, edge, expected_dir, expected_up in test_cases:
            orient = Orientation3D.of(face=cast(Face, face), edge=edge)

            # Check direction matches face normal
            assert orient.direction.x == expected_dir.x
            assert orient.direction.y == expected_dir.y
            assert orient.direction.z == expected_dir.z

            # Check up matches edge direction
            assert abs(orient.up.x - expected_up.x) < 1e-6
            assert abs(orient.up.y - expected_up.y) < 1e-6
            assert abs(orient.up.z - expected_up.z) < 1e-6
