"""Tests for connection module."""

import pytest
from pydantic import ValidationError

from nichiyou_daiku.core.connection import (
    Anchor,
    Connection,
    ConnectionType,
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


class TestAnchor:
    """Test Anchor model."""

    # Basic creation is covered in doctests

    def test_should_accept_all_faces(self):
        """Should accept all face types."""
        all_faces: list[Face] = ["left", "right", "front", "back", "top", "down"]

        # Test all faces
        for contact_face in all_faces:
            for edge_shared_face in all_faces:
                if contact_face != edge_shared_face:
                    anchor = Anchor(
                        contact_face=contact_face,
                        edge_shared_face=edge_shared_face,
                        offset=FromMax(value=10),
                    )
                    assert anchor.contact_face == contact_face
                    assert anchor.edge_shared_face == edge_shared_face

    def test_should_accept_both_offset_types(self):
        """Should accept both FromMax and FromMin."""
        anchor1 = Anchor(
            contact_face="front", edge_shared_face="top", offset=FromMax(value=100)
        )
        anchor2 = Anchor(
            contact_face="back", edge_shared_face="down", offset=FromMin(value=200)
        )

        assert isinstance(anchor1.offset, FromMax)
        assert isinstance(anchor2.offset, FromMin)

    # Immutability test is covered in doctests


class TestEdgePoint:
    """Test EdgePoint model."""

    # Basic creation is covered in doctests

    def test_should_validate_edges(self):
        """Should accept valid edge combinations."""
        # Adjacent faces (valid edge)
        edge1 = EdgePoint(edge=Edge(lhs="top", rhs="front"), offset=FromMin(value=10))
        edge2 = EdgePoint(edge=Edge(lhs="left", rhs="down"), offset=FromMin(value=50))

        assert edge1.edge.lhs == "top" and edge1.edge.rhs == "front"
        assert edge2.edge.lhs == "left" and edge2.edge.rhs == "down"

    def test_should_validate_non_negative_value(self):
        """Should validate that value is non-negative."""
        # Valid value
        edge_point = EdgePoint(
            edge=Edge(lhs="front", rhs="right"), offset=FromMin(value=100)
        )
        assert edge_point.offset.value == 100

        # Zero should now work
        edge_point_zero = EdgePoint(
            edge=Edge(lhs="front", rhs="right"), offset=FromMin(value=0)
        )
        assert edge_point_zero.offset.value == 0

        # Negative values should fail
        with pytest.raises(ValidationError):
            EdgePoint(edge=Edge(lhs="front", rhs="right"), offset=FromMin(value=-50))


class TestAnchorValidation:
    """Test Anchor validation."""

    # Basic creation is covered in doctests

    def test_should_validate_offset_values(self):
        """Should validate offset values."""
        # Valid anchor
        anchor = Anchor(
            contact_face="top", edge_shared_face="left", offset=FromMin(value=50)
        )
        assert anchor.offset.value == 50

        # Invalid offset should fail
        with pytest.raises(ValidationError):
            Anchor(
                contact_face="top", edge_shared_face="left", offset=FromMin(value=-10)
            )


class TestConnectionType:
    """Test ConnectionType enum."""

    def test_should_have_screw_type(self):
        """Should have SCREW connection type."""
        assert ConnectionType.SCREW.value == "screw"

    def test_should_create_from_string(self):
        """Should create ConnectionType from string using of() method."""
        conn_type = ConnectionType.of("screw")
        assert conn_type == ConnectionType.SCREW
        assert conn_type.value == "screw"

    def test_should_raise_error_for_unsupported_type(self):
        """Should raise ValueError for unsupported connection type."""
        with pytest.raises(ValueError) as exc:
            ConnectionType.of("bolt")
        assert "Unsupported connection type: bolt" in str(exc.value)

    def test_should_support_equality(self):
        """Should support equality comparison."""
        type1 = ConnectionType.SCREW
        type2 = ConnectionType.of("screw")
        assert type1 == type2


class TestConnection:
    """Test Connection model."""

    # Basic creation is covered in doctests

    def test_should_validate_nested_models(self):
        """Should validate all nested models."""
        # Valid connection
        conn = Connection(
            lhs=Anchor(
                contact_face="front", edge_shared_face="top", offset=FromMax(value=50)
            ),
            rhs=Anchor(
                contact_face="down",
                edge_shared_face="front",
                offset=FromMin(value=10),
            ),
        )
        assert conn.lhs.offset.value == 50
        assert conn.rhs.offset.value == 10

        # Invalid nested model should fail
        with pytest.raises(ValidationError):
            Connection(
                lhs=Anchor(
                    contact_face="top",
                    edge_shared_face="left",
                    offset=FromMax(value=-10),
                ),
                rhs=Anchor(
                    contact_face="left",
                    edge_shared_face="front",
                    offset=FromMin(value=10),
                ),
            )

    def test_should_represent_complex_connections(self):
        """Should be able to represent various connection types."""
        # T-joint example
        t_joint = Connection(
            lhs=Anchor(
                contact_face="left",
                edge_shared_face="top",
                offset=FromMax(value=50),  # Center of side face
            ),
            rhs=Anchor(
                contact_face="down",
                edge_shared_face="front",
                offset=FromMin(value=10),
            ),
        )

        # L-angle example
        l_angle = Connection(
            lhs=Anchor(
                contact_face="front",
                edge_shared_face="top",
                offset=FromMax(value=25),  # End face
            ),
            rhs=Anchor(
                contact_face="right",
                edge_shared_face="down",
                offset=FromMin(value=100),
            ),
        )

        assert t_joint.lhs.contact_face == "left"
        assert l_angle.lhs.contact_face == "front"

    def test_should_have_default_type(self):
        """Should have default connection type of SCREW."""
        conn = Connection(
            lhs=Anchor(
                contact_face="front", edge_shared_face="top", offset=FromMax(value=50)
            ),
            rhs=Anchor(
                contact_face="down", edge_shared_face="front", offset=FromMin(value=10)
            ),
        )
        assert conn.type == ConnectionType.SCREW

    def test_should_accept_explicit_type(self):
        """Should accept explicitly specified connection type."""
        conn = Connection(
            lhs=Anchor(
                contact_face="front", edge_shared_face="top", offset=FromMax(value=50)
            ),
            rhs=Anchor(
                contact_face="down", edge_shared_face="front", offset=FromMin(value=10)
            ),
            type=ConnectionType.SCREW,
        )
        assert conn.type == ConnectionType.SCREW

    def test_should_serialize_with_type(self):
        """Should serialize Connection including type field."""
        conn = Connection(
            lhs=Anchor(
                contact_face="front", edge_shared_face="top", offset=FromMax(value=50)
            ),
            rhs=Anchor(
                contact_face="down", edge_shared_face="front", offset=FromMin(value=10)
            ),
        )
        data = conn.model_dump()
        assert "type" in data
        assert data["type"] == ConnectionType.SCREW
