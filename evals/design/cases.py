"""The design requests and what a sound answer to each must meet."""

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict

CASES_DIR = Path(__file__).parent / "cases"


class _Requirement(BaseModel):
    # A misspelt key would otherwise be dropped and its check never run
    model_config = ConfigDict(extra="forbid", frozen=True)


class Size(_Requirement):
    """Width along x, depth along y, height along z, in mm. A request that
    only names the height leaves width and depth out. ``either_way`` lets
    width and depth swap: in a box without legs the first piece is a side,
    and the library lays a first piece's width along x."""

    width: float | None = None
    depth: float | None = None
    height: float
    tolerance: float = 1.0
    either_way: bool = False


class Lumber(_Requirement):
    allowed: tuple[str, ...]
    required: tuple[str, ...] = ()


class Legs(_Requirement):
    count: int


class Shelf(_Requirement):
    """A horizontal member whose top or bottom is this far above the floor."""

    at: float
    tolerance: float = 5.0


class Levels(_Requirement):
    """Boards lying flat, grouped by the height of their top."""

    count: int | None = None
    equal: bool = False
    top: bool = False
    """The highest level is the top of the furniture."""


class Fasteners(_Requirement):
    dowel: bool = False
    screw: bool = False


class Case(_Requirement):
    name: str
    request: str
    core: bool = False
    heldout: bool = False
    """Kept out of "all": it checks that a change to the skill does not fit
    only the cases it was tuned on."""
    tags: tuple[str, ...] = ()
    size: Size
    lumber: Lumber
    legs: Legs | None = None
    shelves: tuple[Shelf, ...] = ()
    levels: Levels | None = None
    fasteners: Fasteners | None = None


def load_case(path: Path) -> Case:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return Case(name=path.stem, **data)


def load_cases(selection: str = "all", directory: Path = CASES_DIR) -> list[Case]:
    """The cases of ``selection``: ``all`` (without the held-out ones),
    ``core``, ``heldout`` or names joined by commas, in the order of their
    file names."""
    cases = [load_case(path) for path in sorted(directory.glob("*.toml"))]
    if selection == "all":
        return [case for case in cases if not case.heldout]
    if selection == "core":
        return [case for case in cases if case.core]
    if selection == "heldout":
        return [case for case in cases if case.heldout]
    names = selection.split(",")
    unknown = sorted(set(names) - {case.name for case in cases})
    if unknown:
        raise ValueError(
            f"Unknown case {', '.join(unknown)}; use all, core, heldout or names "
            f"from {', '.join(case.name for case in cases)}"
        )
    return [case for case in cases if case.name in names]
