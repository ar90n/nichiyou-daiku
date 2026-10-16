"""Tests for the parts to make: holes, groups and the faces of a drawing."""

from pathlib import Path

import numpy as np
import pytest

from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.assembly.parts import (
    FACE_ORDER,
    LocalHole,
    _same_holes,
    edge_neighbours,
    face_frame,
    face_letters,
    face_point,
    face_size,
    part_groups,
    piece_holes,
    view_direction,
)
from nichiyou_daiku.core.placement import face_normal
from nichiyou_daiku.dsl import parse_dsl

SHELF = (
    Path(__file__).parents[2] / "skills" / "design" / "examples" / "two-tier-shelf.nd"
).read_text()
# The screwed shelf of patterns.md: the screws go through the posts
SCREWED = """(side_l:2x4 =800)
(side_r:2x4 =800)
(shelf_bottom:2x4 =600)
(shelf_top:2x4 =600)
shelf_bottom -[DL<0 BL<100 S(Slim:3.8x65)]- side_l
shelf_bottom -[TL<0 FL<100 S(Slim:3.8x65)]- side_r
shelf_top -[DL<0 BL>38 S(Slim:3.8x65)]- side_l
shelf_top -[TL<0 FL>38 S(Slim:3.8x65)]- side_r
"""
LEG = (89.0, 38.0, 781.0)
# A 2x2 rung dowelled into two posts by its ends
RUNG = """(post_l:2x4 =600)
(post_r:2x4 =600)
(rung:2x2 =400)
post_l -[RF<300 DF<0 D(:8x30)]- rung
post_r -[LF<300 TF<0 D(:8x30)]- rung
"""


@pytest.fixture(scope="module")
def shelf() -> Assembly:
    return Assembly.of(parse_dsl(SHELF))


def _groups(assembly: Assembly) -> list[tuple[str, ...]]:
    return [group.pieces for group in part_groups(assembly)]


def test_piece_holes_are_in_the_pieces_own_axes(shelf):
    holes = piece_holes(shelf, "leg_1")
    assert len(holes) == 10
    back = sorted(h.point for h in holes if h.face == "back")
    # Dowels for the side aprons, 19 from the edge the left face is on
    assert back[0] == pytest.approx((70.0, 0.0, 172.25))
    assert {h.diameter for h in holes} == {8.0}
    assert {h.depth for h in holes} == {15.0}


def test_pieces_made_the_same_are_one_group(shelf):
    groups = _groups(shelf)
    assert ("shelf_1", "shelf_2", "shelf_3", "shelf_4") in groups
    assert ("top_1", "top_2", "top_3", "top_4", "top_5", "top_6") in groups
    assert len(groups) == 10


def test_a_part_is_named_by_its_pieces(shelf):
    groups = {group.pieces[0]: group for group in part_groups(shelf)}
    assert groups["leg_1"].name == "leg_1"
    assert groups["shelf_1"].name == "shelf_1, shelf_2, shelf_3, shelf_4 ×4"


def test_mirrored_pieces_are_different_parts(shelf):
    # The left and right front legs mirror each other: no turn matches them
    groups = _groups(shelf)
    assert ("leg_1",) in groups
    assert ("leg_2",) in groups


def test_pieces_matching_after_a_turn_are_one_part():
    # The right post is the left post turned half about its length
    groups = _groups(Assembly.of(parse_dsl(SCREWED)))
    assert groups == [("side_l", "side_r"), ("shelf_bottom", "shelf_top")]


@pytest.mark.parametrize("contact", ["FT", "BT"])
def test_boards_turned_end_for_end_are_one_part(contact):
    # b's holes are near its top end, a's near its down end: turning b end
    # for end, about its width (FT) or its thickness (BT), matches them
    source = (
        "(post:2x4 =800)\n(a:2x4 =300)\n(b:2x4 =300)\n"
        "post -[FL<100 BD<0 D(:8x30)]- a\n"
        f"post -[FL<500 {contact}<0 D(:8x30)]- b\n"
    )
    assert ("a", "b") in _groups(Assembly.of(parse_dsl(source)))


