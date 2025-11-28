"""Tests for assembly module."""

import pytest

from nichiyou_daiku.core.assembly import (
    Joint,
    Assembly,
    project_joint,
)
from nichiyou_daiku.core.piece import Piece, PieceType, get_shape
from nichiyou_daiku.core.anchor import Anchor
from nichiyou_daiku.core.connection import (
    BoundAnchor,
    Connection,
    VanillaConnection,
    DowelConnection,
)
from nichiyou_daiku.core.geometry import FromMax, FromMin
from nichiyou_daiku.core.geometry import (
    Point2D,
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
            base=BoundAnchor(
                piece=horizontal,
                anchor=Anchor(
                    contact_face="left",
                    edge_shared_face="top",
                    offset=FromMax(value=10),
                ),
            ),
            target=BoundAnchor(
                piece=vertical,
                anchor=Anchor(
                    contact_face="down",
                    edge_shared_face="right",
                    offset=FromMin(value=10),
                ),
            ),
        )

        # Create joints directly
        horizontal_box = Box(shape=get_shape(horizontal))
        vertical_box = Box(shape=get_shape(vertical))

        base_joint = Joint.of_anchor(anchor=piece_conn.base.anchor, box=horizontal_box)
        target_joint = project_joint(
            horizontal_box,
            vertical_box,
            base_joint,
            piece_conn.base.anchor,
            piece_conn.target.anchor,
        )

        assert isinstance(base_joint, Joint)
        assert isinstance(target_joint, Joint)


class TestAssembly:
    """Test Assembly model."""

    # Basic creation is covered in doctests

    def test_should_create_assembly_with_joints(self):
        """Should create Assembly with a dict of joints."""
        from nichiyou_daiku.core.model import Model

        # Create pieces and connection
        p1 = Piece.of(PieceType.PT_2x4, 1000.0, "p1")
        p2 = Piece.of(PieceType.PT_2x4, 800.0, "p2")

        conn = Connection(
            base=BoundAnchor(
                piece=p1,
                anchor=Anchor(
                    contact_face="front",
                    edge_shared_face="top",
                    offset=FromMax(value=100),
                ),
            ),
            target=BoundAnchor(
                piece=p2,
                anchor=Anchor(
                    contact_face="down",
                    edge_shared_face="front",
                    offset=FromMin(value=50),
                ),
            ),
        )

        model = Model.of(
            pieces=[p1, p2],
            connections=[conn],
            label="test_assembly",
        )

        assembly = Assembly.of(model)

        # VANILLA connections create 1 JointPair (2 joints) at anchor positions
        assert len(assembly.joints) == 2
        assert "p1_j0" in assembly.joints
        assert "p2_j0" in assembly.joints
        assert len(assembly.joint_conns) == 1
        assert assembly.joint_conns[0] == ("p1_j0", "p2_j0")

    def test_should_generate_pilot_holes_for_dowel_connections(self):
        """Should generate pilot holes for dowel-type connections."""
        from nichiyou_daiku.core.model import Model

        # Create pieces and dowel connection
        p1 = Piece.of(PieceType.PT_2x4, 1000.0, "p1")
        p2 = Piece.of(PieceType.PT_2x4, 800.0, "p2")

        conn = Connection(
            base=BoundAnchor(
                piece=p1,
                anchor=Anchor(
                    contact_face="front",
                    edge_shared_face="top",
                    offset=FromMax(value=100),
                ),
            ),
            target=BoundAnchor(
                piece=p2,
                anchor=Anchor(
                    contact_face="down",
                    edge_shared_face="front",
                    offset=FromMin(value=50),
                ),
            ),
            type=DowelConnection(radius=4.0, depth=20.0),
        )

        model = Model.of(pieces=[p1, p2], connections=[conn])

        assembly = Assembly.of(model)

        # Verify pilot_holes is a dict
        assert isinstance(assembly.pilot_holes, dict)

        # Once _calculate_pilot_holes_for_connection is implemented,
        # we can add more specific assertions here.
        # For now, just check the structure exists and is empty (stub returns [])
        # When implemented, this test should verify actual holes are generated

    # Assembly.of() method is covered in doctests


class TestDowelJointFaceCombinations:
    """Test dowel joint implementation for all face combinations."""

    @pytest.mark.parametrize(
        "connection_type",
        [
            VanillaConnection(),
            DowelConnection(radius=4.0, depth=20.0),
        ],
    )
    @pytest.mark.parametrize(
        "base_face,base_edge,target_face,target_edge,description",
        [
            # Top/down combinations
            ("top", "front", "down", "front", "top-down"),
            ("down", "back", "top", "back", "down-top"),
            # Top/down with left/right
            ("top", "front", "left", "top", "top-left"),
            ("down", "back", "right", "down", "down-right"),
            ("left", "top", "down", "front", "left-down"),
            ("right", "top", "top", "front", "right-top"),
            # Top/down with front/back
            ("top", "left", "front", "top", "top-front"),
            ("down", "right", "back", "down", "down-back"),
            # Left/right with front/back
            ("left", "front", "front", "left", "left-front"),
            ("right", "back", "back", "right", "right-back"),
            # Front/back with top/down edges
            ("front", "top", "back", "down", "front-back-topdown"),
        ],
    )
    def test_should_create_joints_for_face_combination(
        self,
        connection_type,
        base_face,
        base_edge,
        target_face,
        target_edge,
        description,
    ):
        """Should create correct number of joints for all valid face combinations."""
        # Create pieces
        p1 = Piece.of(PieceType.PT_2x4, 1000.0, "p1")
        p2 = Piece.of(PieceType.PT_2x4, 800.0, "p2")

        # Create connection
        conn = Connection(
            base=BoundAnchor(
                piece=p1,
                anchor=Anchor(
                    contact_face=base_face,
                    edge_shared_face=base_edge,
                    offset=FromMax(value=100),
                ),
            ),
            target=BoundAnchor(
                piece=p2,
                anchor=Anchor(
                    contact_face=target_face,
                    edge_shared_face=target_edge,
                    offset=FromMin(value=50),
                ),
            ),
            type=connection_type,
        )

        # Create model and assembly
        from nichiyou_daiku.core.model import Model

        model = Model.of(
            pieces=[p1, p2],
            connections=[conn],
            label=f"test_{description}_{connection_type.__class__.__name__}",
        )
        assembly = Assembly.of(model)

        # Verify joints were created based on connection type
        # DOWEL creates 2 joint pairs (4 joints), VANILLA creates 1 joint pair (2 joints)
        if isinstance(connection_type, DowelConnection):
            expected_joints = 4
            expected_pairs = 2
        else:  # VANILLA
            expected_joints = 2
            expected_pairs = 1

        assert len(assembly.joints) == expected_joints, (
            f"Expected {expected_joints} joints for {description} with {connection_type.__class__.__name__}"
        )
        assert len(assembly.joint_conns) == expected_pairs, (
            f"Expected {expected_pairs} joint pairs for {description} with {connection_type.__class__.__name__}"
        )

        # Verify joint IDs
        assert "p1_j0" in assembly.joints
        assert "p2_j0" in assembly.joints
        if isinstance(connection_type, DowelConnection):
            assert "p1_j1" in assembly.joints
            assert "p2_j1" in assembly.joints
