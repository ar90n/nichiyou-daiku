"""Machine checks: read the design with nichiyou-daiku and compare it with
what the case asks for."""

from pathlib import Path
from typing import NamedTuple

from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.connection import DowelConnection, ScrewConnection
from nichiyou_daiku.core.model import Model
from nichiyou_daiku.core.piece import PieceType, get_shape
from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.shell.diagnostics import (
    PiecePosition,
    ValidationReport,
    validation_report,
)

from .cases import Case

CHECKS = (
    "valid",
    "size",
    "orientation",
    "lumber",
    "legs",
    "shelves",
    "levels",
    "fasteners",
    "steps",
)
# Positions are rounded, so a piece this near z = 0 stands on the floor
_FLOOR_MM = 0.5
# Board tops this close are one level; level gaps this close are equal
_LEVEL_MM = 5.0
# A level's boards cover at least this share of the plan: a few narrow
# boards with wide gaps are no shelf. In the 2026-10-19 status check every
# design the judge passed covered 70% or more at each level, and a tv stand
# the judge failed 27%
_LEVEL_COVER = 0.5
# SKILL.md asks for a steps block for "more than a few pieces"
_STEPS_FROM = 6


class Check(NamedTuple):
    passed: bool | None
    """None when the case does not ask for this check."""
    detail: str


def find_design(
    directory: Path, case_name: str, checked: str | None = None
) -> Path | None:
    """The design the agent wrote in ``directory``: the .nd named after the
    case, else the only one, else the one it last validated or rendered
    (``checked``), else the newest. The agent never sees the case's name,
    so a draft beside the design is common."""
    designs = sorted(directory.glob("*.nd"))
    named = [path for path in designs if path.stem.replace("_", "-") == case_name]
    if named:
        return named[0]
    if len(designs) <= 1:
        return designs[0] if designs else None
    if checked and directory / checked in designs:
        return directory / checked
    return max(designs, key=lambda path: path.stat().st_mtime)


def _assemble(path: Path) -> tuple[Model, Assembly]:
    model = parse_dsl(path.read_text(encoding="utf-8"))
    return model, Assembly.of(model)


def assembles(path: Path) -> bool:
    """Whether the design at ``path`` parses and assembles, so that it can
    be drawn."""
    try:
        _assemble(path)
    except Exception:
        return False
    return True


def check_design(path: Path | None, case: Case) -> dict[str, Check]:
    """Every check of ``CHECKS`` for the design at ``path``."""
    asked = _asked(case)
    if path is None:
        return _failed(asked, "no .nd file in the working directory")
    try:
        model, assembly = _assemble(path)
    except Exception as e:
        first_line = str(e).splitlines()[0] if str(e) else type(e).__name__
        return _failed(asked, f"{path.name} does not assemble: {first_line}")
    report = validation_report(assembly)
    checks = {
        "valid": _valid(report),
        "size": _size(report, case),
        "orientation": _orientation(report, case),
        "lumber": _lumber(report.pieces, case),
        "legs": _legs(report.pieces, case),
        "shelves": _shelves(report.pieces, case),
        "levels": _levels(report, case),
        "fasteners": _fasteners(model, case),
        "steps": _steps(model),
    }
    return {
        name: check if name in asked else Check(None, "not asked")
        for name, check in checks.items()
    }


def _asked(case: Case) -> set[str]:
    asked = {"valid", "size", "lumber", "steps"}
    if case.size.width is not None and case.size.depth is not None:
        asked.add("orientation")
    for name, requirement in (
        ("legs", case.legs),
        ("shelves", case.shelves),
        ("levels", case.levels),
        ("fasteners", case.fasteners),
    ):
        if requirement:
            asked.add(name)
    return asked


def _failed(asked: set[str], why: str) -> dict[str, Check]:
    return {
        name: Check(False, why) if name in asked else Check(None, "not asked")
        for name in CHECKS
    }


def _close(a: float, b: float, tolerance: float) -> bool:
    return abs(a - b) <= tolerance


def _valid(report: ValidationReport) -> Check:
    if report.valid:
        return Check(True, "no problems")
    kinds = sorted({problem.kind for problem in report.problems})
    return Check(False, f"validate reports {', '.join(kinds)}")


def _size(report: ValidationReport, case: Case) -> Check:
    size = report.overall_size
    if size is None:
        return Check(False, "the pieces are not all connected: no overall size")
    wanted = case.size
    shown = " × ".join(f"{value:g}" for value in size)
    if wanted.width is None or wanted.depth is None:
        passed = _close(size[2], wanted.height, wanted.tolerance)
        return Check(passed, f"height {size[2]:g}, asked {wanted.height:g}")
    asked = sorted((wanted.width, wanted.depth, wanted.height))
    passed = all(_close(a, b, wanted.tolerance) for a, b in zip(sorted(size), asked))
    return Check(passed, f"{shown} mm")


def _orientation(report: ValidationReport, case: Case) -> Check:
    size = report.overall_size
    wanted = case.size
    if size is None or wanted.width is None or wanted.depth is None:
        return Check(False, "no overall size")
    plan, asked = size[:2], (wanted.width, wanted.depth)
    if wanted.either_way:
        plan, asked = sorted(plan), sorted(asked)
    passed = all(
        _close(a, b, wanted.tolerance)
        for a, b in zip((*plan, size[2]), (*asked, wanted.height))
    )
    return Check(passed, f"x {size[0]:g}, y {size[1]:g}, z {size[2]:g}")


