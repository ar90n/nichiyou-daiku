"""Model representation for woodworking projects.

This module provides the main Model class that represents a complete
woodworking project with pieces and their connections.
"""

from typing import Iterable

from pydantic import BaseModel

from nichiyou_daiku.core.piece import Piece
from nichiyou_daiku.core.connection import Connection


class Model(BaseModel, frozen=True):
    """Complete model of a woodworking project.

    Contains all pieces and their connections. Pieces are stored by ID
    for quick lookup. Connections are keyed by (base_id, target_id) tuples.

    Attributes:
        pieces: Dictionary mapping piece IDs to Piece objects
        connections: Dictionary mapping (base_id, target_id) to Connection objects

    Examples:
        >>> from nichiyou_daiku.core.piece import Piece, PieceType
        >>> from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
        >>> from nichiyou_daiku.core.connection import Connection
        >>> from nichiyou_daiku.core.geometry import FromMax, FromMin
        >>> # Create empty model
        >>> empty_model = Model(pieces={}, connections={})
        >>> len(empty_model.pieces)
        0
        >>> # Create model with pieces
        >>> p1 = Piece.of(PieceType.PT_2x4, 1000.0, "p1")
        >>> p2 = Piece.of(PieceType.PT_2x4, 800.0, "p2")
        >>> conn = Connection(
        ...     base=BoundAnchor(
        ...         piece=p1,
        ...         anchor=Anchor(
        ...             contact_face="front",
        ...             edge_shared_face="top",
        ...             offset=FromMax(value=100)
        ...         )
        ...     ),
        ...     target=BoundAnchor(
        ...         piece=p2,
        ...         anchor=Anchor(
        ...             contact_face="down",
        ...             edge_shared_face="front",
        ...             offset=FromMin(value=50)
        ...         )
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
    label: str | None = None

    @classmethod
    def of(
        cls,
        pieces: Iterable[Piece],
        connections: Iterable[Connection],
        label: str | None = None,
    ) -> "Model":
        """Create a Model instance from pieces and connections.

        Factory method that builds the internal dictionaries from iterables.

        Args:
            pieces: Iterable of Piece objects
            connections: Iterable of Connection objects

        Returns:
            New Model instance

        Examples:
            >>> from nichiyou_daiku.core.piece import Piece, PieceType
            >>> from nichiyou_daiku.core.anchor import Anchor, BoundAnchor
            >>> from nichiyou_daiku.core.connection import Connection
            >>> from nichiyou_daiku.core.geometry import FromMax, FromMin
            >>> piece1 = Piece.of(PieceType.PT_2x4, 1000.0, "piece-1")
            >>> piece2 = Piece.of(PieceType.PT_2x4, 800.0, "piece-2")
            >>> conn = Connection(
            ...     base=BoundAnchor(
            ...         piece=piece1,
            ...         anchor=Anchor(
            ...             contact_face="front",
            ...             edge_shared_face="top",
            ...             offset=FromMax(value=100)
            ...         )
            ...     ),
            ...     target=BoundAnchor(
            ...         piece=piece2,
            ...         anchor=Anchor(
            ...             contact_face="down",
            ...             edge_shared_face="front",
            ...             offset=FromMin(value=10)
            ...         )
            ...     )
            ... )
            >>> model = Model.of(
            ...     pieces=[piece1, piece2],
            ...     connections=[conn]
            ... )
            >>> len(model.pieces)
            2
            >>> ("piece-1", "piece-2") in model.connections
            True
        """
        pieces_dict = {piece.id: piece for piece in pieces}
        connections_dict = {
            (conn.base.piece.id, conn.target.piece.id): conn for conn in connections
        }

        # Validate that all connection pieces exist in pieces_dict
        for base_id, target_id in connections_dict:
            if base_id not in pieces_dict:
                raise ValueError(
                    f"Connection references unknown base piece: '{base_id}'"
                )
            if target_id not in pieces_dict:
                raise ValueError(
                    f"Connection references unknown target piece: '{target_id}'"
                )

        return cls(pieces=pieces_dict, connections=connections_dict, label=label)
