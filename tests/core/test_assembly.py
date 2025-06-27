"""Tests for assembly module."""


from nichiyou_daiku.core.assembly import (
    Joint,
    JointConnection,
    Assembly,
)
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.connection import (
    Connection,
    BasePosition,
    Anchor,
)
from nichiyou_daiku.core.geometry import FromMax, FromMin
from nichiyou_daiku.core.model import Model, PiecePair
from nichiyou_daiku.core.geometry import Shape3D, Point3D, Vector3D, Face, Edge, EdgePoint, Box, Orientation3D


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
            direction=Vector3D(x=-1.0, y=0.0, z=0.0),
            up=Vector3D(x=0.0, y=0.0, z=1.0)
        )

        joint = Joint(position=position, orientation=orientation)

        assert joint.orientation.direction.x == -1.0


class TestConnection:
    """Test Connection model."""

    # Basic creation is covered in doctests

    # Connection.of() method is covered in doctests

    def test_should_represent_l_angle_connection(self):
        """Should be able to represent L-angle connection."""
        # Create pieces for L-angle
        horizontal = Piece.of(PieceType.PT_2x4, 400.0, "horizontal")
        vertical = Piece.of(PieceType.PT_2x4, 300.0, "vertical")

        # Create L-angle piece connection with supported face
        piece_conn = Connection.of(
            base=BasePosition(face="left", offset=FromMax(value=10)),
            target=Anchor(
                face="bottom",
                edge_point=EdgePoint(edge=Edge(lhs="bottom", rhs="right"), offset=FromMin(value=10)),
            ),
        )

        # Create connection
        from nichiyou_daiku.core.piece import get_shape
        horizontal_box = Box(shape=get_shape(horizontal))
        vertical_box = Box(shape=get_shape(vertical))
        connection = JointConnection.of(horizontal_box, vertical_box, piece_conn)

        assert isinstance(connection.joint1, Joint)
        assert isinstance(connection.joint2, Joint)


class TestAssembly:
    """Test Assembly model."""

    # Basic creation is covered in doctests

    def test_should_create_assembly_with_connections(self):
        """Should create Assembly with a dict of connections."""
        # Create a simple connection
        box1 = Box(shape=Shape3D(width=38.0, height=89.0, length=1000.0))
        joint1 = Joint(
            position=Point3D(x=0, y=0, z=0), 
            orientation=Orientation3D.of(
                direction=Vector3D(x=0, y=0, z=1),
                up=Vector3D(x=0, y=1, z=0)
            )
        )

        box2 = Box(shape=Shape3D(width=38.0, height=89.0, length=800.0))
        joint2 = Joint(
            position=Point3D(x=100, y=0, z=0),
            orientation=Orientation3D.of(
                direction=Vector3D(x=0, y=0, z=-1),
                up=Vector3D(x=0, y=1, z=0)
            )
        )

        connection = JointConnection(joint1=joint1, joint2=joint2)

        assembly = Assembly(
            label="test_assembly",
            boxes={"p1": box1, "p2": box2},
            connections={("p1", "p2"): connection}
        )

        assert len(assembly.connections) == 1
        assert assembly.connections[("p1", "p2")] == connection

    # Assembly.of() method is covered in doctests


