"""Problems of an assembly and where its pieces sit, as data.

The text output of the commands, the report's Warnings and ``validate
--json`` all come from ``collect_problems``, so they cannot drift apart.
"""

from typing import Iterable, Literal

import numpy as np
from pydantic import BaseModel

from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.assembly.models import FastenerKind, Hole, LayoutIssue
from nichiyou_daiku.core.geometry import Point3D, SurfacePoint
from nichiyou_daiku.core.piece import get_shape
from nichiyou_daiku.core.placement import (
    Axis,
    ConstraintKind,
    face_normal,
    find_overlaps,
    overall_bounds,
    round_mm,
)

Vector = tuple[float, float, float]
FailureKind = Literal[
    "file", "syntax", "semantic", "validation", "assembly", "unexpected"
]


def format_mm(value: float) -> str:
    """Format a length or volume: 0.1mm steps without a trailing ".0", and
    two significant digits below 0.1 so small values do not print as 0."""
    if abs(value) >= 0.1:
        return f"{value:.1f}".removesuffix(".0")
    return f"{value:.2g}"


class ConflictProblem(BaseModel, frozen=True):
    """A connection that contradicts the ones declared before it."""

    kind: Literal["conflict"] = "conflict"
    message: str
    connection: tuple[str, str]
    constraint: ConstraintKind
    axis: Axis | None
    mismatch_mm: float | None
    loop: tuple[str, ...]


class UnconnectedProblem(BaseModel, frozen=True):
    """Pieces in separate groups, whose relative position is undefined."""

    kind: Literal["unconnected"] = "unconnected"
    message: str
    groups: tuple[tuple[str, ...], ...]


class FastenerProblem(BaseModel, frozen=True):
    """A connection whose fasteners have no room in the contact area."""

    kind: Literal["fastener"] = "fastener"
    message: str
    connection: tuple[str, str]
    fastener: FastenerKind


class HolePosition(BaseModel, frozen=True):
    """Where a hole enters its piece and which way it runs, in world terms."""

    entry: Vector
    direction: str
    depth: float | None
    diameter: float


class HoleCollisionProblem(BaseModel, frozen=True):
    """Holes of two connections that run into each other inside a piece."""

    kind: Literal["hole_collision"] = "hole_collision"
    message: str
    connection: tuple[str, str]
    other_connection: tuple[str, str]
    piece: str
    fastener: FastenerKind
    holes: tuple[HolePosition, HolePosition]


class OverlapProblem(BaseModel, frozen=True):
    """Two pieces that share volume."""

    kind: Literal["overlap"] = "overlap"
    message: str
    pieces: tuple[str, str]
    volume_mm3: float


Problem = (
    ConflictProblem
    | UnconnectedProblem
    | FastenerProblem
    | HoleCollisionProblem
    | OverlapProblem
)


class PieceFaces(BaseModel, frozen=True):
    """World directions of a piece's top, right and front faces; down, left
    and back point the other way."""

    top: str
    right: str
    front: str


class PiecePosition(BaseModel, frozen=True):
    """A piece's box in world coordinates and the way it is turned."""

    id: str
    type: str
    length: float
    group: int
    min: Vector
    max: Vector
    faces: PieceFaces


class ValidationFailure(BaseModel, frozen=True):
    """Why validation stopped before it could check the model."""

    kind: FailureKind
    message: str
    line: int | None = None
    column: int | None = None


class ValidationReport(BaseModel, frozen=True):
    """The result of ``validate --json``."""

    valid: bool
    error: ValidationFailure | None = None
    overall_size: Vector | None = None
    size_reference: str | None = None
    pieces: tuple[PiecePosition, ...] = ()
    problems: tuple[Problem, ...] = ()


def _vector(values: Iterable[float]) -> Vector:
    x, y, z = (round_mm(value) for value in values)
    return (x, y, z)


def _direction(vector: np.ndarray) -> str:
    axis = int(np.argmax(np.abs(vector)))
    return f"{'+' if vector[axis] > 0 else '-'}{'xyz'[axis]}"


def _origin(assembly: Assembly) -> np.ndarray:
    low, _ = overall_bounds(assembly.model, assembly.placement)
    return np.array([low.x, low.y, low.z])


def _hole(
    assembly: Assembly,
    piece_id: str,
    at: SurfacePoint,
    hole: Hole,
    origin: np.ndarray,
) -> HolePosition:
    pose = assembly.placement.poses[piece_id]
    entry = pose.apply(Point3D.of(assembly.boxes[piece_id], at))
    # A hole runs into the piece, against its face's outward normal
    inward = pose.rotation_matrix() @ -face_normal(at.face)
    return HolePosition(
        entry=_vector(np.array([entry.x, entry.y, entry.z]) - origin),
        direction=_direction(inward),
        depth=None if hole.depth is None else round_mm(hole.depth),
        diameter=round_mm(hole.diameter),
    )


