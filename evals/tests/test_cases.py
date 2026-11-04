"""Tests for the design requests of the evaluation."""

import pytest
from pydantic import ValidationError

from evals.design.cases import Case, load_case, load_cases


def test_all_ten_cases_load():
    cases = load_cases()
    assert len(cases) == 10
    assert len({case.name for case in cases}) == 10


def test_the_core_set_is_the_five_starred_cases():
    names = [case.name for case in load_cases("core")]
    assert names == [
        "bookshelf",
        "plant-stand",
        "shoe-rack",
        "side-table",
        "step-stool",
    ]


def test_held_out_cases_stay_out_of_all_and_core():
    # They check whether a change to the skill fits only the ten cases it
    # was tuned on
    held = load_cases("heldout")
    assert len(held) == 5 and all(case.heldout for case in held)
    assert not any(case.heldout for case in load_cases())
    assert not any(case.heldout for case in load_cases("core"))


def test_every_request_says_not_to_ask_and_where_to_write():
    for case in [*load_cases(), *load_cases("heldout")]:
        assert ("質問はせず" in case.request) or (
            "Don't ask questions" in case.request
        ), case.name


def test_cases_are_picked_by_name():
    assert [case.name for case in load_cases("desk,bench")] == ["bench", "desk"]


def test_an_unknown_name_lists_the_known_ones():
    with pytest.raises(
        ValueError,
        match="Unknown case dsk; use all, core, heldout or names from bench",
    ):
        load_cases("dsk")


def test_a_misspelt_requirement_is_refused(tmp_path):
    path = tmp_path / "typo.toml"
    path.write_text(
        'request = "x"\n[size]\nheight = 1\n[lumber]\nallowed = ["2x4"]\n[leggs]\ncount = 4\n'
    )
    with pytest.raises(ValidationError, match="leggs"):
        load_case(path)


def test_a_case_carries_its_requirements():
    case = next(case for case in load_cases() if case.name == "bookshelf")
    assert isinstance(case, Case)
    assert case.levels is not None and case.levels.count == 4 and case.levels.equal
    assert case.legs is None
