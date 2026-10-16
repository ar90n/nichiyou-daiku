"""Tests for planning the assembly steps."""

from pathlib import Path

import pytest

from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.assembly.steps import _view, plan_steps
from nichiyou_daiku.dsl import parse_dsl

SHELF = (
    Path(__file__).parents[2] / "skills" / "design" / "examples" / "two-tier-shelf.nd"
).read_text()
# The example builds the side frames, joins them, then the shelf and the top
SHELF_WITHOUT_STEPS = SHELF[: SHELF.index("steps {")]
# Edges along z (posts to rail), y (rail to block) and x (block to cap)
CHAIN = (
    "(post_a:2x4 =400)\n(post_b:2x4 =400)\n(rail:2x4 =224)\n(block:2x4 =100)\n"
    "(cap:2x4 =60)\n"
    "post_a -[BR<150 DB<0]- rail\n"
    "post_b -[FR<150 TB<0]- rail\n"
    "rail -[RF<50 BT<0]- block\n"
    "block -[RF<10 BT<0]- cap\n"
)


@pytest.fixture(scope="module")
def shelf() -> Assembly:
    return Assembly.of(parse_dsl(SHELF))


@pytest.fixture(scope="module")
def plan(shelf):
    return plan_steps(shelf)


def test_declared_steps_keep_their_names_and_pieces(plan):
    assert plan.declared
    assert [step.name for step in plan.steps] == [
        "Left frame",
        "Right frame",
        "Join",
        "Shelf",
        "Top",
    ]
    assert plan.steps[3].pieces == ("shelf_1", "shelf_2", "shelf_3", "shelf_4")
    assert [step.number for step in plan.steps] == [1, 2, 3, 4, 5]


def test_step_kinds(plan):
    # The right frame is built apart, then the aprons join the two frames
    assert [step.kind for step in plan.steps] == [
        "first",
        "sub-assembly",
        "join",
        "attach",
        "attach",
    ]


def test_each_connection_is_made_once_when_its_later_piece_goes_on(plan, shelf):
    made = [key for step in plan.steps for key in step.connections]
    assert sorted(made) == sorted(shelf.model.connections)
    # Pieces of the same step are joined in that step
    assert ("leg_1", "apron_upper_left") in plan.steps[0].connections
    # The front and back aprons join the legs of both frames
    assert len(plan.steps[2].connections) == 8


def test_a_step_shows_the_part_it_leaves(plan):
    assert plan.steps[1].shown == (
        "leg_2",
        "leg_4",
        "apron_upper_right",
        "apron_lower_right",
    )
    assert len(plan.steps[2].shown) == 12
    assert len(plan.steps[4].shown) == 22


def test_frames_are_seen_from_the_side_and_boards_from_above(plan):
    # (axis, side): 0 = x, 2 = z
    assert [step.view for step in plan.steps] == [
        (0, 1),
        (0, 1),
        (0, 1),
        (2, 1),
        (2, 1),
    ]


def test_without_steps_each_step_adds_one_piece():
    plan = plan_steps(Assembly.of(parse_dsl(SHELF_WITHOUT_STEPS)))
    assert not plan.declared
    assert plan.steps[0].name is None
    # The first piece and the first piece touching it, then whatever touches
    # what is built, in declaration order
    assert [step.pieces for step in plan.steps[:4]] == [
        ("leg_1", "apron_upper_front"),
        ("leg_2",),
        ("apron_upper_left",),
        ("leg_3",),
    ]
    assert len(plan.steps) == 21


def test_without_steps_unconnected_pieces_start_new_parts():
    plan = plan_steps(Assembly.of(parse_dsl("(a:2x4 =400)\n(b:2x4 =400)\n")))
    assert [step.pieces for step in plan.steps] == [("a",), ("b",)]
    assert [step.kind for step in plan.steps] == ["first", "sub-assembly"]


def test_a_single_piece_is_one_step():
    plan = plan_steps(Assembly.of(parse_dsl("(post:2x4 =400)")))
    assert [step.pieces for step in plan.steps] == [("post",)]


def test_view_avoids_every_measured_axis(shelf):
    # The apron is placed along z (up the legs), the shelf board along x
    view = _view(
        shelf,
        ("apron_lower_front", "shelf_1"),
        (("leg_1", "apron_lower_front"), ("apron_lower_front", "shelf_1")),
        tuple(shelf.model.pieces),
    )
    assert view[0] == 1


def test_view_looks_from_where_the_rest_hides_the_new_piece_least(shelf):
    pieces = tuple(shelf.model.pieces)
    # The back apron hides the front one from -y, and the other way round
    assert _view(
        shelf, ("apron_lower_front",), (("leg_1", "apron_lower_front"),), pieces
    ) == (1, 1)
    assert _view(
        shelf, ("apron_lower_back",), (("leg_3", "apron_lower_back"),), pieces
    ) == (1, -1)


def test_view_ignores_the_measured_axes_when_they_are_all_three():
    assembly = Assembly.of(parse_dsl(CHAIN))
    pieces, shown = ("rail", "block", "cap"), tuple(assembly.model.pieces)
    assert _view(assembly, pieces, tuple(assembly.model.connections), shown) == _view(
        assembly, pieces, (), shown
    )
