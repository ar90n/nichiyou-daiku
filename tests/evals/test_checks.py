"""Tests for the machine checks of a design."""

import os
from pathlib import Path

from evals.design.cases import Fasteners, Legs, Levels, Lumber, Shelf, Size, load_cases
from evals.design.checks import CHECKS, _level_tops, _levels, check_design, find_design
from nichiyou_daiku.shell.diagnostics import PieceFaces, PiecePosition, ValidationReport

ROOT = Path(__file__).parents[2]
SIDE_TABLE = ROOT / "skills" / "design" / "examples" / "side-table.nd"
SHELF = ROOT / "skills" / "design" / "examples" / "two-tier-shelf.nd"
CASES = {case.name: case for case in load_cases()}


def _failing(path, case) -> set[str]:
    return {
        name
        for name, check in check_design(path, case).items()
        if check.passed is False
    }


def test_the_examples_pass_their_own_requests():
    for path, name in ((SIDE_TABLE, "side-table"), (SHELF, "two-tier-shelf")):
        checks = check_design(path, CASES[name])
        assert set(checks) == set(CHECKS)
        assert _failing(path, CASES[name]) == set(), name


def test_checks_a_case_does_not_ask_for_are_not_counted():
    checks = check_design(SIDE_TABLE, CASES["side-table"])
    assert checks["shelves"].passed is None
    assert checks["levels"].passed is None


def test_each_requirement_fails_only_its_own_check():
    case = CASES["side-table"]
    changed = {
        "size": case.model_copy(
            update={"size": Size(width=500, depth=400, height=700)}
        ),
        "lumber": case.model_copy(
            update={"lumber": Lumber(allowed=("2x4", "1x4"), required=("1x4",))}
        ),
        "legs": case.model_copy(update={"legs": Legs(count=6)}),
        "shelves": case.model_copy(update={"shelves": (Shelf(at=300),)}),
        "levels": case.model_copy(update={"levels": Levels(count=2)}),
        "fasteners": case.model_copy(update={"fasteners": Fasteners(screw=True)}),
    }
    for name, wrong in changed.items():
        expected = {name, "orientation"} if name == "size" else {name}
        assert _failing(SIDE_TABLE, wrong) == expected, name


def test_a_design_turned_on_its_side_has_the_right_size_and_the_wrong_orientation():
    turned = ROOT / "evals" / "design" / "fixtures" / "on-its-side.nd"
    assert _failing(turned, CASES["side-table"]) >= {"orientation", "legs"}
    assert check_design(turned, CASES["side-table"])["size"].passed is True


BOOKSHELF = """// 1x8 bookshelf: 600 (W) x 184 (D) x 900 (H), four equal levels
(left_side:1x8 =900)
(right_side:1x8 =900)
(bottom:1x8 =562)
(shelf_1:1x8 =562)
(shelf_2:1x8 =562)
(top:1x8 =562)

left_side -[BL<0 DL<0 D(:8x30)]- bottom
right_side -[FL<0 TL<0 D(:8x30)]- bottom
left_side -[BL<294 DL<0 D(:8x30)]- shelf_1
right_side -[FL<294 TL<0 D(:8x30)]- shelf_1
left_side -[BL<587 DL<0 D(:8x30)]- shelf_2
right_side -[FL<587 TL<0 D(:8x30)]- shelf_2
left_side -[BL<881 DL<0 D(:8x30)]- top
right_side -[FL<881 TL<0 D(:8x30)]- top
"""


def test_a_box_without_legs_may_face_either_way(tmp_path):
    # Its first piece is a side, and the library lays a first piece's width
    # along x: the bookshelf's depth comes out along x however it is written
    design = tmp_path / "bookshelf.nd"
    design.write_text(BOOKSHELF)
    assert check_design(design, CASES["bookshelf"])["orientation"].passed is True
    # Still the right way up: the height along z
    lying = tmp_path / "lying.nd"
    lying.write_text("(top:1x8 =562)\n" + BOOKSHELF.replace("(top:1x8 =562)\n", ""))
    checks = check_design(lying, CASES["bookshelf"])
    assert checks["size"].passed is True
    assert checks["orientation"].passed is False


