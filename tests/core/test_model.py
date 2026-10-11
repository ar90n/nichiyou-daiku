"""Tests for model module."""

import pytest

from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.anchor import Anchor
from nichiyou_daiku.core.anchor import BoundAnchor
from nichiyou_daiku.core.connection import Connection
from nichiyou_daiku.core.geometry import FromMax, FromMin


class TestModel:
    """Test Model class."""

    # Basic creation is covered in doctests

    def test_should_create_model_with_pieces_and_connections(self):
        """Should create Model with pieces and connections dicts."""
        piece1 = Piece.of(PieceType.PT_2x4, 1000.0, "p1")
        piece2 = Piece.of(PieceType.PT_2x4, 800.0, "p2")

        conn = Connection(
            base=BoundAnchor(
                piece=piece1,
                anchor=Anchor(
                    contact_face="front",
                    edge_shared_face="top",
                    offset=FromMax(value=10),
                ),
            ),
            target=BoundAnchor(
                piece=piece2,
                anchor=Anchor(
                    contact_face="down",
                    edge_shared_face="right",
                    offset=FromMin(value=10),
                ),
            ),
        )

        model = Model(
            pieces={"p1": piece1, "p2": piece2}, connections={("p1", "p2"): conn}
        )

        assert len(model.pieces) == 2
        assert model.pieces["p1"] == piece1
        assert model.pieces["p2"] == piece2
        assert len(model.connections) == 1
        assert model.connections[("p1", "p2")] == conn

    # Model.of() factory method is covered in doctests

    def test_should_create_simple_l_angle_model(self):
        """Should create a model representing an L-angle joint."""
        # Create two pieces
        horizontal = Piece.of(PieceType.PT_2x4, 400.0, "horizontal")
        vertical = Piece.of(PieceType.PT_2x4, 300.0, "vertical")

        # Create L-angle connection
        l_angle_conn = Connection(
            base=BoundAnchor(
                piece=horizontal,
                anchor=Anchor(
                    contact_face="front",
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

        # Create model
        model = Model.of(
            pieces=[horizontal, vertical],
            connections=[l_angle_conn],
        )

        assert len(model.pieces) == 2
        assert len(model.connections) == 1
        assert ("horizontal", "vertical") in model.connections

    def test_should_support_multiple_connections_per_piece(self):
        """Should support pieces with multiple connections."""
        # Create three pieces in a T configuration
        main = Piece.of(PieceType.PT_2x4, 1000.0, "main")
        branch1 = Piece.of(PieceType.PT_2x4, 300.0, "branch1")
        branch2 = Piece.of(PieceType.PT_2x4, 300.0, "branch2")

        conn1 = Connection(
            base=BoundAnchor(
                piece=main,
                anchor=Anchor(
                    contact_face="left",
                    edge_shared_face="top",
                    offset=FromMax(value=20),
                ),
            ),
            target=BoundAnchor(
                piece=branch1,
                anchor=Anchor(
                    contact_face="down",
                    edge_shared_face="front",
                    offset=FromMin(value=10),
                ),
            ),
        )

        conn2 = Connection(
            base=BoundAnchor(
                piece=main,
                anchor=Anchor(
                    contact_face="right",
                    edge_shared_face="top",
                    offset=FromMax(value=30),
                ),
            ),
            target=BoundAnchor(
                piece=branch2,
                anchor=Anchor(
                    contact_face="down",
                    edge_shared_face="front",
                    offset=FromMin(value=10),
                ),
            ),
        )

        model = Model.of(
            pieces=[main, branch1, branch2],
            connections=[conn1, conn2],
        )

        assert len(model.pieces) == 3
        assert len(model.connections) == 2
        # Main piece has connections to both branches
        assert ("main", "branch1") in model.connections
        assert ("main", "branch2") in model.connections


class TestModelValidation:
    """Test Model validation rules."""

    def test_should_raise_error_for_unknown_base_piece(self):
        """Should raise ValueError when connection references unknown base piece."""
        piece1 = Piece.of(PieceType.PT_2x4, 1000.0, "p1")
        piece2 = Piece.of(PieceType.PT_2x4, 800.0, "p2")
        unknown_piece = Piece.of(PieceType.PT_2x4, 500.0, "unknown")

        # Connection uses unknown_piece as base, but it's not in pieces list
        conn = Connection(
            base=BoundAnchor(
                piece=unknown_piece,
                anchor=Anchor(
                    contact_face="front",
                    edge_shared_face="top",
                    offset=FromMax(value=10),
                ),
            ),
            target=BoundAnchor(
                piece=piece2,
                anchor=Anchor(
                    contact_face="down",
                    edge_shared_face="right",
                    offset=FromMin(value=10),
                ),
            ),
        )

        with pytest.raises(ValueError, match="unknown base piece: 'unknown'"):
            Model.of(pieces=[piece1, piece2], connections=[conn])

    def test_should_raise_error_for_unknown_target_piece(self):
        """Should raise ValueError when connection references unknown target piece."""
        piece1 = Piece.of(PieceType.PT_2x4, 1000.0, "p1")
        piece2 = Piece.of(PieceType.PT_2x4, 800.0, "p2")
        unknown_piece = Piece.of(PieceType.PT_2x4, 500.0, "unknown")

        # Connection uses unknown_piece as target, but it's not in pieces list
        conn = Connection(
            base=BoundAnchor(
                piece=piece1,
                anchor=Anchor(
                    contact_face="front",
                    edge_shared_face="top",
                    offset=FromMax(value=10),
                ),
            ),
            target=BoundAnchor(
                piece=unknown_piece,
                anchor=Anchor(
                    contact_face="down",
                    edge_shared_face="right",
                    offset=FromMin(value=10),
                ),
            ),
        )

        with pytest.raises(ValueError, match="unknown target piece: 'unknown'"):
            Model.of(pieces=[piece1, piece2], connections=[conn])

    def test_should_accept_valid_connections(self):
        """Should accept connections that reference pieces in the model."""
        piece1 = Piece.of(PieceType.PT_2x4, 1000.0, "p1")
        piece2 = Piece.of(PieceType.PT_2x4, 800.0, "p2")

        conn = Connection(
            base=BoundAnchor(
                piece=piece1,
                anchor=Anchor(
                    contact_face="front",
                    edge_shared_face="top",
                    offset=FromMax(value=10),
                ),
            ),
            target=BoundAnchor(
                piece=piece2,
                anchor=Anchor(
                    contact_face="down",
                    edge_shared_face="right",
                    offset=FromMin(value=10),
                ),
            ),
        )

        # Should not raise
        model = Model.of(pieces=[piece1, piece2], connections=[conn])
        assert len(model.connections) == 1


class TestModelIntegrity:
    """Model.of must not silently drop or mix up pieces and connections."""

    @staticmethod
    def _conn(base: Piece, target: Piece, base_offset: float = 0.0) -> Connection:
        return Connection(
            base=BoundAnchor(
                piece=base,
                anchor=Anchor(
                    contact_face="front",
                    edge_shared_face="left",
                    offset=FromMin(value=base_offset),
                ),
            ),
            target=BoundAnchor(
                piece=target,
                anchor=Anchor(
                    contact_face="down",
                    edge_shared_face="front",
                    offset=FromMin(value=0),
                ),
            ),
        )

    def test_duplicate_connection_between_same_pair_is_rejected(self):
        a = Piece.of(PieceType.PT_2x4, 1000.0, "a")
        b = Piece.of(PieceType.PT_2x4, 500.0, "b")
        with pytest.raises(ValueError, match="Duplicate connection"):
            Model.of(
                pieces=[a, b], connections=[self._conn(a, b, 0), self._conn(a, b, 100)]
            )

    def test_connection_repeated_in_reverse_direction_is_rejected(self):
        a = Piece.of(PieceType.PT_2x4, 1000.0, "a")
        b = Piece.of(PieceType.PT_2x4, 500.0, "b")
        with pytest.raises(ValueError, match="Duplicate connection"):
            Model.of(pieces=[a, b], connections=[self._conn(a, b), self._conn(b, a)])

    def test_duplicate_piece_id_is_rejected(self):
        a1 = Piece.of(PieceType.PT_2x4, 1000.0, "a")
        a2 = Piece.of(PieceType.PT_2x4, 2000.0, "a")
        with pytest.raises(ValueError, match="Duplicate piece id"):
            Model.of(pieces=[a1, a2], connections=[])

    def test_connection_piece_must_match_model_piece(self):
        a = Piece.of(PieceType.PT_2x4, 1000.0, "a")
        b = Piece.of(PieceType.PT_2x4, 500.0, "b")
        stale_a = Piece.of(PieceType.PT_2x4, 2000.0, "a")
        with pytest.raises(ValueError, match="does not match"):
            Model.of(pieces=[a, b], connections=[self._conn(stale_a, b)])
