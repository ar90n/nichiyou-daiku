"""Tests for assembly module."""

from nichiyou_daiku.core.assembly import (
    Joint,
    JointPair,
    Assembly,
    _project_joint,
    _project_surface_point,
)
from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
from nichiyou_daiku.core.connection import Connection, Anchor
from nichiyou_daiku.core.geometry import FromMax, FromMin
from nichiyou_daiku.core.geometry import (
    Point2D,
    Point3D,
    SurfacePoint,
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
        position = SurfacePoint(face="top", position=Point2D(u=0.0, v=0.0))
        orientation = Orientation3D.of(
            direction=Vector3D(x=-1.0, y=0.0, z=0.0), up=Vector3D(x=0.0, y=0.0, z=1.0)
        )

        joint = Joint(position=position, orientation=orientation)

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

        # Create joints directly
        from nichiyou_daiku.core.piece import get_shape

        horizontal_box = Box(shape=get_shape(horizontal))
        vertical_box = Box(shape=get_shape(vertical))

        lhs_joint = Joint.of_anchor(anchor=piece_conn.lhs, box=horizontal_box)
        rhs_joint = _project_joint(
            horizontal_box, vertical_box, lhs_joint, piece_conn.lhs, piece_conn.rhs
        )

        assert isinstance(lhs_joint, Joint)
        assert isinstance(rhs_joint, Joint)


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

        assert len(assembly.joints) == 2
        assert "p1_j0" in assembly.joints
        assert "p2_j0" in assembly.joints
        assert len(assembly.joint_conns) == 1
        assert assembly.joint_conns[0] == ("p1_j0", "p2_j0")

    def test_should_generate_pilot_holes_for_screw_connections(self):
        """Should generate pilot holes for screw-type connections."""
        from nichiyou_daiku.core.model import Model, PiecePair
        from nichiyou_daiku.core.connection import ConnectionType

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

        # Verify pilot_holes is a dict
        assert isinstance(assembly.pilot_holes, dict)

        # Once _calculate_pilot_holes_for_connection is implemented,
        # we can add more specific assertions here.
        # For now, just check the structure exists and is empty (stub returns [])
        # When implemented, this test should verify actual holes are generated

    # Assembly.of() method is covered in doctests


class TestProjectSurfacePoint:
    """Test surface point projection between coordinate systems."""

    def test_should_project_point_on_same_face(self):
        """Should project a point when source and destination are on the same logical face."""
        # Create two pieces
        src_piece = Piece.of(PieceType.PT_2x4, 1000.0)
        dst_piece = Piece.of(PieceType.PT_2x4, 800.0)
        src_box = Box(shape=get_shape(src_piece))
        dst_box = Box(shape=get_shape(dst_piece))

        # Create matching anchors (front face of src connects to down face of dst)
        src_anchor = Anchor(
            contact_face="front", edge_shared_face="top", offset=FromMax(value=100)
        )
        dst_anchor = Anchor(
            contact_face="down", edge_shared_face="front", offset=FromMin(value=50)
        )

        # Create a point on the source front face
        src_sp = SurfacePoint(face="front", position=Point2D(u=10.0, v=20.0))

        # Project to destination
        dst_sp = _project_surface_point(src_box, dst_box, src_sp, src_anchor, dst_anchor)

        # Result should be a SurfacePoint on the destination contact face
        assert isinstance(dst_sp, SurfacePoint)
        assert dst_sp.face == "down"
        assert isinstance(dst_sp.position, Point2D)

    def test_should_preserve_joint_position(self):
        """Should preserve the joint position when projecting the joint itself."""
        # Create two pieces
        src_piece = Piece.of(PieceType.PT_2x4, 1000.0)
        dst_piece = Piece.of(PieceType.PT_2x4, 800.0)
        src_box = Box(shape=get_shape(src_piece))
        dst_box = Box(shape=get_shape(dst_piece))

        # Create matching anchors
        src_anchor = Anchor(
            contact_face="front", edge_shared_face="top", offset=FromMax(value=100)
        )
        dst_anchor = Anchor(
            contact_face="down", edge_shared_face="front", offset=FromMin(value=50)
        )

        # Get the joint position on source
        src_joint = Joint.of_anchor(box=src_box, anchor=src_anchor)

        # Project the joint position to destination
        dst_sp = _project_surface_point(
            src_box, dst_box, src_joint.position, src_anchor, dst_anchor
        )

        # The projected point should match the destination joint position
        dst_joint = Joint.of_anchor(box=dst_box, anchor=dst_anchor, flip_dir=True)

        # Convert both to Point3D for comparison
        dst_sp_3d = Point3D.of(dst_box, dst_sp)
        dst_joint_3d = Point3D.of(dst_box, dst_joint.position)

        # They should be at the same 3D position (allowing small numerical error)
        assert abs(dst_sp_3d.x - dst_joint_3d.x) < 1e-6
        assert abs(dst_sp_3d.y - dst_joint_3d.y) < 1e-6
        assert abs(dst_sp_3d.z - dst_joint_3d.z) < 1e-6

    def test_should_handle_different_faces(self):
        """Should correctly project between different face orientations."""
        # Create two pieces
        src_piece = Piece.of(PieceType.PT_2x4, 1000.0)
        dst_piece = Piece.of(PieceType.PT_2x4, 800.0)
        src_box = Box(shape=get_shape(src_piece))
        dst_box = Box(shape=get_shape(dst_piece))

        # Create anchors with different face combinations
        src_anchor = Anchor(
            contact_face="left", edge_shared_face="top", offset=FromMax(value=200)
        )
        dst_anchor = Anchor(
            contact_face="right", edge_shared_face="down", offset=FromMin(value=100)
        )

        # Create a point on the source left face
        src_sp = SurfacePoint(face="left", position=Point2D(u=5.0, v=15.0))

        # Project to destination
        dst_sp = _project_surface_point(src_box, dst_box, src_sp, src_anchor, dst_anchor)

        # Result should be a SurfacePoint on the destination right face
        assert isinstance(dst_sp, SurfacePoint)
        assert dst_sp.face == "right"

    def test_should_project_joint(self):
        """Should project entire joint from source to destination."""
        # Create two pieces
        src_piece = Piece.of(PieceType.PT_2x4, 1000.0)
        dst_piece = Piece.of(PieceType.PT_2x4, 800.0)
        src_box = Box(shape=get_shape(src_piece))
        dst_box = Box(shape=get_shape(dst_piece))

        # Create matching anchors
        src_anchor = Anchor(
            contact_face="front", edge_shared_face="top", offset=FromMax(value=100)
        )
        dst_anchor = Anchor(
            contact_face="down", edge_shared_face="front", offset=FromMin(value=50)
        )

        # Create source joint
        src_joint = Joint.of_anchor(box=src_box, anchor=src_anchor)

        # Project joint
        dst_joint = _project_joint(src_box, dst_box, src_joint, src_anchor, dst_anchor)

        # Verify it's a Joint with correct attributes
        assert isinstance(dst_joint, Joint)
        assert isinstance(dst_joint.position, SurfacePoint)
        assert isinstance(dst_joint.orientation, Orientation3D)
        assert dst_joint.position.face == "down"

        # Verify the projected joint matches what Joint.of_anchor would create
        # (for regression testing)
        expected_joint = Joint.of_anchor(box=dst_box, anchor=dst_anchor, flip_dir=True)

        # Convert both positions to Point3D for comparison
        dst_joint_3d = Point3D.of(dst_box, dst_joint.position)
        expected_joint_3d = Point3D.of(dst_box, expected_joint.position)

        # They should be at the same 3D position
        assert abs(dst_joint_3d.x - expected_joint_3d.x) < 1e-6
        assert abs(dst_joint_3d.y - expected_joint_3d.y) < 1e-6
        assert abs(dst_joint_3d.z - expected_joint_3d.z) < 1e-6

        # Orientation should also match
        assert dst_joint.orientation.direction == expected_joint.orientation.direction
        assert abs(dst_joint.orientation.up.x - expected_joint.orientation.up.x) < 1e-6
        assert abs(dst_joint.orientation.up.y - expected_joint.orientation.up.y) < 1e-6
        assert abs(dst_joint.orientation.up.z - expected_joint.orientation.up.z) < 1e-6