def test_square_boards_turned_a_quarter_are_one_part():
    # a is drilled on its back, b on its left: a quarter turn apart
    source = (
        "(post:2x4 =800)\n(a:2x2 =300)\n(b:2x2 =300)\n"
        "post -[FL<100 BD<0 D(:8x30)]- a\n"
        "post -[FL<500 LD<0 D(:8x30)]- b\n"
    )
    assert ("a", "b") in _groups(Assembly.of(parse_dsl(source)))


def test_through_holes_have_no_depth():
    assembly = Assembly.of(parse_dsl(SCREWED))
    post = piece_holes(assembly, "side_l")
    shelf = piece_holes(assembly, "shelf_bottom")
    assert {h.depth for h in post} == {None}
    assert {h.depth for h in shelf} == {27.0}
    assert {h.diameter for h in post + shelf} == {2.5}


def test_holes_match_within_the_tolerance():
    one = (LocalHole("back", (10.0, 0.0, 100.0), 8.0, 15.0),)
    near = (LocalHole("back", (10.04, 0.0, 100.0), 8.0, 15.0),)
    far = (LocalHole("back", (10.06, 0.0, 100.0), 8.0, 15.0),)
    assert _same_holes(one, near)
    assert not _same_holes(one, far)


def test_every_face_is_seen_from_outside():
    for face in FACE_ORDER:
        right, up = face_frame(face)
        assert np.cross(right, up) == pytest.approx(face_normal(face))


def test_long_faces_have_the_down_end_on_the_left():
    for face in ("front", "back", "left", "right"):
        right, _ = face_frame(face)
        assert tuple(right) == (0.0, 0.0, 1.0)
        assert edge_neighbours(face)["left"] == "down"


def test_face_points_are_measured_from_the_lower_left_corner(shelf):
    holes = piece_holes(shelf, "leg_1")
    back = sorted(face_point("back", h.point, LEG) for h in holes if h.face == "back")
    assert back[0] == pytest.approx((172.25, 19.0))
    top = sorted(face_point("top", h.point, LEG) for h in holes if h.face == "top")
    assert top == [pytest.approx((22.25, 19.0)), pytest.approx((66.75, 19.0))]
    assert face_size("back", LEG) == (781.0, 89.0)
    assert face_size("top", LEG) == (89.0, 38.0)


def test_neighbours_across_each_edge():
    assert edge_neighbours("back")["top"] == "left"
    assert edge_neighbours("back")["bottom"] == "right"
    assert edge_neighbours("top") == {
        "top": "front",
        "bottom": "back",
        "left": "left",
        "right": "right",
    }


def test_drilled_faces_are_lettered_in_order(shelf):
    holes = piece_holes(shelf, "leg_1")
    assert face_letters(holes, LEG) == {"back": "A", "left": "B", "top": "C"}


def test_ends_without_a_drilled_long_face_get_a_reference_when_turning_matters():
    size = (89.0, 38.0, 400.0)
    centred = (
        LocalHole("top", (44.5, 19.0, 400.0), 8.0, 15.0),
        LocalHole("down", (44.5, 19.0, 0.0), 8.0, 15.0),
    )
    # The same holes after a half turn: no reference needed
    assert face_letters(centred, size) == {"top": "A", "down": "B"}
    off_centre = (
        LocalHole("top", (20.0, 19.0, 400.0), 8.0, 15.0),
        LocalHole("down", (20.0, 19.0, 0.0), 8.0, 15.0),
    )
    assert face_letters(off_centre, size) == {"top": "A", "down": "B", "front": "C"}


def test_square_ends_get_a_reference_when_a_quarter_turn_matters():
    # Each end's pair looks the same turned half, but one end drilled a
    # quarter turn off would not fit: the front ties the two ends
    rung = next(
        group
        for group in part_groups(Assembly.of(parse_dsl(RUNG)))
        if group.pieces == ("rung",)
    )
    assert face_letters(rung.holes, rung.size) == {
        "top": "A",
        "down": "B",
        "front": "C",
    }
    centred = (
        LocalHole("top", (19.0, 19.0, 400.0), 8.0, 15.0),
        LocalHole("down", (19.0, 19.0, 0.0), 8.0, 15.0),
    )
    assert face_letters(centred, (38.0, 38.0, 400.0)) == {"top": "A", "down": "B"}


def test_view_shows_the_most_lettered_faces():
    assert view_direction(["back", "left", "top"]) == (-1, -1, 1)
    # A tie keeps the first diagonal
    assert view_direction(["top"]) == (1, 1, 1)
