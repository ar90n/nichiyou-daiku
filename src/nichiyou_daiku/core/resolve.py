"""Fix unknown lengths and offsets from the connections.

A piece may leave its length unknown, and a connection may leave its offset
unknown so that the two pieces slide along the shared edge. Resolving solves
the model's positions with those unknowns left free and returns a model in
which every length and offset is a number, so placement, fasteners and
reports work as usual.
"""

import numpy as np
from pydantic import ValidationError

from .anchor import Anchor, BoundAnchor, as_edge_point, as_point_3d
from .connection import Connection
from .geometry import Box, FromMin, edge_length_of
from .model import Model
from .piece import Piece, get_shape
from .placement import (
    AXES,
    TOLERANCE_MM,
    PositionSolution,
    edge_axis,
    face_normal,
    round_mm,
    solve_positions,
)


class ResolutionError(ValueError):
    """Unknowns that the connections leave open or fix to impossible values.

    ``piece_id`` or ``connection`` (base_id, target_id) names the culprit.
    """

    def __init__(
        self,
        message: str,
        *,
        piece_id: str | None = None,
        connection: tuple[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.piece_id = piece_id
        self.connection = connection


def resolve_model(model: Model) -> Model:
    """The model with every unknown length and offset fixed by the connections.

    Returns ``model`` itself when it has no unknowns.

    Raises:
        ResolutionError: If a length or position is not fixed, a length would
            not be positive, two sliding pieces do not meet along their edge,
            or a check fails on the solved values (e.g. an offset longer than
            the solved length)
    """
    if not model.has_unknowns:
        return model
    solution = solve_positions(model)
    pieces = {
        piece_id: piece
        if piece.length is not None
        else Piece(id=piece_id, type=piece.type, length=_solved_length(piece, solution))
        for piece_id, piece in model.pieces.items()
    }
    _check_positions_fixed(model, solution)

    conflicted = {(c.base_id, c.target_id): c.kind for c in solution.conflicts}
    connections = []
    for key, connection in model.connections.items():
        base, target = connection.base.anchor, connection.target.anchor
        if base.offset is None:
            if conflicted.get(key) == "rotation":
                # The connection does not hold at all; any valid offset will do
                offsets = (FromMin(value=0), FromMin(value=0))
            else:
                # A conflicting sliding connection still takes the position the
                # rest of the model gives it, so only its real conflict remains
                offsets = _sliding_offsets(
                    connection, pieces, solution, must_meet=key not in conflicted
                )
            base = Anchor.of(base.contact_face, base.edge_shared_face, offsets[0])
            target = Anchor.of(target.contact_face, target.edge_shared_face, offsets[1])
        try:
            connections.append(
                Connection(
                    base=BoundAnchor(piece=pieces[key[0]], anchor=base),
                    target=BoundAnchor(piece=pieces[key[1]], anchor=target),
                    type=connection.type,
                )
            )
        except ValidationError as error:
            raise ResolutionError(_messages(error), connection=key) from error
    return Model.of(
        pieces=list(pieces.values()),
        connections=connections,
        label=model.label,
        steps=model.steps,
    )


def _messages(error: ValidationError) -> str:
    return "; ".join(
        str(detail.get("ctx", {}).get("error", detail["msg"]))
        for detail in error.errors()
    )


def _solved_length(piece: Piece, solution: PositionSolution) -> float:
    index, sign = solution.length_axis[piece.id]
    offsets = solution.offsets[AXES[index]]
    down_root, down = offsets.find((piece.id, "down"))
    top_root, top = offsets.find((piece.id, "top"))
    if down_root != top_root:
        raise ResolutionError(
            f"The length of '{piece.id}' is not fixed by its connections",
            piece_id=piece.id,
        )
    length = round_mm(sign * (top - down))
    if length <= TOLERANCE_MM:
        raise ResolutionError(
            f"The connections make '{piece.id}' {length:g}mm long; "
            "a piece needs a positive length",
            piece_id=piece.id,
        )
    return length


def _check_positions_fixed(model: Model, solution: PositionSolution) -> None:
    """Every piece must sit at a fixed place relative to its group."""
    for group in solution.groups:
        root = group[0]
        for member in group[1:]:
            for axis in AXES:
                offsets = solution.offsets[axis]
                if offsets.find((member, "down"))[0] != offsets.find((root, "down"))[0]:
                    sliding = [
                        f"{base_id} -> {target_id}"
                        for (
                            base_id,
                            target_id,
                        ), connection in model.connections.items()
                        if member in (base_id, target_id)
                        and connection.base.anchor.offset is None
                    ]
                    held_by = (
                        f"its connections with unknown offsets ({', '.join(sliding)})"
                        if sliding
                        else "connections with unknown offsets (?)"
                    )
                    raise ResolutionError(
                        f"'{member}' can slide along {axis} (axes of '{root}'): "
                        f"{held_by} leave its position open",
                        piece_id=member,
                    )


def _sliding_offsets(
    connection: Connection,
    pieces: dict[str, Piece],
    solution: PositionSolution,
    must_meet: bool,
) -> tuple[FromMin, FromMin]:
    """Offsets that put both anchors where the two edges overlap.

    Of the overlap, the point closest to the start of the base's edge is
    taken, so the base offset is as small as it can be.
    """
    base_id, target_id = connection.base.piece.id, connection.target.piece.id
    axis = edge_axis(solution.rotation[base_id], connection.base)
    spans = [
        _edge_span(pieces[piece_id], anchor, solution, axis)
        for piece_id, anchor in (
            (base_id, connection.base.anchor),
            (target_id, connection.target.anchor),
        )
    ]
    low = max(
        min(start, start + direction * length) for start, direction, length in spans
    )
    high = min(
        max(start, start + direction * length) for start, direction, length in spans
    )
    if must_meet and high < low - TOLERANCE_MM:
        raise ResolutionError(
            f"'{base_id}' and '{target_id}' slide along a shared edge (?) but "
            "their edges do not meet",
            connection=(base_id, target_id),
        )
    point = low if spans[0][1] > 0 else high
    base_offset, target_offset = (
        min(max(round_mm((point - start) * direction), 0.0), length)
        for start, direction, length in spans
    )
    return FromMin(value=base_offset), FromMin(value=target_offset)


def _edge_span(
    piece: Piece, anchor: Anchor, solution: PositionSolution, axis: int
) -> tuple[float, int, float]:
    """World coordinate along ``axis`` of the edge's FromMin start, the
    direction offsets grow in (+1 or -1) and the edge length."""
    rotation = solution.rotation[piece.id]
    start_anchor = Anchor.of(
        anchor.contact_face, anchor.edge_shared_face, FromMin(value=0)
    )
    point = as_point_3d(BoundAnchor(piece=piece, anchor=start_anchor))
    position = solution.offsets[AXES[axis]].find((piece.id, "down"))[1]
    start = position + float((rotation @ np.array([point.x, point.y, point.z]))[axis])
    # FromMin offsets grow along the edge's local axis, from its negative end
    local_axis = np.abs(
        np.cross(face_normal(anchor.contact_face), face_normal(anchor.edge_shared_face))
    )
    direction = int((rotation @ local_axis)[axis])
    edge = as_edge_point(start_anchor).edge
    return start, direction, edge_length_of(Box(shape=get_shape(piece)), edge)
