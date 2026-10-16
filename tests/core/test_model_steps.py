"""Tests for a model's assembly steps and what is checked about them."""

import pytest

from nichiyou_daiku.core.model import Model, Step, connected_parts
from nichiyou_daiku.dsl import parse_dsl

# Two posts joined by a rail, and a block on the rail
FRAME = parse_dsl(
    "(post_a:2x4 =400)\n(post_b:2x4 =400)\n(rail:2x4 =224)\n(block:2x4 =100)\n"
    "post_a -[BR<150 DB<0]- rail\n"
    "post_b -[FR<150 TB<0]- rail\n"
    "rail -[RF<50 BT<0]- block\n"
)


def _with_steps(*steps: Step) -> Model:
    return Model.of(FRAME.pieces.values(), FRAME.connections.values(), steps=steps)


def test_steps_are_kept_in_order():
    steps = (
        Step(name="Posts and rail", pieces=("post_a", "rail", "post_b")),
        Step(name="Block", pieces=("block",)),
    )
    assert _with_steps(*steps).steps == steps


def test_a_model_needs_no_steps():
    assert Model.of(FRAME.pieces.values(), FRAME.connections.values()).steps == ()


def test_every_piece_must_be_in_a_step():
    with pytest.raises(ValueError, match="steps leaves out block; add them to a step"):
        _with_steps(Step(name="Frame", pieces=("post_a", "rail", "post_b")))


def test_unknown_piece_names_a_close_one():
    with pytest.raises(
        ValueError, match="Step 'Frame' names unknown piece 'rial'; did you mean 'rail'"
    ):
        _with_steps(Step(name="Frame", pieces=("post_a", "rial", "post_b", "block")))


def test_a_piece_in_two_steps_is_an_error():
    with pytest.raises(
        ValueError, match="'rail' is in steps 'Frame' and 'Block'; keep it in one step"
    ):
        _with_steps(
            Step(name="Frame", pieces=("post_a", "rail", "post_b")),
            Step(name="Block", pieces=("block", "rail")),
        )


def test_a_piece_twice_in_one_step_is_an_error():
    with pytest.raises(ValueError, match="'rail' is twice in step 'Frame'"):
        _with_steps(
            Step(name="Frame", pieces=("post_a", "rail", "post_b", "block", "rail"))
        )


def test_an_empty_step_is_an_error():
    with pytest.raises(ValueError, match="Step 'Nothing' adds no pieces"):
        _with_steps(
            Step(name="Nothing", pieces=()),
            Step(name="All", pieces=("post_a", "rail", "post_b", "block")),
        )


def test_a_step_leaving_its_pieces_apart_is_an_error():
    # The two posts touch nothing but the rail, which comes later
    with pytest.raises(
        ValueError,
        match="Step 'Posts' leaves its pieces in 2 separate parts: split it into "
        "steps or connect the parts",
    ):
        _with_steps(
            Step(name="Posts", pieces=("post_a", "post_b")),
            Step(name="Rest", pieces=("rail", "block")),
        )


def test_a_step_may_start_a_separate_part():
    # The block alone is a part of its own until the rail joins it
    model = _with_steps(
        Step(name="Post", pieces=("post_a",)),
        Step(name="Block", pieces=("block",)),
        Step(name="Rail", pieces=("rail", "post_b")),
    )
    assert [step.name for step in model.steps] == ["Post", "Block", "Rail"]


def test_connected_parts_ignore_pairs_with_other_pieces():
    parts = connected_parts(["a", "b", "c"], [("a", "b"), ("b", "z")])
    assert sorted(sorted(part) for part in parts) == [["a", "b"], ["c"]]
