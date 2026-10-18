"""Tests for the machine checks of a design."""

from pathlib import Path

from evals.design.cases import Fasteners, Legs, Levels, Lumber, Shelf, Size, load_cases
from evals.design.checks import CHECKS, check_design, find_design

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


def test_levels_count_boards_and_their_spacing():
    shelf = CASES["two-tier-shelf"]
    # The shelf's boards: the 2x4 shelf on the lower aprons and the 1x4 top
    two = shelf.model_copy(update={"levels": Levels(count=2, equal=True, top=True)})
    assert check_design(SHELF, two)["levels"].passed is True
    three = shelf.model_copy(update={"levels": Levels(count=3)})
    assert "2 levels, asked 3" in check_design(SHELF, three)["levels"].detail


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
    assert checks["valid"].detail == "no single .nd file in the working directory"


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
    assert find_design(tmp_path, "side-table") is None
