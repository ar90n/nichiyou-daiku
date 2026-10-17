"""Which dimensions the technical drawing writes, and where crowded values go.

Free of build123d, like ``views``: the drawing measures and draws the text.
A chain runs along one world axis of one view, from stop to stop; the stops
are both ends of the chosen pieces and of the whole model.
"""

from typing import Iterable, Literal, NamedTuple, Sequence

from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.geometry import Point3D
from nichiyou_daiku.core.piece import Piece, get_shape
from nichiyou_daiku.shell.diagnostics import format_mm

PRECISION_MM = 0.05
"""Stops closer than this print as the same value, so they are merged."""

# Placement rounds positions to 1e-6mm, so the top layer is found exactly
_TOP_TOLERANCE_MM = 1e-6

Axis = Literal["x", "y", "z"]
Side = Literal["left", "below"]

VIEW_NAMES = {"from +z": "top", "from -y": "front", "from +x": "right side"}
"""Names of the dimensioned views, by their caption in ``views.VIEWS``."""


class CrowdedDimensionsWarning(UserWarning):
    """Dimension values that do not fit beside their chain."""


class Segment(NamedTuple):
    """A stretch between neighbouring stops, in world mm along the axis.

    ``lumber`` marks the width or thickness of a piece that fills the
    stretch: readers know it from the lumber size, so the drawing writes it
    only where it fits.
    """

    start: float
    end: float
    lumber: bool

    @property
    def text(self) -> str:
        return format_mm(self.end - self.start)


class Chain(NamedTuple):
    """Chain dimensions along one world axis of one view.

    ``segments`` is empty when there is nothing between the model's ends;
    then only the overall size is drawn.
    """

    view: str
    axis: Axis
    side: Side
    stops: tuple[float, ...]
    segments: tuple[Segment, ...]

    @property
    def overall(self) -> Segment:
        return Segment(self.stops[0], self.stops[-1], lumber=False)


def _stops(ends: Iterable[float], low: float, high: float) -> tuple[float, ...]:
    """``low``, ``high`` and the ends between them, merged within PRECISION_MM."""
    stops = [low]
    for value in sorted(
        e for e in ends if low + PRECISION_MM <= e <= high - PRECISION_MM
    ):
        if value - stops[-1] >= PRECISION_MM:
            stops.append(value)
    stops.append(high)
    return tuple(stops)


def _is_lumber(
    start: float,
    end: float,
    extents: Sequence[tuple[float, float, Piece]],
) -> bool:
    for low, high, piece in extents:
        shape = get_shape(piece)
        if (
            abs(low - start) < PRECISION_MM
            and abs(high - end) < PRECISION_MM
            and min(abs(end - start - shape.width), abs(end - start - shape.height))
            < PRECISION_MM
        ):
            return True
    return False


def chain_for(
    view: str,
    axis: Axis,
    side: Side,
    bounds: dict[str, tuple[Point3D, Point3D]],
    pieces: dict[str, Piece],
    chosen: Sequence[str],
) -> Chain:
    """Chain dimensions along ``axis`` over the pieces in ``bounds`` (their
    world boxes), stopping at both ends of the ``chosen`` ones.

    ``pieces`` gives the lumber of the chosen pieces, so stretches that are
    their width or thickness are marked as lumber.
    """
    low = min(getattr(box[0], axis) for box in bounds.values())
    high = max(getattr(box[1], axis) for box in bounds.values())
    extents = [
        (getattr(bounds[i][0], axis), getattr(bounds[i][1], axis), pieces[i])
        for i in chosen
    ]
    stops = _stops((end for e in extents for end in e[:2]), low, high)
    segments = (
        tuple(
            Segment(a, b, _is_lumber(a, b, extents)) for a, b in zip(stops, stops[1:])
        )
        if len(stops) > 2
        else ()
    )
    return Chain(view, axis, side, stops, segments)


def chain_from_stops(
    view: str, axis: Axis, side: Side, stops: Iterable[float]
) -> Chain:
    """Chain dimensions through given stops, such as hole centres, between
    the lowest and the highest; none of its stretches is a lumber size."""
    ordered = sorted(stops)
    merged = _stops(ordered[1:-1], ordered[0], ordered[-1])
    segments = (
        tuple(Segment(a, b, lumber=False) for a, b in zip(merged, merged[1:]))
        if len(merged) > 2
        else ()
    )
    return Chain(view, axis, side, merged, segments)


def chains(assembly: Assembly) -> list[Chain]:
    """The drawing's dimension chains; none when the pieces are not all
    connected, since then the overall size means nothing.

    Heights in the front view stop at every piece. Widths in the front view
    and depths in the side view stop at the upright pieces (length along z),
    the top view's at the top layer (pieces whose top is the model's top).
    """
    if len(assembly.placement.groups) != 1:
        return []
    pieces = dict(assembly.model.pieces)
    bounds = {
        piece_id: assembly.placement.poses[piece_id].bounds(piece)
        for piece_id, piece in pieces.items()
    }
    upright = [
        piece_id
        for piece_id in pieces
        if abs(assembly.placement.poses[piece_id].rotation[2][2]) == 1
    ]
    top = max(box[1].z for box in bounds.values())
    top_layer = [
        piece_id
        for piece_id, box in bounds.items()
        if box[1].z >= top - _TOP_TOLERANCE_MM
    ]
    return [
        chain_for("from -y", "z", "left", bounds, pieces, list(pieces)),
        chain_for("from -y", "x", "below", bounds, pieces, upright),
        chain_for("from +x", "y", "below", bounds, pieces, upright),
        chain_for("from +z", "x", "below", bounds, pieces, top_layer),
        chain_for("from +z", "y", "left", bounds, pieces, top_layer),
    ]


def _span(
    labels: Sequence[int],
    wanted: Sequence[float],
    sizes: Sequence[float],
    low: float,
    high: float,
    gap: float,
) -> tuple[float, float]:
    total = sum(sizes[i] for i in labels) + gap * (len(labels) - 1)
    start = sum(wanted[i] for i in labels) / len(labels) - total / 2
    start = max(low, min(start, high - total))
    return start, start + total


def spread(
    wanted: Sequence[float],
    sizes: Sequence[float],
    low: float,
    high: float,
    gap: float,
) -> tuple[list[float], bool]:
    """Centres for labels along a line, and whether they all fit.

    Labels keep the order of ``wanted`` (ascending) and stay ``gap`` apart;
    each run of labels that would touch is centred on where its labels want
    to be, then moved inside ``low``..``high``. A run longer than that range
    starts at ``low`` and does not fit.

    Examples:
        >>> spread([0.0, 1.0], [2.0, 2.0], -10.0, 10.0, 1.0)
        ([-1.0, 2.0], True)
        >>> spread([0.0], [4.0], 0.0, 10.0, 1.0)
        ([2.0], True)
    """
    runs = [[i] for i in range(len(wanted))]
    while True:
        spans = [_span(run, wanted, sizes, low, high, gap) for run in runs]
        touching = next(
            (k for k in range(len(runs) - 1) if spans[k + 1][0] < spans[k][1] + gap),
            None,
        )
        if touching is None:
            break
        runs[touching : touching + 2] = [runs[touching] + runs[touching + 1]]

    centres = [0.0] * len(wanted)
    fits = True
    for run, (start, end) in zip(runs, spans):
        fits = fits and start >= low - 1e-9 and end <= high + 1e-9
        cursor = start
        for i in run:
            centres[i] = cursor + sizes[i] / 2
            cursor += sizes[i] + gap
    return centres, fits