def _fastener_problem(
    assembly: Assembly, issue: LayoutIssue, origin: np.ndarray
) -> FastenerProblem | HoleCollisionProblem:
    message = f"Connection {issue.base_id} -> {issue.target_id}: {issue.message}"
    connection = (issue.base_id, issue.target_id)
    if issue.piece_id is None or issue.other is None or issue.holes is None:
        return FastenerProblem(
            message=message, connection=connection, fastener=issue.kind
        )
    later, earlier = issue.holes
    return HoleCollisionProblem(
        message=message,
        connection=connection,
        other_connection=issue.other,
        piece=issue.piece_id,
        fastener=issue.kind,
        holes=(
            _hole(assembly, issue.piece_id, *later, origin),
            _hole(assembly, issue.piece_id, *earlier, origin),
        ),
    )


def collect_problems(assembly: Assembly, *, overlaps: bool = True) -> list[Problem]:
    """Everything wrong with the assembly, in the order the CLI prints it:
    placement conflicts, unconnected groups, fasteners and colliding holes,
    then overlapping pieces (left out with ``overlaps=False``)."""
    placement = assembly.placement
    origin = _origin(assembly)
    problems: list[Problem] = []
    for conflict in placement.conflicts:
        loop = " -> ".join(conflict.loop)
        where = f"Connection {conflict.base_id} -> {conflict.target_id}"
        if conflict.kind == "rotation":
            message = (
                f"{where}: orientation contradicts the other connections (loop: {loop})"
            )
        else:
            message = (
                f"{where}: {conflict.kind} ({conflict.axis}) is off by "
                f"{format_mm(abs(conflict.mismatch_mm or 0.0))}mm (loop: {loop})"
            )
        problems.append(
            ConflictProblem(
                message=message,
                connection=(conflict.base_id, conflict.target_id),
                constraint=conflict.kind,
                axis=conflict.axis,
                mismatch_mm=None
                if conflict.mismatch_mm is None
                else round_mm(conflict.mismatch_mm),
                loop=conflict.loop,
            )
        )
    if len(placement.groups) > 1:
        listed = "; ".join(", ".join(group) for group in placement.groups)
        problems.append(
            UnconnectedProblem(
                message=(
                    "Some pieces are not connected to each other, so their relative "
                    f"position is undefined (groups: {listed})"
                ),
                groups=placement.groups,
            )
        )
    problems += [
        _fastener_problem(assembly, issue, origin) for issue in assembly.fastener_issues
    ]
    if overlaps:
        problems += [
            OverlapProblem(
                message=(
                    f"Pieces '{overlap.lhs}' and '{overlap.rhs}' overlap "
                    f"({format_mm(overlap.volume)}mm³)"
                ),
                pieces=(overlap.lhs, overlap.rhs),
                volume_mm3=round_mm(overlap.volume),
            )
            for overlap in find_overlaps(assembly.model, placement)
        ]
    return problems


def describe_assembly_issues(assembly: Assembly) -> list[str]:
    """Human-readable lines for every problem but overlaps: the warnings the
    other commands print and the report lists."""
    return [problem.message for problem in collect_problems(assembly, overlaps=False)]


def _positions(assembly: Assembly, origin: np.ndarray) -> tuple[PiecePosition, ...]:
    group_of = {
        member: index
        for index, group in enumerate(assembly.placement.groups)
        for member in group
    }
    positions = []
    for piece_id, piece in assembly.model.pieces.items():
        pose = assembly.placement.poses[piece_id]
        low, high = pose.bounds(piece)
        rotation = pose.rotation_matrix()
        positions.append(
            PiecePosition(
                id=piece_id,
                type=piece.type.value,
                length=round_mm(get_shape(piece).length),
                group=group_of[piece_id],
                min=_vector(np.array([low.x, low.y, low.z]) - origin),
                max=_vector(np.array([high.x, high.y, high.z]) - origin),
                faces=PieceFaces(
                    top=_direction(rotation @ face_normal("top")),
                    right=_direction(rotation @ face_normal("right")),
                    front=_direction(rotation @ face_normal("front")),
                ),
            )
        )
    return tuple(positions)


def validation_report(assembly: Assembly) -> ValidationReport:
    """Positions and problems of an assembled model. ``overall_size`` and
    ``size_reference`` (the first declared piece, whose width, thickness and
    length run along x, y and z) are only set when every piece is connected,
    as in the report."""
    problems = tuple(collect_problems(assembly))
    overall_size = None
    size_reference = None
    if len(assembly.placement.groups) == 1:
        low, high = overall_bounds(assembly.model, assembly.placement)
        overall_size = _vector((high.x - low.x, high.y - low.y, high.z - low.z))
        size_reference = assembly.placement.groups[0][0]
    return ValidationReport(
        valid=not problems,
        overall_size=overall_size,
        size_reference=size_reference,
        pieces=_positions(assembly, _origin(assembly)),
        problems=problems,
    )


def failure_report(kind: FailureKind, error: Exception) -> ValidationReport:
    """The report of a validation that stopped at ``error``."""
    return ValidationReport(
        valid=False,
        error=ValidationFailure(
            kind=kind,
            message=str(error),
            line=getattr(error, "line", None),
            column=getattr(error, "column", None),
        ),
    )
