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
# SKILL.md asks for a steps block for "more than a few pieces"
_STEPS_FROM = 6


class Check(NamedTuple):
    passed: bool | None
    """None when the case does not ask for this check."""
    detail: str


def find_design(directory: Path, case_name: str) -> Path | None:
    """The design the agent wrote: the .nd named after the case, else the
    only .nd in ``directory``."""
    designs = sorted(directory.glob("*.nd"))
    named = [path for path in designs if path.stem.replace("_", "-") == case_name]
    if named:
        return named[0]
    return designs[0] if len(designs) == 1 else None


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
        return _failed(asked, "no single .nd file in the working directory")
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
    passed = all(
        _close(a, b, wanted.tolerance)
        for a, b in zip(size, (wanted.width, wanted.depth, wanted.height))
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


def _level_tops(pieces: tuple[PiecePosition, ...]) -> list[float]:
    tops = sorted(piece.max[2] for piece in pieces if _flat_board(piece))
    levels: list[list[float]] = []
    for top in tops:
        if levels and top - levels[-1][0] <= _LEVEL_MM:
            levels[-1].append(top)
        else:
            levels.append([top])
    return [max(level) for level in levels]


def _levels(report: ValidationReport, case: Case) -> Check:
    wanted = case.levels
    if wanted is None:
        return Check(None, "not asked")
    tops = _level_tops(report.pieces)
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