def _lumber(pieces: tuple[PiecePosition, ...], case: Case) -> Check:
    used = sorted({piece.type for piece in pieces})
    extra = sorted(set(used) - set(case.lumber.allowed))
    missing = sorted(set(case.lumber.required) - set(used))
    detail = f"uses {', '.join(used)}"
    if extra:
        detail += f"; not asked: {', '.join(extra)}"
    if missing:
        detail += f"; missing: {', '.join(missing)}"
    return Check(not extra and not missing, detail)


def _upright(piece: PiecePosition) -> bool:
    return piece.faces.top[1] == "z"


def _legs(pieces: tuple[PiecePosition, ...], case: Case) -> Check:
    if case.legs is None:
        return Check(None, "not asked")
    legs = [p for p in pieces if _upright(p) and p.min[2] <= _FLOOR_MM]
    return Check(
        len(legs) == case.legs.count,
        f"{len(legs)} upright pieces stand on the floor, asked {case.legs.count}",
    )


def _shelves(pieces: tuple[PiecePosition, ...], case: Case) -> Check:
    lying = [piece for piece in pieces if not _upright(piece)]
    missing = [
        shelf.at
        for shelf in case.shelves
        if not any(
            _close(piece.min[2], shelf.at, shelf.tolerance)
            or _close(piece.max[2], shelf.at, shelf.tolerance)
            for piece in lying
        )
    ]
    if missing:
        heights = ", ".join(f"{at:g}" for at in missing)
        return Check(False, f"no horizontal piece starts or ends at {heights}")
    return Check(True, "every asked height has a horizontal piece")


def _flat_board(piece: PiecePosition) -> bool:
    section = get_shape(PieceType(piece.type))
    # A square section (2x2) lying down is a rail, not a board
    return piece.faces.front[1] == "z" and section.width > section.height


def _holds_up(lower: PiecePosition, upper: PiecePosition) -> bool:
    """Whether ``lower`` lies right under ``upper``, touching it."""
    return abs(lower.max[2] - upper.min[2]) <= _LEVEL_MM and all(
        lower.min[axis] < upper.max[axis] and upper.min[axis] < lower.max[axis]
        for axis in (0, 1)
    )


def _level_tops(
    pieces: tuple[PiecePosition, ...], plan_area: float | None
) -> tuple[list[float], list[tuple[float, float]]]:
    """The tops of the levels, and (top, share of the plan) of the boards
    that sit at one height but cover too little of the plan to be a level
    (``plan_area`` None counts every level)."""
    boards = [piece for piece in pieces if _flat_board(piece)]
    # A flat apron or cleat right under a board holds it up; it is not a
    # level of its own
    boards = sorted(
        (b for b in boards if not any(_holds_up(b, other) for other in boards)),
        key=lambda board: board.max[2],
    )
    groups: list[list[PiecePosition]] = []
    for board in boards:
        if groups and board.max[2] - groups[-1][0].max[2] <= _LEVEL_MM:
            groups[-1].append(board)
        else:
            groups.append([board])
    levels: list[float] = []
    sparse: list[tuple[float, float]] = []
    for group in groups:
        top = max(board.max[2] for board in group)
        covered = sum(
            (board.max[0] - board.min[0]) * (board.max[1] - board.min[1])
            for board in group
        )
        share = covered / plan_area if plan_area else 1.0
        if share >= _LEVEL_COVER:
            levels.append(top)
        else:
            sparse.append((top, share))
    return levels, sparse


def _levels(report: ValidationReport, case: Case) -> Check:
    wanted = case.levels
    if wanted is None:
        return Check(None, "not asked")
    size = report.overall_size
    tops, sparse = _level_tops(report.pieces, size[0] * size[1] if size else None)
    shown = ", ".join(f"{top:g}" for top in tops) or "none"
    failures = []
    if wanted.count is not None and len(tops) != wanted.count:
        failures.append(f"{len(tops)} levels, asked {wanted.count}")
    gaps = [b - a for a, b in zip(tops, tops[1:])]
    if wanted.equal and gaps and max(gaps) - min(gaps) > _LEVEL_MM:
        failures.append("levels not evenly spaced")
    height = report.overall_size[2] if report.overall_size else None
    if wanted.top and (not tops or height is None or not _close(tops[-1], height, 1)):
        failures.append("the top is not a board")
    detail = f"board tops at {shown}"
    if sparse:
        detail += "; too sparse to count: " + ", ".join(
            f"{top:g} ({share:.0%} of the plan)" for top, share in sparse
        )
    return Check(
        not failures, f"{detail}; {'; '.join(failures)}" if failures else detail
    )


def _fasteners(model: Model, case: Case) -> Check:
    wanted = case.fasteners
    if wanted is None:
        return Check(None, "not asked")
    kinds = {type(connection.type) for connection in model.connections.values()}
    missing = [
        name
        for name, asked, kind in (
            ("dowels", wanted.dowel, DowelConnection),
            ("screws", wanted.screw, ScrewConnection),
        )
        if asked and kind not in kinds
    ]
    if missing:
        return Check(False, f"no {' or '.join(missing)}")
    return Check(True, "asked fasteners used")


def _steps(model: Model) -> Check:
    if len(model.pieces) < _STEPS_FROM:
        return Check(True, f"{len(model.pieces)} pieces: no steps block needed")
    return Check(
        bool(model.steps),
        f"{len(model.steps)} steps" if model.steps else "no steps block",
    )