def test_levels_count_boards_and_their_spacing():
    shelf = CASES["two-tier-shelf"]
    # The shelf's boards: the 2x4 shelf on the lower aprons and the 1x4 top
    two = shelf.model_copy(update={"levels": Levels(count=2, equal=True, top=True)})
    assert check_design(SHELF, two)["levels"].passed is True
    three = shelf.model_copy(update={"levels": Levels(count=3)})
    assert "2 levels, asked 3" in check_design(SHELF, three)["levels"].detail


def _flat(id: str, type: str, low: tuple, high: tuple) -> PiecePosition:
    faces = PieceFaces(top="+x", right="+y", front="+z")
    return PiecePosition(
        id=id,
        type=type,
        length=high[0] - low[0],
        group=0,
        min=low,
        max=high,
        faces=faces,
    )


def test_a_flat_board_holding_up_another_is_not_a_level():
    # A tv stand: a flat 2x4 apron right under the 2x6 top holds it up
    top = _flat("top", "2x6", (0, 0, 362), (1200, 140, 400))
    apron = _flat("apron", "2x4", (0, 20, 324), (1200, 109, 362))
    shelf = _flat("shelf", "2x6", (0, 0, 62), (1200, 140, 100))
    assert _level_tops((top, apron, shelf), None)[0] == [100, 400]
    # A board at that height but elsewhere is a level of its own
    aside = _flat("aside", "2x4", (0, 200, 324), (1200, 289, 362))
    assert _level_tops((top, aside, shelf), None)[0] == [100, 362, 400]


def test_a_level_of_a_few_narrow_boards_is_not_counted():
    # GLM's tv stand: three 2x6 boards running front to back with wide gaps
    # made its middle shelf, 27% of the plan. Every design the judge passed
    # in the 2026-10-19 status check covered 70% or more at each level
    top_front = _flat("top_f", "2x6", (0, 210, 362), (1200, 350, 400))
    top_back = _flat("top_b", "2x6", (0, 0, 362), (1200, 140, 400))
    shelves = [
        _flat(f"shelf_{x}", "2x6", (x, 38, 150), (x + 140, 312, 188))
        for x in (0, 556, 1060)
    ]
    report = ValidationReport.model_construct(
        pieces=(top_front, top_back, *shelves), overall_size=(1200.0, 350.0, 400.0)
    )
    check = _levels(report, CASES["tv-stand"])
    assert check.passed is False
    assert check.detail == (
        "board tops at 400; too sparse to count: 188 (27% of the plan); "
        "1 levels, asked 2"
    )


def test_only_the_height_is_checked_when_only_the_height_is_asked():
    stool = CASES["step-stool"].model_copy(
        update={"size": Size(height=600, tolerance=20)}
    )
    checks = check_design(SIDE_TABLE, stool)
    assert checks["size"].passed is True
    assert checks["orientation"].passed is None


def test_no_design_fails_every_asked_check(tmp_path):
    checks = check_design(find_design(tmp_path, "side-table"), CASES["side-table"])
    assert {name for name, check in checks.items() if check.passed is False} == {
        "valid",
        "size",
        "orientation",
        "lumber",
        "legs",
        "fasteners",
        "steps",
    }
    assert checks["valid"].detail == "no .nd file in the working directory"


def test_a_design_that_does_not_parse_fails_every_asked_check(tmp_path):
    broken = tmp_path / "side-table.nd"
    broken.write_text("(leg:2x4 =)\n")
    checks = check_design(broken, CASES["side-table"])
    assert checks["valid"].passed is False
    assert "does not assemble" in checks["valid"].detail


def test_the_design_named_after_the_case_is_chosen(tmp_path):
    (tmp_path / "draft.nd").write_text("")
    (tmp_path / "side_table.nd").write_text("")
    assert find_design(tmp_path, "side-table") == tmp_path / "side_table.nd"
    (tmp_path / "side_table.nd").unlink()
    assert find_design(tmp_path, "side-table") == tmp_path / "draft.nd"
    (tmp_path / "other.nd").write_text("")
    # The agent never sees the case's name: of several, the last one it
    # checked, else the newest
    assert find_design(tmp_path, "side-table", "draft.nd") == tmp_path / "draft.nd"
    os.utime(tmp_path / "draft.nd", (1, 1))
    assert find_design(tmp_path, "side-table") == tmp_path / "other.nd"
    assert find_design(tmp_path, "side-table", "gone.nd") == tmp_path / "other.nd"


def test_no_nd_file_is_no_design(tmp_path):
    assert find_design(tmp_path, "side-table") is None
