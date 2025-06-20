"""Model representation for woodworking projects.

This module provides the main Model class that represents a complete
woodworking project with pieces and their connections.
"""

from typing import Iterable

from pydantic import BaseModel

from nichiyou_daiku.core.piece import Piece
from nichiyou_daiku.core.connection import Connection


class BaseTargetPair(BaseModel, frozen=True):
    """A pair of pieces in a connection relationship.

    Represents which piece is the base and which is the target
    in a connection.

    Attributes:
        base: The base piece (stays fixed)
        target: The target piece (attaches to base)

    Examples:
        >>> from nichiyou_daiku.core.piece import Piece, PieceType
        >>> base = Piece.of(PieceType.PT_2x4, 1000.0, "base-1")
        >>> target = Piece.of(PieceType.PT_2x4, 800.0, "target-1")
        >>> pair = BaseTargetPair(base=base, target=target)
        >>> pair.base.id
        'base-1'
        >>> pair.target.id
        'target-1'
    """

    base: Piece
    target: Piece


class Model(BaseModel, frozen=True):
    """Complete model of a woodworking project.

    Contains all pieces and their connections. Pieces are stored by ID
    for quick lookup. Connections are keyed by (base_id, target_id) tuples.

    Attributes:
        pieces: Dictionary mapping piece IDs to Piece objects
        connections: Dictionary mapping (base_id, target_id) to Connection objects

    Examples:
        >>> from nichiyou_daiku.core.piece import Piece, PieceType
        >>> from nichiyou_daiku.core.connection import (
        ...     Connection, BasePosition, FromTopOffset,
        ...     TargetAnchor, EdgePosition
        ... )
        >>> # Create empty model
        >>> empty_model = Model(pieces={}, connections={})
        >>> len(empty_model.pieces)
        0
        >>> # Create model with pieces
        >>> p1 = Piece.of(PieceType.PT_2x4, 1000.0, "p1")
        >>> p2 = Piece.of(PieceType.PT_2x4, 800.0, "p2")
        >>> conn = Connection(
        ...     base_pos=BasePosition(face="top", offset=FromTopOffset(value=100)),
        ...     target_anchor=TargetAnchor(
        ...         face="bottom",
        ...         edge_position=EdgePosition(src="bottom", dst="front", value=50)
        ...     )
        ... )
        >>> model = Model(
        ...     pieces={"p1": p1, "p2": p2},
        ...     connections={("p1", "p2"): conn}
        ... )
        >>> model.pieces["p1"].length
        1000.0
        >>> ("p1", "p2") in model.connections
        True
    """

    pieces: dict[str, Piece]
    connections: dict[tuple[str, str], Connection]

    @classmethod
    def of(
        cls,
        pieces: Iterable[Piece],
        connections: Iterable[tuple[BaseTargetPair, Connection]],
    ) -> "Model":
        """Create a Model instance from pieces and connections.

        Factory method that builds the internal dictionaries from iterables.

        Args:
            pieces: Iterable of Piece objects
            connections: Iterable of (BaseTargetPair, Connection) tuples

        Returns:
            New Model instance

        Examples:
            >>> from nichiyou_daiku.core.piece import Piece, PieceType
            >>> from nichiyou_daiku.core.connection import (
            ...     Connection, BasePosition, FromTopOffset,
            ...     TargetAnchor, EdgePosition
            ... )
            >>> piece1 = Piece.of(PieceType.PT_2x4, 1000.0, "piece-1")
            >>> piece2 = Piece.of(PieceType.PT_2x4, 800.0, "piece-2")
            >>> conn = Connection(
            ...     base_pos=BasePosition(face="top", offset=FromTopOffset(value=100)),
            ...     target_anchor=TargetAnchor(
            ...         face="bottom",
            ...         edge_position=EdgePosition(src="bottom", dst="front", value=10)
            ...     )
            ... )
            >>> model = Model.of(
            ...     pieces=[piece1, piece2],
            ...     connections=[
            ...         (BaseTargetPair(base=piece1, target=piece2), conn)
            ...     ]
            ... )
            >>> len(model.pieces)
            2
            >>> ("piece-1", "piece-2") in model.connections
            True
        """
        pieces_dict = {piece.id: piece for piece in pieces}
        connections_dict = {
            (pair.base.id, pair.target.id): conn for pair, conn in connections
        }
        return cls(pieces=pieces_dict, connections=connections_dict)
