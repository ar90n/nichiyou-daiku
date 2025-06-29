"""Tests for orientation transformation in connections."""

from nichiyou_daiku.core.connection import Connection, Anchor
from nichiyou_daiku.core.geometry import (
    FromMax,
    FromMin,
)
from nichiyou_daiku.core.assembly import Assembly
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
        connection = Connection(
            lhs=Anchor(
                contact_face="left", edge_shared_face="back", offset=FromMax(value=1.0)
            ),
            rhs=Anchor(
                contact_face="right", edge_shared_face="back", offset=FromMin(value=1.0)
            ),
        )

        # Build assembly
        model = Model.of(
            [vertical, horizontal],
            [(PiecePair(base=vertical, target=horizontal), connection)],
        )
        assembly = Assembly.of(model)

        # Get joints - pieces have default IDs p0, p1
        key = list(assembly.joints.keys())[0]
        joint1 = assembly.joints[key].lhs
        joint2 = assembly.joints[key].rhs

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
        connection = Connection(
            lhs=Anchor(
                contact_face="front", edge_shared_face="left", offset=FromMax(value=10)
            ),
            rhs=Anchor(
                contact_face="back", edge_shared_face="left", offset=FromMin(value=10)
            ),
        )

        # Test that anchors have the expected values
        assert connection.lhs.contact_face == "front"
        assert connection.lhs.edge_shared_face == "left"
        assert connection.lhs.offset.value == 10

        assert connection.rhs.contact_face == "back"
        assert connection.rhs.edge_shared_face == "left"
        assert connection.rhs.offset.value == 10
