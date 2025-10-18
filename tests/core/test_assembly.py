"""Tests for assembly module."""

from nichiyou_daiku.core.assembly import (
    Joint,
    JointPair,
    Assembly,
)
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.connection import Connection, Anchor
from nichiyou_daiku.core.geometry import FromMax, FromMin
from nichiyou_daiku.core.geometry import (
    Point3D,
    Vector3D,
    Box,
    Orientation3D,
)


class TestBox:
    """Test Box model."""

    # Basic creation is covered in doctests

    def test_should_handle_different_piece_lengths(self):
        """Should create boxes with correct dimensions for different piece lengths."""
        from nichiyou_daiku.core.piece import get_shape

        lengths = [500.0, 1000.0, 2000.0]

        for length in lengths:
            piece = Piece.of(PieceType.PT_2x4, length)
            box = Box(shape=get_shape(piece))
            assert box.shape.length == length
            assert box.shape.width == 89.0
            assert box.shape.height == 38.0


class TestJoint:
    """Test Joint model."""

    # Basic creation is covered in doctests

    def test_should_support_negative_direction_vectors(self):
        """Should support joints with negative direction vectors."""
        position = Point3D(x=0.0, y=0.0, z=100.0)
        orientation = Orientation3D.of(
            direction=Vector3D(x=-1.0, y=0.0, z=0.0), up=Vector3D(x=0.0, y=0.0, z=1.0)
        )

        joint = Joint(id="test-joint", position=position, orientation=orientation)

        assert joint.orientation.direction.x == -1.0


class TestJointPair:
    """Test JointPair model."""

    # Basic creation is covered in doctests

    # JointPair.of() method is covered in doctests

    def test_should_represent_l_angle_connection(self):
        """Should be able to represent L-angle connection."""
        # Create pieces for L-angle
        horizontal = Piece.of(PieceType.PT_2x4, 400.0, "horizontal")
        vertical = Piece.of(PieceType.PT_2x4, 300.0, "vertical")

        # Create L-angle piece connection
        piece_conn = Connection(
            lhs=Anchor(
                contact_face="left", edge_shared_face="top", offset=FromMax(value=10)
            ),
            rhs=Anchor(
                contact_face="down",
                edge_shared_face="right",
                offset=FromMin(value=10),
            ),
        )

        # Create joint pair
        from nichiyou_daiku.core.piece import get_shape

        horizontal_box = Box(shape=get_shape(horizontal))
        vertical_box = Box(shape=get_shape(vertical))
        joint_pair = JointPair.of(horizontal_box, vertical_box, piece_conn)

        assert isinstance(joint_pair.lhs, Joint)
        assert isinstance(joint_pair.rhs, Joint)


class TestAssembly:
    """Test Assembly model."""

    # Basic creation is covered in doctests

    def test_should_create_assembly_with_joints(self):
        """Should create Assembly with a dict of joints."""
        from nichiyou_daiku.core.model import Model, PiecePair

        # Create pieces and connection
        p1 = Piece.of(PieceType.PT_2x4, 1000.0, "p1")
        p2 = Piece.of(PieceType.PT_2x4, 800.0, "p2")

        conn = Connection(
            lhs=Anchor(
                contact_face="front", edge_shared_face="top", offset=FromMax(value=100)
            ),
            rhs=Anchor(
                contact_face="down", edge_shared_face="front", offset=FromMin(value=50)
            ),
        )

        model = Model.of(
            pieces=[p1, p2],
            connections=[(PiecePair(base=p1, target=p2), conn)],
            label="test_assembly",
        )

        assembly = Assembly.of(model)

        # Each connection creates 2 joints (lhs and rhs)
        assert len(assembly.joints) == 2
        assert len(assembly.joint_pairs) == 1

        # Verify joints are Joint instances
        for joint_id, joint in assembly.joints.items():
            assert isinstance(joint, Joint)
            assert isinstance(joint_id, str)

        # Verify joint_pairs structure
        lhs_joint_id, rhs_joint_id = assembly.joint_pairs[0]
        assert lhs_joint_id in assembly.joints
        assert rhs_joint_id in assembly.joints

    def test_should_generate_pilot_holes_for_screw_connections(self):
        """Should generate pilot holes for screw-type connections."""
        from nichiyou_daiku.core.model import Model, PiecePair
        from nichiyou_daiku.core.connection import ConnectionType
        from nichiyou_daiku.core.assembly import Hole

        # Create pieces and screw connection
        p1 = Piece.of(PieceType.PT_2x4, 1000.0, "p1")
        p2 = Piece.of(PieceType.PT_2x4, 800.0, "p2")

        conn = Connection(
            lhs=Anchor(
                contact_face="front", edge_shared_face="top", offset=FromMax(value=100)
            ),
            rhs=Anchor(
                contact_face="down", edge_shared_face="front", offset=FromMin(value=50)
            ),
            type=ConnectionType.SCREW,
        )

        model = Model.of(
            pieces=[p1, p2], connections=[(PiecePair(base=p1, target=p2), conn)]
        )

        assembly = Assembly.of(model)

        # Verify pilot_holes structure: dict[str, Hole]
        assert isinstance(assembly.pilot_holes, dict)

        # For screw connections, pilot holes should be created for both joints
        assert len(assembly.pilot_holes) == 2

        # Verify that pilot holes map to joint IDs
        lhs_joint_id, rhs_joint_id = assembly.joint_pairs[0]
        assert lhs_joint_id in assembly.pilot_holes
        assert rhs_joint_id in assembly.pilot_holes

        # Verify Hole instances
        assert isinstance(assembly.pilot_holes[lhs_joint_id], Hole)
        assert isinstance(assembly.pilot_holes[rhs_joint_id], Hole)

    # Assembly.of() method is covered in doctests
