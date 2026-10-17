"""Model representation for woodworking projects.

This module provides the main Model class that represents a complete
woodworking project with pieces and their connections.
"""

from difflib import get_close_matches
from typing import Iterable

from pydantic import BaseModel

from nichiyou_daiku.core.piece import Piece
from nichiyou_daiku.core.connection import Connection


class Step(BaseModel, frozen=True):
    """An assembly step: the pieces added in it, and a name for its heading."""

    name: str
    pieces: tuple[str, ...]


def connected_parts(
    pieces: Iterable[str], pairs: Iterable[tuple[str, str]]
) -> list[frozenset[str]]:
    """The pieces grouped by the pairs that join them; pairs naming other
    pieces are ignored.

    Examples:
        >>> sorted(sorted(part) for part in connected_parts("abc", [("a", "b")]))
        [['a', 'b'], ['c']]
    """
    parent = {piece: piece for piece in pieces}

    def root(piece: str) -> str:
        while parent[piece] != piece:
            piece = parent[piece]
        return piece

    for a, b in pairs:
        if a in parent and b in parent:
            parent[root(a)] = root(b)
    parts: dict[str, set[str]] = {}
    for piece in parent:
        parts.setdefault(root(piece), set()).add(piece)
    return [frozenset(part) for part in parts.values()]


def _check_steps(
    pieces: dict[str, Piece],
    pairs: list[tuple[str, str]],
    steps: tuple[Step, ...],
) -> None:
    """Raise what is wrong with the steps and how to fix it."""
    # A step's number, not its name, tells it apart: names may repeat
    step_of: dict[str, int] = {}
    for number, step in enumerate(steps, 1):
        if not step.pieces:
            raise ValueError(f"Step '{step.name}' adds no pieces; name at least one")
        for piece_id in step.pieces:
            if piece_id not in pieces:
                close = get_close_matches(piece_id, pieces, n=1)
                hint = f"; did you mean '{close[0]}'?" if close else ""
                raise ValueError(
                    f"Step '{step.name}' names unknown piece '{piece_id}'{hint}"
                )
            if piece_id in step_of:
                first = step_of[piece_id]
                if first == number:
                    where = f"twice in step '{step.name}'"
                elif steps[first - 1].name == step.name:
                    where = f"in steps {first} and {number}, both named '{step.name}'"
                else:
                    where = f"in steps '{steps[first - 1].name}' and '{step.name}'"
                raise ValueError(f"'{piece_id}' is {where}; keep it in one step")
            step_of[piece_id] = number
    missing = [piece_id for piece_id in pieces if piece_id not in step_of]
    if missing:
        them = "it" if len(missing) == 1 else "them"
        raise ValueError(f"steps leaves out {', '.join(missing)}; add {them} to a step")
    placed: list[str] = []
    for step in steps:
        placed += step.pieces
        parts = [
            part for part in connected_parts(placed, pairs) if part & set(step.pieces)
        ]
        if len(parts) > 1:
            raise ValueError(
                f"Step '{step.name}' leaves its pieces in {len(parts)} separate "
                "parts: split it into steps or connect the parts"
            )


class Model(BaseModel, frozen=True):
    """Complete model of a woodworking project.

    Contains all pieces and their connections. Pieces are stored by ID
    for quick lookup. Connections are keyed by (base_id, target_id) tuples.

    Attributes:
        pieces: Dictionary mapping piece IDs to Piece objects
        connections: Dictionary mapping (base_id, target_id) to Connection objects
        steps: The assembly steps in order; empty when none are declared

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
        ...             offset=FromMax(value=10)
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
    steps: tuple[Step, ...] = ()

    @property
    def has_unknowns(self) -> bool:
        """Whether some length or offset is left for the connections to fix."""
        return any(piece.length is None for piece in self.pieces.values()) or any(
            connection.base.anchor.offset is None
            for connection in self.connections.values()
        )

    @classmethod
    def of(
        cls,
        pieces: Iterable[Piece],
        connections: Iterable[Connection],
        label: str | None = None,
        steps: Iterable[Step] = (),
    ) -> "Model":
        """Create a Model instance from pieces and connections.

        Factory method that builds the internal dictionaries from iterables.

        Args:
            pieces: Iterable of Piece objects
            connections: Iterable of Connection objects
            label: Name of the model
            steps: Assembly steps; when given, every piece is in exactly one
                and no step leaves its pieces in separate parts

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
            ...             offset=FromMax(value=10)
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
        pieces_dict: dict[str, Piece] = {}
        for piece in pieces:
            if piece.id in pieces_dict:
                raise ValueError(f"Duplicate piece id: '{piece.id}'")
            pieces_dict[piece.id] = piece

        connections_dict: dict[tuple[str, str], Connection] = {}
        for conn in connections:
            for role, bound in (("base", conn.base), ("target", conn.target)):
                known = pieces_dict.get(bound.piece.id)
                if known is None:
                    raise ValueError(
                        f"Connection references unknown {role} piece: '{bound.piece.id}'"
                    )
                if known != bound.piece:
                    raise ValueError(
                        f"Connection {role} piece '{bound.piece.id}' does not match "
                        f"the model's piece with the same id"
                    )
            key = (conn.base.piece.id, conn.target.piece.id)
            # Connections are keyed by piece pair, so a second one (in either
            # direction) would silently replace or duplicate the first.
            if key in connections_dict or key[::-1] in connections_dict:
                raise ValueError(
                    f"Duplicate connection between '{key[0]}' and '{key[1]}': "
                    "only one connection per piece pair is supported"
                )
            connections_dict[key] = conn

        steps = tuple(steps)
        if steps:
            _check_steps(pieces_dict, list(connections_dict), steps)
        return cls(
            pieces=pieces_dict, connections=connections_dict, label=label, steps=steps
        )
