"""Tests for which dimensions the technical drawing writes."""

from pathlib import Path

import pytest

from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.shell.dimensioning import Chain, _stops, chain_for, chains, spread

SHELF = (
    Path(__file__).parents[2] / "skills" / "design" / "examples" / "two-tier-shelf.nd"
)


def _chains(source: str) -> dict[tuple[str, str], Chain]:
    return {
        (chain.view, chain.axis): chain
        for chain in chains(Assembly.of(parse_dsl(source)))
    }


@pytest.fixture(scope="module")
def shelf() -> dict[tuple[str, str], Chain]:
    return _chains(SHELF.read_text())


def _texts(chain: Chain) -> list[str]:
    return [segment.text for segment in chain.segments]


def _lumber(chain: Chain) -> list[bool]:
    return [segment.lumber for segment in chain.segments]


def test_heights_stop_at_both_ends_of_every_piece(shelf):
    chain = shelf[("from -y", "z")]
    assert chain.side == "left"
    assert chain.stops == pytest.approx((0, 150, 239, 277, 692, 781, 800))
    assert _texts(chain) == ["150", "89", "38", "415", "89", "19"]
    # Apron widths and board thicknesses are lumber sizes; the gaps are not
    assert _lumber(chain) == [False, True, True, False, True, True]
    assert chain.overall.text == "800"


def test_front_and_side_stop_at_the_legs(shelf):
    front = shelf[("from -y", "x")]
    side = shelf[("from +x", "y")]
    assert (front.side, side.side) == ("below", "below")
    assert _texts(front) == ["89", "422", "89"]
    assert _lumber(front) == [True, False, True]
    assert _texts(side) == ["38", "224", "38"]
    assert _lumber(side) == [True, False, True]
    assert (front.overall.text, side.overall.text) == ("600", "300")


def test_top_view_stops_at_the_top_boards_and_their_gaps(shelf):
    # The lower shelf boards sit at other x positions and are left out
    chain = shelf[("from +z", "x")]
    assert _texts(chain) == ["89", "13.2"] * 5 + ["89"]
    assert _lumber(chain) == [True, False] * 5 + [True]


def test_axis_without_stops_between_the_ends_has_only_the_overall_size(shelf):
    # The top boards all run the full depth
    chain = shelf[("from +z", "y")]
    assert chain.side == "left"
    assert chain.segments == ()
    assert chain.overall.text == "300"


def test_unconnected_pieces_get_no_dimensions():
    assert chains(Assembly.of(parse_dsl("(a:2x4 =400)\n(b:2x4 =400)\n"))) == []


def test_a_single_piece_has_overall_sizes_only():
    found = chains(Assembly.of(parse_dsl("(post:2x4 =500)")))
    assert len(found) == 5
    assert all(chain.segments == () for chain in found)


def test_stops_closer_than_the_printed_precision_are_merged():
    assert _stops([10.0, 10.03, 19.98, -5.0, 25.0], 0.0, 20.0) == (0.0, 10.0, 20.0)


def test_spread_leaves_labels_that_do_not_touch_where_they_want_to_be():
    assert spread([0.0, 10.0], [2.0, 2.0], -100.0, 100.0, 1.0) == ([0.0, 10.0], True)


def test_spread_centres_touching_labels_on_their_wishes():
    # Two 2mm labels 1mm apart take 5mm, centred on 0.5
    assert spread([0.0, 1.0], [2.0, 2.0], -100.0, 100.0, 1.0) == ([-1.0, 2.0], True)


def test_spread_moves_labels_inside_the_range():
    assert spread([0.0], [4.0], 0.0, 10.0, 1.0) == ([2.0], True)
    assert spread([10.0], [4.0], 0.0, 10.0, 1.0) == ([8.0], True)


def test_spread_says_when_labels_do_not_fit():
    centres, fits = spread([0.0, 1.0, 2.0], [4.0, 4.0, 4.0], 0.0, 10.0, 1.0)
    assert centres == [2.0, 7.0, 12.0]
    assert not fits


def test_spread_keeps_order_and_never_overlaps():
    wanted = [0.0, 0.2, 0.4, 5.0, 5.1, 9.0, 9.5, 9.9]
    sizes = [3.0, 1.0, 2.0, 4.0, 1.5, 2.5, 1.0, 3.0]
    centres, fits = spread(wanted, sizes, -50.0, 50.0, 1.2)
    assert fits
    for i in range(len(wanted) - 1):
        assert centres[i + 1] - centres[i] >= (sizes[i] + sizes[i + 1]) / 2 + 1.2 - 1e-9


def test_spread_of_nothing_fits():
    assert spread([], [], 0.0, 1.0, 1.0) == ([], True)


def test_a_chain_can_cover_some_pieces_only():
    assembly = Assembly.of(parse_dsl(SHELF.read_text()))
    frame = ["leg_1", "leg_3", "apron_upper_left", "apron_lower_left"]
    bounds = {
        p: assembly.placement.poses[p].bounds(assembly.model.pieces[p]) for p in frame
    }
    chain = chain_for(
        "from +x", "y", "below", bounds, dict(assembly.model.pieces), frame
    )
    # The frame alone: 38 + 224 + 38 deep, the legs' faces as stops
    assert [segment.text for segment in chain.segments] == ["38", "224", "38"]
    assert chain.overall.text == "300"
    assert chain.view == "from +x"
