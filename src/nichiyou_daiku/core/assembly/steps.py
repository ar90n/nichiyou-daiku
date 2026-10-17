"""Assembly steps: the pieces each step adds, the connections it makes, what
kind of step it is, and the direction its dimension view looks from.

Free of build123d. A model's ``steps`` give the order; without them each
step adds one piece.
"""

from typing import Literal

from pydantic import BaseModel

from nichiyou_daiku.core.geometry import Point3D
from nichiyou_daiku.core.model import Model, connected_parts
from nichiyou_daiku.core.placement import edge_axis

from .builder import Assembly

StepKind = Literal["first", "attach", "sub-assembly", "join"]
"""first: the first step. sub-assembly: builds a part apart from everything
built so far. join: brings two or more parts together. attach: adds to one."""

# Tie-break for the dimension view: from above, then the front, then the side
_AXIS_PREFERENCE = (2, 1, 0)
# The step images' isometric looks from -x +y +z (shell/views.py). A
# dimension view from the same side of its axis shows the part the same way
# round, so that side wins a tie
_ISOMETRIC_SIDE = (-1, 1, 1)


class PlannedStep(BaseModel, frozen=True):
    """One step of the assembly.

    Attributes:
        number: 1-based position
        name: The name in the steps block; None when there is no steps block
        pieces: The pieces this step adds
        connections: The connections it makes, as model connection keys
        kind: What the step does to the parts built so far
        shown: The pieces of the part it leaves, in model order
        view: World axis (0, 1, 2) and side (+1, -1) the dimension view
            looks from
    """

    number: int
    name: str | None
    pieces: tuple[str, ...]
    connections: tuple[tuple[str, str], ...]
    kind: StepKind
    shown: tuple[str, ...]
    view: tuple[int, int]


class StepPlan(BaseModel, frozen=True):
    """The steps, and whether the model declared them."""

    declared: bool
    steps: tuple[PlannedStep, ...]


def _one_piece_steps(model: Model) -> list[tuple[str, ...]]:
    """Without a steps block: start with the first piece and the first piece
    touching it, then add the first piece (in declaration order) touching
    what is built; when none does, start a new part the same way."""
    order = list(model.pieces)
    touching: dict[str, set[str]] = {piece_id: set() for piece_id in order}
    for a, b in model.connections:
        touching[a].add(b)
        touching[b].add(a)
    placed: set[str] = set()
    steps: list[tuple[str, ...]] = []
    while len(placed) < len(order):
        next_to_built = [p for p in order if p not in placed and touching[p] & placed]
        if next_to_built:
            new: tuple[str, ...] = (next_to_built[0],)
        else:
            start = next(p for p in order if p not in placed)
            partner = next(
                (p for p in order if p not in placed and p in touching[start]), None
            )
            new = (start,) if partner is None else (start, partner)
        placed.update(new)
        steps.append(new)
    return steps


def _rect(box: tuple[Point3D, Point3D], axis: int) -> tuple[float, float, float, float]:
    """The box seen along ``axis``: its extent on the two other axes."""
    low = [box[0].x, box[0].y, box[0].z]
    high = [box[1].x, box[1].y, box[1].z]
    u, v = (i for i in range(3) if i != axis)
    return low[u], low[v], high[u], high[v]


def _overlap(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    width = min(a[2], b[2]) - max(a[0], b[0])
    height = min(a[3], b[3]) - max(a[1], b[1])
    return width * height if width > 0 and height > 0 else 0.0


def _area(rect: tuple[float, ...]) -> float:
    return (rect[2] - rect[0]) * (rect[3] - rect[1])


def _centre(box: tuple[Point3D, Point3D], axis: int) -> float:
    return (getattr(box[0], "xyz"[axis]) + getattr(box[1], "xyz"[axis])) / 2


def _view(
    assembly: Assembly,
    pieces: tuple[str, ...],
    connections: tuple[tuple[str, str], ...],
    shown: tuple[str, ...],
) -> tuple[int, int]:
    """The axis and side the step's dimension view looks from: across the
    edges its connections are measured along, where the new pieces hide
    each other least, from the side where the rest hides them least."""
    poses, model = assembly.placement.poses, assembly.model
    boxes = {p: poses[p].bounds(model.pieces[p]) for p in shown}
    measured = {
        edge_axis(poses[key[0]].rotation_matrix(), model.connections[key].base)
        for key in connections
    }
    axes = [axis for axis in _AXIS_PREFERENCE if axis not in measured] or list(
        _AXIS_PREFERENCE
    )

    def crowding(axis: int) -> tuple[float, float]:
        rects = [_rect(boxes[p], axis) for p in pieces]
        overlap = sum(
            _overlap(a, b) for i, a in enumerate(rects) for b in rects[i + 1 :]
        )
        return overlap, -sum(_area(r) for r in rects)

    axis = min(axes, key=crowding)  # min keeps the preferred axis on ties
    others = [p for p in shown if p not in pieces]

    def hidden(sign: int) -> float:
        return sum(
            _overlap(_rect(boxes[p], axis), _rect(boxes[o], axis))
            for p in pieces
            for o in others
            if sign * _centre(boxes[o], axis) > sign * _centre(boxes[p], axis)
        )

    # min keeps the first side on ties: the isometric's
    side = _ISOMETRIC_SIDE[axis]
    return axis, min((side, -side), key=hidden)


def plan_steps(assembly: Assembly) -> StepPlan:
    """The assembly steps of the model's steps block, or one piece per step
    when it has none.

    Examples:
        >>> from nichiyou_daiku.dsl import parse_dsl
        >>> model = parse_dsl(
        ...     "(a:2x4 =400)\\n(b:2x4 =400)\\na -[TF<0 BD<0]- b\\n"
        ... )
        >>> plan = plan_steps(Assembly.of(model))
        >>> plan.declared, [step.pieces for step in plan.steps]
        (False, [('a', 'b')])
    """
    model = assembly.model
    declared = bool(model.steps)
    groups = (
        [(step.name, step.pieces) for step in model.steps]
        if declared
        else [(None, pieces) for pieces in _one_piece_steps(model)]
    )
    step_of = {p: i for i, (_, pieces) in enumerate(groups) for p in pieces}
    pairs = list(model.connections)
    order = list(model.pieces)

    planned = []
    placed: list[str] = []
    for i, (name, pieces) in enumerate(groups):
        before = connected_parts(placed, pairs)
        placed += pieces
        part = next(
            part for part in connected_parts(placed, pairs) if part & set(pieces)
        )
        joined = [old for old in before if old & part]
        if i == 0:
            kind: StepKind = "first"
        elif not joined:
            kind = "sub-assembly"
        elif len(joined) > 1:
            kind = "join"
        else:
            kind = "attach"
        made = tuple(key for key in pairs if max(step_of[key[0]], step_of[key[1]]) == i)
        shown = tuple(p for p in order if p in part)
        planned.append(
            PlannedStep(
                number=i + 1,
                name=name,
                pieces=pieces,
                connections=made,
                kind=kind,
                shown=shown,
                view=_view(assembly, pieces, made, shown),
            )
        )
    return StepPlan(declared=declared, steps=tuple(planned))
