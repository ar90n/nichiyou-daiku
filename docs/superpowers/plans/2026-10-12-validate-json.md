# validate --json Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `nichiyou-daiku validate --json` prints the problems, piece positions and overall size as one JSON object, and the design skill reads it instead of guessing.

**Architecture:** Hole collisions in core keep the two holes they found (`LayoutIssue.piece_id/other/holes`). A new `shell/diagnostics.py` turns an `Assembly` into structured problems and positions (pydantic models); the text output, the report's Warnings and the JSON all come from its `collect_problems`. `validate` gains `--json`; the skill and the DSL spec describe the format.

**Tech Stack:** Python 3.13, pydantic, click 8.2 (`CliRunner` result has `.stdout`), numpy, pytest.

**Spec:** `docs/superpowers/specs/2026-10-12-validate-json-design.md`

## Global Constraints

- Branch `feat/validate-json`. `make check` before every commit. Code, comments and skill text in English; the spec stays Japanese.
- JSON keys, `kind` values and field names exactly as in the spec: top level `valid`, `error`, `overall_size`, `pieces`, `problems`; error kinds `file` / `syntax` / `semantic` / `validation` / `assembly` / `unexpected`; problem kinds `conflict` / `unconnected` / `fastener` / `hole_collision` / `overlap`.
- Coordinates in mm, origin at the smallest corner of the box around all pieces; numbers through `round_mm`.
- `overall_size` is null when the pieces form more than one group, as in the report (the spec says it equals the report's value; the report has none then).
- Problems in the text output's order: placement conflicts, unconnected groups, `assembly.fastener_issues` in their order (fasteners that do not fit, by connection, then hole collisions), overlaps.
- Text output and every message string stay exactly as they are now.
- `core/` stays free of build123d; `shell/diagnostics.py` imports nothing from build123d.
- `format_mm` and `describe_assembly_issues` move from `shell/resources.py` to `shell/diagnostics.py`; update the importers instead of re-exporting.

## Review Focus

1. `-v`, `-q` or `-d` together with `--json` must leave stdout as pure JSON (no headings, summaries or colour). Test: Task 3 `test_validate_json_stays_pure_with_global_options`.
2. An empty or comment-only file is a syntax error without a position: `error.kind == "syntax"`, `line`/`column` null, exit 1. Test: Task 3 `test_validate_json_reports_an_empty_file`.
3. Pieces in separate groups: each gets its group number, `overall_size` is null and only `unconnected` is reported (groups are not "overlapping"). Test: Task 2 `test_unconnected_groups_have_no_overall_size`.
4. A rotated piece's `faces` must obey the placement rules (contact faces opposed, edge-shared faces aligned), not just echo the solver. Test: Task 2 `test_faces_follow_the_placement_rules`.
5. Hole positions must lie on the drilled piece's surface and run into it, from the right faces. Test: Task 2 `test_a_hole_collision_says_where_both_holes_are`.

---

### Task 1: Hole collisions keep the holes they found

**Files:**
- Modify: `src/nichiyou_daiku/core/assembly/models.py` (`LayoutIssue`)
- Modify: `src/nichiyou_daiku/core/assembly/fasteners.py` (`find_hole_collisions`)
- Modify: `docs/api-specification.md:396` (one sentence)
- Test: `tests/core/test_fasteners.py` (class `TestHoleCollisions`)

**Interfaces:**
- Produces: `LayoutIssue.piece_id: str | None = None`, `LayoutIssue.other: tuple[str, str] | None = None`, `LayoutIssue.holes: tuple[tuple[SurfacePoint, Hole], tuple[SurfacePoint, Hole]] | None = None` — set only for hole collisions; `holes[0]` is this (later) connection's hole, `holes[1]` the earlier connection's, both in `piece_id`, positions in that piece's coordinates.

- [ ] **Step 1: Write the failing tests**

Append to `class TestHoleCollisions` in `tests/core/test_fasteners.py` (`Hole`, `Assembly`, `parse_dsl` are already imported there):

```python
    def test_a_collision_names_the_piece_the_other_connection_and_both_holes(self):
        source = POST_AND_FRONT_RAIL.format(front=40) + (
            "post -[BL<300 DB<0 D(4, 40)]- other\n"
        )
        [issue] = Assembly.of(parse_dsl(source)).fastener_issues
        assert issue.piece_id == "post"
        assert issue.other == ("post", "front")
        assert issue.holes is not None
        (later, later_hole), (earlier, earlier_hole) = issue.holes
        # This connection drills the post's back, the earlier one its front
        assert (later.face, earlier.face) == ("back", "front")
        assert later_hole == earlier_hole == Hole(diameter=8.0, depth=20.0)

    def test_a_fastener_without_room_has_no_holes(self):
        source = "(a:2x4 =500)\n(b:1x4 =300)\na -[FL<100 DF<0 D(5, 30)]- b\n"
        [issue] = Assembly.of(parse_dsl(source)).fastener_issues
        assert (issue.piece_id, issue.other, issue.holes) == (None, None, None)
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/core/test_fasteners.py -q -k "names_the_piece or without_room"`
Expected: 2 failed, `AttributeError: 'LayoutIssue' object has no attribute 'piece_id'`

- [ ] **Step 3: Add the fields**

In `src/nichiyou_daiku/core/assembly/models.py` replace the `LayoutIssue` class with:

```python
class LayoutIssue(BaseModel, frozen=True):
    """A connection whose fasteners could not be laid out, or whose holes run
    into the holes of an earlier connection.

    For a collision, ``piece_id`` is the piece both holes are in, ``other`` the
    earlier connection and ``holes`` the two holes, this connection's first,
    each as where it enters the piece (piece coordinates) and how it is drilled.
    """

    base_id: str
    target_id: str
    kind: FastenerKind
    message: str
    piece_id: str | None = None
    other: tuple[str, str] | None = None
    holes: tuple[tuple[SurfacePoint, Hole], tuple[SurfacePoint, Hole]] | None = None
```

- [ ] **Step 4: Fill them in `find_hole_collisions`**

In `src/nichiyou_daiku/core/assembly/fasteners.py` replace the body of `find_hole_collisions` from `bores: dict[...]` to the end with:

```python
    bores: dict[str, list[tuple[Fastener, SurfacePoint, Hole, _Bore]]] = {}
    for fastener in fasteners:
        for piece_id, position, hole in (
            (fastener.base_id, fastener.base_position, fastener.base_hole),
            (fastener.target_id, fastener.target_position, fastener.target_hole),
        ):
            box = Box(shape=get_shape(pieces[piece_id]))
            bores.setdefault(piece_id, []).append(
                (fastener, position, hole, _bore(box, position, hole))
            )

    issues: dict[tuple[str, str, str, str], LayoutIssue] = {}
    for piece_id, drilled in bores.items():
        for (earlier, earlier_at, earlier_hole, a), (
            later,
            later_at,
            later_hole,
            b,
        ) in combinations(drilled, 2):
            if not _bores_meet(a, b):
                continue
            issues.setdefault(
                (later.base_id, later.target_id, earlier.base_id, earlier.target_id),
                LayoutIssue(
                    base_id=later.base_id,
                    target_id=later.target_id,
                    kind=later.kind,
                    message=(
                        f"{later.kind} hole in '{piece_id}' runs into a "
                        f"{earlier.kind} hole of connection "
                        f"{earlier.base_id} -> {earlier.target_id}"
                    ),
                    piece_id=piece_id,
                    other=(earlier.base_id, earlier.target_id),
                    holes=((later_at, later_hole), (earlier_at, earlier_hole)),
                ),
            )
    return list(issues.values())
```

(`SurfacePoint` and `Hole` are already imported in `fasteners.py`; check with `grep -n "^from\|^import" src/nichiyou_daiku/core/assembly/fasteners.py` and add them to the existing imports if not.)

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run pytest tests/core/test_fasteners.py -q`
Expected: all pass.

- [ ] **Step 6: Document the fields**

In `docs/api-specification.md`, at the end of the paragraph starting `**Fasteners:**` (line 396), after `... the later connection gets a `LayoutIssue` and both keep their fasteners.` append:
` That issue also names the piece (`piece_id`), the earlier connection (`other`) and the two holes (`holes`: this connection's first, each as the `SurfacePoint` where it enters the piece and its `Hole`).`

- [ ] **Step 7: Commit**

```bash
uv run ruff format src/ tests/ && make check
git add src/nichiyou_daiku/core/assembly/models.py src/nichiyou_daiku/core/assembly/fasteners.py docs/api-specification.md tests/core/test_fasteners.py
git commit -m "feat: Keep the colliding holes in the layout issue"
```

---

### Task 2: Diagnostics as data (`shell/diagnostics.py`)

**Files:**
- Create: `src/nichiyou_daiku/shell/diagnostics.py`
- Modify: `src/nichiyou_daiku/shell/resources.py` (remove `format_mm` and `describe_assembly_issues`, import `describe_assembly_issues` from `.diagnostics`)
- Modify: `src/nichiyou_daiku/shell/report_generator.py:13`, `src/nichiyou_daiku/cli/utils.py:12`, `src/nichiyou_daiku/cli/commands/validate.py:8`, `tests/cli/test_validate.py:268` (import from `diagnostics`)
- Test: `tests/shell/test_diagnostics.py` (new)

**Interfaces:**
- Consumes: Task 1's `LayoutIssue.piece_id/other/holes`.
- Produces (in `nichiyou_daiku.shell.diagnostics`):
  - `format_mm(value: float) -> str` (moved, unchanged)
  - `FailureKind = Literal["file", "syntax", "semantic", "validation", "assembly", "unexpected"]`
  - models `ConflictProblem`, `UnconnectedProblem`, `FastenerProblem`, `HolePosition`, `HoleCollisionProblem`, `OverlapProblem`, `Problem` (their union), `PieceFaces`, `PiecePosition`, `ValidationFailure`, `ValidationReport`
  - `collect_problems(assembly: Assembly, *, overlaps: bool = True) -> list[Problem]`
  - `describe_assembly_issues(assembly: Assembly) -> list[str]` (moved; every problem's `message` but overlaps)
  - `validation_report(assembly: Assembly) -> ValidationReport`
  - `failure_report(kind: FailureKind, error: Exception) -> ValidationReport`

- [ ] **Step 1: Write the failing tests**

`tests/shell/test_diagnostics.py`:

```python
"""Problems and piece positions as data, for validate --json."""

from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.dsl import DSLSyntaxError, parse_dsl
from nichiyou_daiku.shell.diagnostics import (
    ValidationFailure,
    ValidationReport,
    collect_problems,
    describe_assembly_issues,
    failure_report,
    validation_report,
)
from nichiyou_daiku.shell.resources import extract_resources

CORNER = "(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n"
OVERLAP = (
    "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\n"
    "a -[FL<100 DF<0]- b\na -[FL<100 DF<0]- c\n"
)
COLLISION = (
    "(post:2x4 =600)\n(front:2x4 =300)\n(other:2x4 =300)\n"
    "post -[FL<300 DF<0 D(4, 40)]- front\n"
    "post -[BL<300 DB<0 D(4, 40)]- other\n"
)


def _report(source: str) -> ValidationReport:
    return validation_report(Assembly.of(parse_dsl(source)))


def _flip(direction: str) -> str:
    return ("-" if direction[0] == "+" else "+") + direction[1]


class TestPositions:
    def test_the_overall_box_starts_at_the_origin(self):
        report = _report(CORNER)
        assert report.overall_size is not None
        lows = [min(p.min[axis] for p in report.pieces) for axis in range(3)]
        highs = [max(p.max[axis] for p in report.pieces) for axis in range(3)]
        assert lows == [0, 0, 0]
        assert highs == list(report.overall_size)

    def test_overall_size_matches_the_report(self):
        assembly = Assembly.of(parse_dsl(CORNER))
        assert (
            validation_report(assembly).overall_size
            == extract_resources(assembly).overall_size
        )

    def test_each_box_is_the_piece_turned_into_place(self):
        report = _report(CORNER)
        assert [(p.id, p.type, p.length, p.group) for p in report.pieces] == [
            ("a", "2x4", 400, 0),
            ("b", "2x4", 400, 0),
        ]
        for piece in report.pieces:
            extent = sorted(hi - lo for lo, hi in zip(piece.min, piece.max))
            assert extent == [38, 89, 400]

    def test_faces_follow_the_placement_rules(self):
        # a -[TF<0 BD<0]- b: b's back lies on a's top (contact faces face each
        # other) and b's down end is flush with a's front (same direction)
        a, b = _report(CORNER).pieces
        assert a.faces.model_dump() == {"top": "+z", "right": "+x", "front": "+y"}
        assert b.faces.front == a.faces.top
        assert _flip(b.faces.top) == a.faces.front

    def test_unconnected_groups_have_no_overall_size(self):
        report = _report(
            "(a:2x4 =500)\n(b:2x4 =300)\n(floating:2x4 =300)\na -[FL<100 DF<0]- b\n"
        )
        assert report.overall_size is None
        assert {p.id: p.group for p in report.pieces} == {
            "a": 0,
            "b": 0,
            "floating": 1,
        }
        [problem] = report.problems
        assert problem.kind == "unconnected"
        assert problem.groups == (("a", "b"), ("floating",))


class TestProblems:
    def test_a_conflict_names_the_connection_constraint_and_mismatch(self):
        report = _report(
            "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\n"
            "a -[FL<100 DF<0]- b\na -[FL>100 DF<0]- c\nb -[RF<0 LF<0]- c\n"
        )
        [conflict] = [p for p in report.problems if p.kind == "conflict"]
        assert conflict.connection == ("b", "c")
        assert (conflict.constraint, conflict.axis) == ("contact", "z")
        assert conflict.mismatch_mm is not None and abs(conflict.mismatch_mm) == 389
        assert conflict.loop == ("b", "a", "c")
        assert conflict.message == (
            "Connection b -> c: contact (z) is off by 389mm (loop: b -> a -> c)"
        )

    def test_an_orientation_conflict_has_no_axis_or_mismatch(self):
        report = _report(
            "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\n"
            "a -[RF<0 LF<0]- b\na -[FL<100 DF<0]- c\nb -[RF<0 LF<0]- c\n"
        )
        [conflict] = [p for p in report.problems if p.kind == "conflict"]
        assert (conflict.constraint, conflict.axis, conflict.mismatch_mm) == (
            "rotation",
            None,
            None,
        )

    def test_a_fastener_without_room(self):
        report = _report("(a:2x4 =500)\n(b:1x4 =300)\na -[FL<100 DF<0 D(5, 30)]- b\n")
        [problem] = report.problems
        assert (problem.kind, problem.connection, problem.fastener) == (
            "fastener",
            ("a", "b"),
            "dowel",
        )
        assert problem.message == (
            "Connection a -> b: contact area 19.0 x 89.0mm is too narrow "
            "for a 10.0mm dowel"
        )

    def test_a_hole_collision_says_where_both_holes_are(self):
        report = _report(COLLISION)
        [problem] = report.problems
        assert problem.kind == "hole_collision"
        assert (
            problem.connection,
            problem.other_connection,
            problem.piece,
            problem.fastener,
        ) == (("post", "other"), ("post", "front"), "post", "dowel")
        post = next(p for p in report.pieces if p.id == "post")
        for hole in problem.holes:
            assert (hole.depth, hole.diameter) == (20, 8)
            axis = "xyz".index(hole.direction[1])
            inward = 1 if hole.direction[0] == "+" else -1
            # Enters on the post's surface and runs into it
            surface = post.min if inward > 0 else post.max
            assert hole.entry[axis] == surface[axis]
            assert post.min[axis] <= hole.entry[axis] + inward * 20 <= post.max[axis]
        # From the back and the front, towards each other
        assert problem.holes[0].direction == _flip(problem.holes[1].direction)

    def test_overlaps_carry_the_pieces_and_volume(self):
        [problem] = _report(OVERLAP).problems
        assert (problem.kind, problem.pieces, problem.volume_mm3) == (
            "overlap",
            ("b", "c"),
            1014600,
        )
        assert problem.message == "Pieces 'b' and 'c' overlap (1014600mm³)"

    def test_the_warnings_leave_out_overlaps(self):
        assembly = Assembly.of(parse_dsl(OVERLAP))
        assert [p.kind for p in collect_problems(assembly)] == ["overlap"]
        assert describe_assembly_issues(assembly) == []

    def test_a_sound_model_is_valid(self):
        report = _report(CORNER)
        assert report.valid is True
        assert (report.error, report.problems) == (None, ())


def test_a_failure_keeps_the_error_and_its_position():
    error = DSLSyntaxError("Unexpected token", line=3, column=5)
    report = failure_report("syntax", error)
    assert report == ValidationReport(
        valid=False,
        error=ValidationFailure(
            kind="syntax", message=str(error), line=3, column=5
        ),
    )
    assert (report.overall_size, report.pieces, report.problems) == (None, (), ())
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/shell/test_diagnostics.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'nichiyou_daiku.shell.diagnostics'`

- [ ] **Step 3: Write `shell/diagnostics.py`**

`src/nichiyou_daiku/shell/diagnostics.py`:

```python
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
        _fastener_problem(assembly, issue, origin)
        for issue in assembly.fastener_issues
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
    """Positions and problems of an assembled model. ``overall_size`` is only
    set when every piece is connected, as in the report."""
    problems = tuple(collect_problems(assembly))
    overall_size = None
    if len(assembly.placement.groups) == 1:
        low, high = overall_bounds(assembly.model, assembly.placement)
        overall_size = _vector((high.x - low.x, high.y - low.y, high.z - low.z))
    return ValidationReport(
        valid=not problems,
        overall_size=overall_size,
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
```

- [ ] **Step 4: Move the old helpers out of `resources.py` and update the importers**

In `src/nichiyou_daiku/shell/resources.py`, delete the functions `format_mm` and `describe_assembly_issues` (lines 18–53), and add to the imports:

```python
from nichiyou_daiku.shell.diagnostics import describe_assembly_issues
```

Then:

```bash
sed -i 's/^from .resources import ResourceSummary, format_mm$/from .diagnostics import format_mm\nfrom .resources import ResourceSummary/' src/nichiyou_daiku/shell/report_generator.py
sed -i 's/^from nichiyou_daiku.shell.resources import describe_assembly_issues$/from nichiyou_daiku.shell.diagnostics import describe_assembly_issues/' src/nichiyou_daiku/cli/utils.py
sed -i 's/^from nichiyou_daiku.shell.resources import describe_assembly_issues, format_mm$/from nichiyou_daiku.shell.diagnostics import describe_assembly_issues, format_mm/' src/nichiyou_daiku/cli/commands/validate.py
sed -i 's/    from nichiyou_daiku.shell.resources import format_mm/    from nichiyou_daiku.shell.diagnostics import format_mm/' tests/cli/test_validate.py
grep -rn "resources import.*\(format_mm\|describe_assembly_issues\)" src tests   # Expected: no output
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run pytest tests/shell/test_diagnostics.py -q`
Expected: all 13 pass.
Run: `uv run pytest tests/ -q -x 2>&1 | tail -2`
Expected: all pass (messages unchanged, report and CLI tests untouched).

- [ ] **Step 6: Commit**

```bash
uv run ruff format src/ tests/ && make check
git add src/nichiyou_daiku/shell/diagnostics.py src/nichiyou_daiku/shell/resources.py src/nichiyou_daiku/shell/report_generator.py src/nichiyou_daiku/cli/utils.py src/nichiyou_daiku/cli/commands/validate.py tests/shell/test_diagnostics.py tests/cli/test_validate.py
git commit -m "feat: Describe problems and piece positions as data"
```

---

### Task 3: `validate --json`

**Files:**
- Modify: `src/nichiyou_daiku/cli/commands/validate.py` (whole file below)
- Test: `tests/cli/test_validate.py` (append)

**Interfaces:**
- Consumes: Task 2's `FailureKind`, `ValidationReport`, `collect_problems`, `failure_report`, `validation_report`.
- Produces: CLI `nichiyou-daiku validate --json FILE` → one JSON object (`ValidationReport.model_dump_json(indent=2)`) on stdout; exit 0 when `valid`, else 1.

- [ ] **Step 1: Write the failing tests**

Add `import json` to the imports of `tests/cli/test_validate.py` and append:

```python
def _validate_json(runner, tmp_path, dsl, *global_options):
    dsl_file = tmp_path / "design.nd"
    dsl_file.write_text(dsl)
    result = runner.invoke(
        cli, [*global_options, "validate", "--json", str(dsl_file)]
    )
    return result, json.loads(result.stdout)


def test_validate_json_reports_a_valid_model(runner, tmp_path, valid_dsl):
    result, data = _validate_json(runner, tmp_path, valid_dsl)
    assert result.exit_code == 0
    assert (data["valid"], data["error"], data["problems"]) == (True, None, [])
    assert [piece["id"] for piece in data["pieces"]] == ["piece1", "piece2"]
    assert len(data["overall_size"]) == 3


def test_validate_json_reports_problems(runner, tmp_path):
    result, data = _validate_json(
        runner,
        tmp_path,
        "(a:2x4 =500)\n(b:2x4 =300)\n(c:2x4 =300)\n"
        "a -[FL<100 DF<0]- b\na -[FL<100 DF<0]- c\n",
    )
    assert result.exit_code == 1
    assert data["valid"] is False
    assert [p["kind"] for p in data["problems"]] == ["overlap"]
    assert data["problems"][0]["pieces"] == ["b", "c"]


def test_validate_json_reports_syntax_errors_with_their_position(
    runner, tmp_path, invalid_syntax_dsl
):
    result, data = _validate_json(runner, tmp_path, invalid_syntax_dsl)
    assert result.exit_code == 1
    assert data["error"]["kind"] == "syntax"
    assert data["error"]["line"] == 2
    assert isinstance(data["error"]["column"], int)
    assert (data["overall_size"], data["pieces"], data["problems"]) == (None, [], [])


def test_validate_json_reports_an_empty_file(runner, tmp_path):
    result, data = _validate_json(runner, tmp_path, "// nothing yet\n")
    assert result.exit_code == 1
    assert data["error"]["kind"] == "syntax"
    assert (data["error"]["line"], data["error"]["column"]) == (None, None)


def test_validate_json_reports_semantic_errors(
    runner, tmp_path, invalid_semantic_dsl
):
    result, data = _validate_json(runner, tmp_path, invalid_semantic_dsl)
    assert result.exit_code == 1
    assert data["error"]["kind"] == "semantic"


def test_validate_json_reports_a_missing_file(runner):
    result = runner.invoke(cli, ["validate", "--json", "missing.nd"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["kind"] == "file"


def test_validate_json_reports_assembly_errors(runner, tmp_path, monkeypatch):
    import nichiyou_daiku.cli.commands.validate as validate_module

    def broken(model):
        raise RuntimeError("boom")

    monkeypatch.setattr(validate_module.Assembly, "of", broken)
    result, data = _validate_json(
        runner, tmp_path, "(a:2x4 =500)\n(b:2x4 =300)\na -[FL<100 DF<0]- b\n"
    )
    assert result.exit_code == 1
    assert data["error"] == {
        "kind": "assembly",
        "message": "boom",
        "line": None,
        "column": None,
    }


def test_validate_json_reads_stdin(runner, valid_dsl):
    result = runner.invoke(cli, ["validate", "--json", "-"], input=valid_dsl)
    assert result.exit_code == 0
    assert json.loads(result.stdout)["valid"] is True


@pytest.mark.parametrize("option", ["-v", "-q", "-d"])
def test_validate_json_stays_pure_with_global_options(
    runner, tmp_path, valid_dsl, option
):
    # json.loads in the helper fails on anything but one JSON object
    result, data = _validate_json(runner, tmp_path, valid_dsl, option)
    assert result.exit_code == 0
    assert data["valid"] is True
```

Also add `import pytest` to the imports if it is not there.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/cli/test_validate.py -q -k json`
Expected: all fail — `No such option: --json` makes `result.stdout` empty, so `json.loads` raises `JSONDecodeError`.

- [ ] **Step 3: Rewrite `validate.py`**

`src/nichiyou_daiku/cli/commands/validate.py`:

```python
"""Validate command for DSL files."""

import sys

import click

from nichiyou_daiku.cli.utils import CliEcho, read_dsl_file
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.dsl import (
    DSLSemanticError,
    DSLSyntaxError,
    DSLValidationError,
    parse_dsl,
)
from nichiyou_daiku.shell.diagnostics import (
    FailureKind,
    ValidationReport,
    collect_problems,
    failure_report,
    validation_report,
)

# The first class that matches names a parse error, in the text and the JSON
_PARSE_ERRORS: tuple[tuple[type[Exception], FailureKind, str], ...] = (
    (DSLSyntaxError, "syntax", "Syntax error"),
    (DSLSemanticError, "semantic", "Semantic error"),
    (DSLValidationError, "validation", "Validation error"),
    (Exception, "unexpected", "Unexpected error"),
)


def _classify(error: Exception) -> tuple[FailureKind, str]:
    return next(
        (kind, label)
        for error_class, kind, label in _PARSE_ERRORS
        if isinstance(error, error_class)
    )


def report_validation_error(
    echo: CliEcho, error_type: str, exception: Exception
) -> None:
    """Report validation error with consistent formatting.

    Args:
        echo: CliEcho instance
        error_type: Type of error (e.g., "Syntax error", "Semantic error")
        exception: The exception to report
    """
    echo.error(click.style(f"✗ {error_type}", fg="red", bold=True))
    echo.exception(f"\n{exception}")


def _json_report(file: str) -> ValidationReport:
    try:
        content = read_dsl_file(file)
    except click.ClickException as e:
        return failure_report("file", e)
    try:
        model = parse_dsl(content)
    except Exception as e:
        return failure_report(_classify(e)[0], e)
    try:
        assembly = Assembly.of(model)
    except Exception as e:
        return failure_report("assembly", e)
    return validation_report(assembly)


@click.command()
@click.argument("file", type=str)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Print the result as one JSON object (problems, piece positions, "
    "overall size) for tools and agents.",
)
@click.pass_context
def validate(ctx: click.Context, file: str, as_json: bool) -> None:
    """Validate a DSL file and the model it describes.

    Checks the syntax, builds the assembly and solves the placement, then
    reports contradicting connections, unconnected pieces, overlapping
    pieces, fasteners that do not fit their joint and holes that collide.
    With --json, prints the same result with piece positions as JSON.

    FILE: Path to .nd file or '-' for stdin
    """
    if as_json:
        report = _json_report(file)
        # Not through CliEcho: the JSON is the output even with --quiet
        click.echo(report.model_dump_json(indent=2))
        sys.exit(0 if report.valid else 1)

    echo = CliEcho(ctx)

    try:
        dsl_content = read_dsl_file(file)
    except click.ClickException as e:
        echo.error(f"Error: {e}")
        sys.exit(1)

    try:
        model = parse_dsl(dsl_content)
    except Exception as e:
        report_validation_error(echo, _classify(e)[1], e)
        sys.exit(1)

    echo.echo(click.style("✓ DSL syntax is valid", fg="green"))
    echo.verbose("\nModel summary:")
    echo.verbose(f"  Pieces: {len(model.pieces)}")
    echo.verbose(f"  Connections: {len(model.connections)}")
    if model.pieces:
        echo.verbose("\nPieces:")
        for piece_id, piece in model.pieces.items():
            echo.verbose(f"  - {piece_id}: {piece.type.value} @ {piece.length}mm")

    try:
        assembly = Assembly.of(model)
    except Exception as e:
        report_validation_error(echo, "Assembly error", e)
        sys.exit(1)

    problems = [problem.message for problem in collect_problems(assembly)]
    if problems:
        echo.error(click.style("✗ Model has problems", fg="red", bold=True))
        for problem in problems:
            echo.error(f"  - {problem}")
        sys.exit(1)

    echo.echo(click.style("✓ Model is valid", fg="green"))
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/cli/test_validate.py -q`
Expected: all pass (the new JSON tests and the unchanged text tests).

- [ ] **Step 5: Commit**

```bash
uv run ruff format src/ tests/ && make check
git add src/nichiyou_daiku/cli/commands/validate.py tests/cli/test_validate.py
git commit -m "feat: Add validate --json"
```

---

### Task 4: Document the JSON and teach the skill to read it

**Files:**
- Modify: `docs/dsl-specification.md` (`### Validation`, after its second paragraph)
- Modify: `skills/design/SKILL.md` (sections `## 4.` and `## 5.`)
- Test: `tests/test_docs.py` (append)

**Interfaces:**
- Consumes: Task 3's CLI.

- [ ] **Step 1: Write the failing test**

Add to the imports of `tests/test_docs.py`:

```python
import json

from click.testing import CliRunner

from nichiyou_daiku.cli.dsl_cli import cli
```

Append:

```python
def test_validate_json_example_matches_the_cli():
    command = "validate --json examples/nd_files/corner_angle_compact.nd"
    blocks = _fences(DSL_SPEC)
    index = next(i for i, (_, _, body) in enumerate(blocks) if command in body)
    _, language, documented = blocks[index + 1]
    assert language == "json"
    result = CliRunner().invoke(
        cli, ["validate", "--json", str(ROOT / command.split()[-1])]
    )
    assert json.loads(documented) == json.loads(result.stdout)
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/test_docs.py -q -k validate_json`
Expected: FAIL with `StopIteration` (the spec has no such example yet).

- [ ] **Step 3: Document `--json` in the DSL specification**

Generate the example output:

```bash
uv run nichiyou-daiku validate --json examples/nd_files/corner_angle_compact.nd > /tmp/corner.json; echo "exit $?"   # Expected: exit 0
```

In `docs/dsl-specification.md`, after the paragraph `The other commands print the same problems (all but overlaps) as warnings and carry on; ...` (end of `### Validation`), insert the text below, replacing `<the contents of /tmp/corner.json>` with that file's contents verbatim:

````markdown
With `--json`, `validate` prints one JSON object on standard output instead, for tools and agents, and exits the same way:

```bash
nichiyou-daiku validate --json examples/nd_files/corner_angle_compact.nd
```

```json
<the contents of /tmp/corner.json>
```

- `valid`: there is no error and no problem.
- `error`: why validation stopped before it could check the model, with `kind` (`file`, `syntax`, `semantic`, `validation`, `assembly` or `unexpected`), `message`, and the `line` and `column` when known. Then `overall_size` is null and `pieces` and `problems` are empty.
- `overall_size`: the x, y and z extent of the model in mm, as in the report; null when some pieces are not connected.
- `pieces`: each piece's lumber `type`, solved `length`, placement `group`, and its box (`min`, `max`) in world coordinates, with the origin at the smallest corner of the whole model. `faces` gives the world direction (`+x` … `-z`) that its `top`, `right` and `front` faces point to; `down`, `left` and `back` point the other way.
- `problems`: the problems of the text output in the same order, each with a `kind`, the text `message` and the parts involved:

| `kind` | Fields |
|--------|--------|
| `conflict` | `connection` (base, target), `constraint` (`rotation`, `contact`, `flush` or `edge`), `axis`, `mismatch_mm` (null for `rotation`), `loop` (the pieces the contradiction runs through) |
| `unconnected` | `groups` (the piece IDs of each group) |
| `fastener` | `connection`, `fastener` (`dowel` or `screw`) |
| `hole_collision` | `connection`, `other_connection` (the earlier one), `piece`, `fastener`, `holes`: this connection's hole and the other's, each with `entry` (the world point where it enters the piece), `direction` (the world direction it runs), `depth` and `diameter` |
| `overlap` | `pieces`, `volume_mm3` |
````

- [ ] **Step 4: Teach the skill**

In `skills/design/SKILL.md` replace the sections `## 4. Check and fix` and `## 5. Compare with the request` (up to, not including, `## 6.`) with:

````markdown
## 4. Check and fix

Run `nichiyou-daiku validate --json <name>.nd`. Fix the `error` or every entry in `problems`, and run it again until `valid` is true. If the same problem survives three attempts, stop and explain it to the user with what you tried.

Read the JSON instead of guessing where pieces went (the DSL specification describes every field under "Validation"):

- `pieces[].min` and `max`: each piece's box in mm, with the origin at the smallest corner of the whole model. A piece that sticks out is the one whose box passes the others.
- `pieces[].faces`: the world direction of the piece's `top`, `right` and `front` faces (`down`, `left` and `back` point the other way), so you can tell which face to name in a connection.
- `problems[].kind`:
  - `conflict`: the `connection` contradicts earlier ones; `loop` shows the pieces it runs through and `mismatch_mm` how far off it is.
  - `unconnected`: the `groups` that no connection joins.
  - `overlap`: the two `pieces` share volume.
  - `fastener`: no room for the fastener in the contact area.
  - `hole_collision`: `holes` shows where both holes enter the `piece` and which way they run. Move one connection's offset by more than the hole diameter, or use a shorter fastener.

## 5. Compare with the request

Check `overall_size` in the same JSON against the request (it is null while some pieces are not connected). If it is off, find the piece that sets it in `pieces`, fix its length or offset and go back to step 4. Once the model is valid and the right size, run `nichiyou-daiku report <name>.nd --no-cut-diagram --no-anchor-details --no-pilot-holes` for the bill of materials and the shopping list.

````

- [ ] **Step 5: Run the doc and plugin tests**

Run: `uv run pytest tests/test_docs.py tests/test_plugin.py -q 2>&1 | tail -1`
Expected: all pass (the JSON example matches; links and paths in SKILL.md resolve).

- [ ] **Step 6: Commit**

```bash
make check
git add docs/dsl-specification.md skills/design/SKILL.md tests/test_docs.py
git commit -m "docs: Describe validate --json and read it in the design skill"
```

---

### Task 5: Does it help? (sonnet, headless, 3 requests × 2)

**Files:**
- Modify: `docs/superpowers/specs/2026-10-12-validate-json-design.md` (status and result line)
- Scratch (not committed): `/tmp/ndk-eval3/`

- [ ] **Step 1: A clean plugin copy and the requests**

```bash
rm -rf /tmp/ndk-plugin /tmp/ndk-eval3 && mkdir -p /tmp/ndk-plugin /tmp/ndk-eval3
git archive HEAD | tar -x -C /tmp/ndk-plugin
SUFFIX='質問はせず、決まっていないところは既定値で進めて。ファイルはカレントディレクトリに書いて。'
echo "幅500×奥行400×高さ600mmのサイドテーブルを2x4材で設計して。脚は4本、幕板は脚の上端にそろえる。天板も2x4を奥行方向に並べる。接合は8x30のダボ。$SUFFIX" > /tmp/ndk-eval3/side-table.txt
echo "幅600×奥行300×高さ800mmの2段の棚を設計して。骨組みは2x4、天板は1x4を奥行方向に並べる。脚は4本で、幕板は上端と床から150mmの2か所。下の段の棚板は2x4で下の幕板に載せる。接合は8x30のダボ。$SUFFIX" > /tmp/ndk-eval3/two-tier-shelf.txt
echo "2x2材で花台を作りたい。幅400×奥行300×高さ700mm。天板は1x4、床から200mmの位置に棚を1段。$SUFFIX" > /tmp/ndk-eval3/plant-stand.txt
```

- [ ] **Step 2: Run 6 sessions in parallel**

Run with the Bash tool's `run_in_background` and wait for its notification:

```bash
CLEAN_PATH=$(echo "$PATH" | tr ':' '\n' | grep -v -e '/\.local/bin' -e '/nichiyou-daiku/\.venv' | paste -sd:)
for case in side-table two-tier-shelf plant-stand; do for n in 1 2; do
  dir=/tmp/ndk-eval3/runs/$case-$n; mkdir -p $dir
  (cd $dir && env PATH="$CLEAN_PATH" $HOME/.local/bin/claude -p --model sonnet --plugin-dir /tmp/ndk-plugin \
     --setting-sources project,local \
     --allowedTools "Read,Write,Edit,Glob,Grep,Skill,Bash(nichiyou-daiku:*),Bash(ls:*),Bash(cat:*)" \
     --output-format stream-json --verbose "$(cat /tmp/ndk-eval3/$case.txt)" < /dev/null > run.jsonl 2> err.log) &
done; done; wait
```

- [ ] **Step 3: Score**

`/tmp/ndk-eval3/score.py`:

```python
"""Score the runs: skill used, validate passes, size matches, JSON read."""

import json
import re
import subprocess
import sys
from pathlib import Path

CLI = "/home/argon/workspace/nichiyou-daiku/.venv/bin/nichiyou-daiku"
WANTED = {
    "side-table": [400, 500, 600],
    "two-tier-shelf": [300, 600, 800],
    "plant-stand": [300, 400, 700],
}

for run in sorted(p for p in Path(sys.argv[1]).iterdir() if p.is_dir()):
    case = run.name.rsplit("-", 1)[0]
    events = [json.loads(line) for line in (run / "run.jsonl").read_text().splitlines() if line.strip()]
    uses = [
        block
        for event in events
        if event.get("type") == "assistant"
        for block in event["message"]["content"]
        if block.get("type") == "tool_use"
    ]
    commands = [u["input"].get("command", "") for u in uses if u["name"] == "Bash"]
    skill = any(u["name"] == "Skill" and "design" in json.dumps(u["input"]) for u in uses)
    validates = sum("nichiyou-daiku validate" in c for c in commands)
    with_json = sum("validate --json" in c for c in commands)
    result = next((e for e in events if e.get("type") == "result"), {})
    minutes = round(result.get("duration_ms", 0) / 60000, 1)
    nd_files = sorted(run.glob("*.nd"))
    named = [p for p in nd_files if p.stem.replace("_", "-") == case]
    if not nd_files:
        print(f"{run.name}: skill={skill} validate={validates} json={with_json} NO .nd")
        continue
    nd = named[0] if named else nd_files[0]
    data = json.loads(subprocess.run([CLI, "validate", "--json", str(nd)], capture_output=True, text=True).stdout)
    size = sorted(data["overall_size"]) if data["overall_size"] else None
    match = size is not None and all(abs(a - b) <= 1 for a, b in zip(size, WANTED[case]))
    print(f"{run.name}: skill={skill} validate={validates} json={with_json} valid={data['valid']} size={size} match={match} min={minutes} file={nd.name}")
```

Run: `.venv/bin/python /tmp/ndk-eval3/score.py /tmp/ndk-eval3/runs`
Expected (spec's bar): 6/6 `skill=True valid=True match=True`; the plant stand's median `validate` count below 25 and median minutes below 24.5; `json` > 0 in the plant-stand runs. Also read one plant-stand transcript (`jq -r 'select(.type=="assistant") | .message.content[] | select(.type=="text") | .text' run.jsonl`) to see the agent reading positions or holes from the JSON.

- [ ] **Step 4: If the bar is missed, improve the skill and rerun**

Fix `skills/design/SKILL.md` (how to read the JSON), `make check`, commit (`fix: ...`), rebuild `/tmp/ndk-plugin` (Step 1's first two lines) and rerun Steps 2–3. After two rounds without reaching the bar, stop and report the runs to the user.

- [ ] **Step 5: Record the result and commit**

In the spec set `- ステータス: 実装済み（ブランチ feat/validate-json）` and add after it:
`- 効果の確認: sonnet・非対話で 3 依頼 × 2 回。スキル <n>/6、validate <n>/6、外形寸法 <n>/6。花台の validate は <a> 回・<b> 回、<c> 分・<d> 分（前回は 11 回・39 回、18 分・31 分）。<JSON をどう使ったかを 1 文で>。`
filled in from the score output and the transcript.

```bash
make check
git add docs/superpowers/specs/2026-10-12-validate-json-design.md
git commit -m "docs: Mark the validate --json spec implemented"
```
