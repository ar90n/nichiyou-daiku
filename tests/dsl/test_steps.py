"""Tests for the steps block of the DSL."""

from pathlib import Path

import pytest

from nichiyou_daiku.core.model import Step
from nichiyou_daiku.dsl import DSLSemanticError, DSLSyntaxError, parse_dsl

ROOT = Path(__file__).parents[2]
FRAME = (
    "(post_a:2x4 =400)\n(post_b:2x4 =400)\n(rail:2x4 =224)\n(block:2x4 =100)\n"
    "post_a -[BR<150 DB<0]- rail\n"
    "post_b -[FR<150 TB<0]- rail\n"
    "rail -[RF<50 BT<0]- block\n"
)
STEPS = 'steps {\n  "Frame": post_a, rail, post_b\n  "Block": block\n}\n'


def test_steps_block_lists_the_pieces_of_each_step():
    model = parse_dsl(FRAME + STEPS)
    assert model.steps == (
        Step(name="Frame", pieces=("post_a", "rail", "post_b")),
        Step(name="Block", pieces=("block",)),
    )


def test_steps_block_may_come_before_the_pieces():
    assert parse_dsl(STEPS + FRAME).steps == parse_dsl(FRAME + STEPS).steps


def test_a_file_without_steps_has_none():
    assert parse_dsl(FRAME).steps == ()


def test_only_one_steps_block_is_allowed():
    with pytest.raises(DSLSemanticError, match="Only one steps block is allowed"):
        parse_dsl(FRAME + STEPS + STEPS)


def test_a_wrong_steps_block_is_reported_where_it_is():
    source = FRAME + 'steps {\n  "Frame": post_a, rail, post_b\n}\n'
    with pytest.raises(DSLSemanticError, match="steps leaves out block") as error:
        parse_dsl(source)
    assert error.value.line == 8


def test_unknown_piece_in_a_step_names_a_close_one():
    source = FRAME + 'steps {\n  "Frame": post_a, rial, post_b, block\n}\n'
    with pytest.raises(DSLSemanticError, match="did you mean 'rail'"):
        parse_dsl(source)


def test_a_step_needs_a_piece():
    with pytest.raises(DSLSyntaxError):
        parse_dsl(FRAME + 'steps {\n  "Frame":\n}\n')


def test_steps_cannot_name_a_piece():
    with pytest.raises(DSLSemanticError, match="'steps' names the steps block"):
        parse_dsl("(steps:2x4 =400)\n")


def test_steps_survive_solving_unknowns():
    source = (ROOT / "examples" / "nd_files" / "simple_table_unknowns.nd").read_text()
    pieces = [
        line.split(":")[0].lstrip("(")
        for line in source.splitlines()
        if line.startswith("(")
    ]
    model = parse_dsl(source + 'steps {\n  "All": ' + ", ".join(pieces) + "\n}\n")
    assert model.pieces["apron_front"].length == 622.0
    assert model.steps == (Step(name="All", pieces=tuple(pieces)),)
