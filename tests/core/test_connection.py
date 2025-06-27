"""Tests for connection module."""

import pytest
from pydantic import ValidationError

from nichiyou_daiku.core.connection import (
    BasePosition,
    Anchor,
    Connection,
)
from nichiyou_daiku.core.geometry import Face, Edge, EdgePoint, FromMax, FromMin, Offset


class TestFromMax:
    """Test FromMax model."""

    # Basic creation and validation are covered in doctests

    def test_should_support_equality(self):
        """Should support equality comparison."""
        offset1 = FromMax(value=100.0)
        offset2 = FromMax(value=100.0)
        offset3 = FromMax(value=200.0)

        assert offset1 == offset2
        assert offset1 != offset3


class TestFromMin:
    """Test FromMin model."""

    # Basic creation, validation, and type comparison are covered in doctests
    # No additional tests needed as doctests cover all functionality


class TestOffset:
    """Test Offset type union."""

    def test_should_accept_from_max(self):
        """Offset should accept FromMax."""
        offset: Offset = FromMax(value=100.0)
        assert isinstance(offset, FromMax)
        assert offset.value == 100.0

    def test_should_accept_from_min(self):
        """Offset should accept FromMin."""
        offset: Offset = FromMin(value=200.0)
        assert isinstance(offset, FromMin)
        assert offset.value == 200.0


class TestBasePosition:
    """Test BasePosition model."""

    # Basic creation is covered in doctests

    def test_should_accept_only_side_faces(self):
        """Should accept only side faces (not top/bottom)."""
        valid_faces: list[Face] = ["left", "right", "front", "back"]
        invalid_faces: list[Face] = ["top", "bottom"]

        # Test valid faces
        for face in valid_faces:
            pos = BasePosition(face=face, offset=FromMax(value=10))
            assert pos.face == face
            
        # Test invalid faces raise error
        for face in invalid_faces:
            with pytest.raises(ValidationError):
                BasePosition(face=face, offset=FromMax(value=10))

    def test_should_accept_both_offset_types(self):
        """Should accept both FromMax and FromMin."""
        pos1 = BasePosition(face="front", offset=FromMax(value=100))
        pos2 = BasePosition(face="back", offset=FromMin(value=200))

        assert isinstance(pos1.offset, FromMax)
        assert isinstance(pos2.offset, FromMin)

    # Immutability test is covered in doctests


class TestEdgePoint:
    """Test EdgePoint model."""

    # Basic creation is covered in doctests

    def test_should_validate_edges(self):
        """Should accept valid edge combinations."""
        # Adjacent faces (valid edge)
        edge1 = EdgePoint(edge=Edge(lhs="top", rhs="front"), offset=FromMin(value=10))
        edge2 = EdgePoint(edge=Edge(lhs="left", rhs="bottom"), offset=FromMin(value=50))

        assert edge1.edge.lhs == "top" and edge1.edge.rhs == "front"
        assert edge2.edge.lhs == "left" and edge2.edge.rhs == "bottom"

    def test_should_validate_non_negative_value(self):
        """Should validate that value is non-negative."""
        # Valid value
        edge_point = EdgePoint(edge=Edge(lhs="front", rhs="right"), offset=FromMin(value=100))
        assert edge_point.offset.value == 100
        
        # Zero should now work
        edge_point_zero = EdgePoint(edge=Edge(lhs="front", rhs="right"), offset=FromMin(value=0))
        assert edge_point_zero.offset.value == 0

        # Negative values should fail
        with pytest.raises(ValidationError):
            EdgePoint(edge=Edge(lhs="front", rhs="right"), offset=FromMin(value=-50))


class TestTargetAnchor:
    """Test TargetAnchor model."""

    # Basic creation is covered in doctests

    def test_should_validate_nested_models(self):
        """Should validate nested EdgePoint model."""
        # Valid anchor
        anchor = Anchor(
            face="top", edge_point=EdgePoint(edge=Edge(lhs="top", rhs="left"), offset=FromMin(value=50))
        )
        assert anchor.edge_point.offset.value == 50

        # Invalid nested model should fail
        with pytest.raises(ValidationError):
            Anchor(
                face="top", edge_point=EdgePoint(edge=Edge(lhs="top", rhs="left"), offset=FromMin(value=-10))
            )


class TestConnection:
    """Test Connection model."""

    # Basic creation is covered in doctests

    def test_should_validate_nested_models(self):
        """Should validate all nested models."""
        # Valid connection
        conn = Connection.of(
            base=BasePosition(face="front", offset=FromMax(value=50)),
            target=Anchor(
                face="bottom",
                edge_point=EdgePoint(edge=Edge(lhs="bottom", rhs="front"), offset=FromMin(value=10)),
            ),
        )
        assert conn.base.edge_point.offset.value == 50

        # Invalid nested model should fail
        with pytest.raises(ValidationError):
            Connection.of(
                base=BasePosition(face="top", offset=FromMax(value=-10)),
                target=Anchor(
                    face="left",
                    edge_point=EdgePoint(edge=Edge(lhs="left", rhs="front"), offset=FromMin(value=10)),
                ),
            )

    def test_should_represent_complex_connections(self):
        """Should be able to represent various connection types."""
        # T-joint example
        t_joint = Connection.of(
            base=BasePosition(
                face="left",
                offset=FromMax(value=50),  # Center of side face
            ),
            target=Anchor(
                face="bottom",
                edge_point=EdgePoint(edge=Edge(lhs="bottom", rhs="front"), offset=FromMin(value=10)),
            ),
        )

        # L-angle example
        l_angle = Connection.of(
            base=BasePosition(
                face="front",
                offset=FromMax(value=25),  # End face
            ),
            target=Anchor(
                face="right",
                edge_point=EdgePoint(edge=Edge(lhs="right", rhs="bottom"), offset=FromMin(value=100)),
            ),
        )

        assert t_joint.base.face == "left"
        assert l_angle.base.face == "front"
