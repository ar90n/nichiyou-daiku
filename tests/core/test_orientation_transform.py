"""Tests for orientation transformation in connections."""

from nichiyou_daiku.core.anchor import Anchor
from nichiyou_daiku.core.connection import BoundAnchor, Connection
from nichiyou_daiku.core.geometry import (
    FromMax,
    FromMin,
)
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.model import Model


class TestOrientationTransform:
    """Test orientation preservation in connections."""

    def test_should_preserve_orientation_alignment(self):
        """Should preserve relative orientation when pieces connect."""
        # Create two pieces
        vertical = Piece.of(PieceType.PT_2x4, 600.0, "vertical")
        horizontal = Piece.of(PieceType.PT_2x4, 400.0, "horizontal")

        # Create connection - horizontal piece on side of vertical
        connection = Connection(
            base=BoundAnchor(
                piece=vertical,
                anchor=Anchor(
                    contact_face="left",
                    edge_shared_face="back",
                    offset=FromMax(value=1.0),
                ),
            ),
            target=BoundAnchor(
                piece=horizontal,
                anchor=Anchor(
                    contact_face="right",
                    edge_shared_face="back",
                    offset=FromMin(value=1.0),
                ),
            ),
        )

        # Build assembly
        model = Model.of(
            [vertical, horizontal],
            [connection],
        )
        assembly = Assembly.of(model)

        # Get joints from joint_conns
        lhs_joint_id, rhs_joint_id = assembly.joint_conns[0]
        joint1 = assembly.joints[lhs_joint_id]
        joint2 = assembly.joints[rhs_joint_id]

        # Verify face normals are opposite (base face normal = -target face normal)
        dir1 = joint1.orientation.direction
        dir2 = joint2.orientation.direction

        # They should point in opposite directions
        assert abs(dir1.x + dir2.x) < 1e-6
        assert abs(dir1.y + dir2.y) < 1e-6
        assert abs(dir1.z + dir2.z) < 1e-6

    def test_edge_alignment_in_connection(self):
        """Test that edges align properly in connections."""
        p1 = Piece.of(PieceType.PT_2x4, 1000.0, "p1")
        p2 = Piece.of(PieceType.PT_2x4, 1000.0, "p2")
        # Create connection where edges should align
        connection = Connection(
            base=BoundAnchor(
                piece=p1,
                anchor=Anchor(
                    contact_face="front",
                    edge_shared_face="left",
                    offset=FromMax(value=10),
                ),
            ),
            target=BoundAnchor(
                piece=p2,
                anchor=Anchor(
                    contact_face="back",
                    edge_shared_face="left",
                    offset=FromMin(value=10),
                ),
            ),
        )

        # Test that anchors have the expected values
        assert connection.base.anchor.contact_face == "front"
        assert connection.base.anchor.edge_shared_face == "left"
        assert connection.base.anchor.offset.value == 10

        assert connection.target.anchor.contact_face == "back"
        assert connection.target.anchor.edge_shared_face == "left"
        assert connection.target.anchor.offset.value == 10
