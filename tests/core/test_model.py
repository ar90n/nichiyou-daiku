"""Tests for model module."""

import pytest
from pydantic import ValidationError

from nichiyou_daiku.core.model import PiecePair, Model
from nichiyou_daiku.core.piece import Piece, PieceType
from nichiyou_daiku.core.connection import (
    Connection,
    BasePosition,
    FromTopOffset,
    Anchor,
)
from nichiyou_daiku.core.geometry import Face, Edge, EdgePoint


class TestPiecePair:
    """Test PiecePair model."""

    # Basic creation is covered in doctests

    def test_should_support_same_piece_type(self):
        """Should support pairs with same piece types."""
        piece1 = Piece.of(PieceType.PT_2x4, 1000.0)
        piece2 = Piece.of(PieceType.PT_2x4, 1000.0)

        pair = PiecePair(base=piece1, target=piece2)

        assert pair.base.type == pair.target.type
        assert pair.base.id != pair.target.id  # Different pieces

    # Immutability is covered in doctests


class TestModel:
    """Test Model class."""

    # Basic creation is covered in doctests

    def test_should_create_model_with_pieces_and_connections(self):
        """Should create Model with pieces and connections dicts."""
        piece1 = Piece.of(PieceType.PT_2x4, 1000.0, "p1")
        piece2 = Piece.of(PieceType.PT_2x4, 800.0, "p2")

        conn = Connection.of(
            base=BasePosition(face="front", offset=FromTopOffset(value=10)),
            target=Anchor(
                face="bottom",
                edge_point=EdgePoint(edge=Edge(lhs="bottom", rhs="right"), value=10),
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

    def test_should_handle_duplicate_piece_ids(self):
        """Should handle duplicate piece IDs by overwriting."""
        piece1a = Piece.of(PieceType.PT_2x4, 1000.0, "same-id")
        piece1b = Piece.of(
            PieceType.PT_2x4, 2000.0, "same-id"
        )  # Same ID, different length

        model = Model.of(pieces=[piece1a, piece1b], connections=[])

        # Later piece should overwrite earlier one
        assert len(model.pieces) == 1
        assert model.pieces["same-id"].length == 2000.0

    def test_should_create_simple_l_angle_model(self):
        """Should create a model representing an L-angle joint."""
        # Create two pieces
        horizontal = Piece.of(PieceType.PT_2x4, 400.0, "horizontal")
        vertical = Piece.of(PieceType.PT_2x4, 300.0, "vertical")

        # Create L-angle connection
        l_angle_conn = Connection.of(
            base=BasePosition(face="front", offset=FromTopOffset(value=10)),
            target=Anchor(
                face="bottom",
                edge_point=EdgePoint(edge=Edge(lhs="bottom", rhs="right"), value=10),
            ),
        )

        # Create model
        model = Model.of(
            pieces=[horizontal, vertical],
            connections=[
                (PiecePair(base=horizontal, target=vertical), l_angle_conn)
            ],
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

        conn1 = Connection.of(
            base=BasePosition(face="left", offset=FromTopOffset(value=200)),
            target=Anchor(
                face="bottom",
                edge_point=EdgePoint(edge=Edge(lhs="bottom", rhs="front"), value=10),
            ),
        )

        conn2 = Connection.of(
            base=BasePosition(face="right", offset=FromTopOffset(value=800)),
            target=Anchor(
                face="bottom",
                edge_point=EdgePoint(edge=Edge(lhs="bottom", rhs="front"), value=10),
            ),
        )

        model = Model.of(
            pieces=[main, branch1, branch2],
            connections=[
                (PiecePair(base=main, target=branch1), conn1),
                (PiecePair(base=main, target=branch2), conn2),
            ],
        )

        assert len(model.pieces) == 3
        assert len(model.connections) == 2
        # Main piece has connections to both branches
        assert ("main", "branch1") in model.connections
        assert ("main", "branch2") in model.connections
