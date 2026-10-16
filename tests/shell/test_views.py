"""Where the views look from and where piece labels go."""

from pathlib import Path

import pytest

from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.shell.views import VIEWS, axis_view, project, visible_labels

ROOT = Path(__file__).parents[2]
SHELF = (ROOT / "skills" / "design" / "examples" / "two-tier-shelf.nd").read_text()
VIEW = {view.caption: view for view in VIEWS}


def _labels(source: str, caption: str) -> list[str]:
    assembly = Assembly.of(parse_dsl(source))
    return [label.piece_id for label in visible_labels(assembly, VIEW[caption])]


def test_the_views_are_the_drawings():
    assert [(v.caption, v.origin, v.up, v.column, v.row) for v in VIEWS] == [
        ("from +z", (0, 0, 100), (0, 1, 0), 0, 0),
        ("from -y", (0, -100, 0), (0, 0, 1), 0, 1),
        ("from +x +y +z", (100, 100, 100), (0, 0, 1), 1, 0),
        ("from +x", (100, 0, 0), (0, 0, 1), 1, 1),
    ]


@pytest.mark.parametrize("view", VIEWS, ids=lambda v: v.caption)
def test_projection_matches_build123d(view):
    build123d = pytest.importorskip("build123d")
    box = build123d.Pos(10, 20, 30) * build123d.Box(4, 6, 8, align=None)
    visible, _ = box.project_to_viewport(view.origin, view.up, look_at=(0, 0, 0))
    drawn = build123d.Compound(children=list(visible)).bounding_box()
    corners = [
        project(view, (x, y, z)) for x in (10, 14) for y in (20, 26) for z in (30, 38)
    ]
    assert min(x for x, _ in corners) == pytest.approx(drawn.min.X)
    assert max(x for x, _ in corners) == pytest.approx(drawn.max.X)
    assert min(y for _, y in corners) == pytest.approx(drawn.min.Y)
    assert max(y for _, y in corners) == pytest.approx(drawn.max.Y)


def test_a_shelf_under_the_top_is_labelled_from_the_side_not_from_above():
    shelves = {"shelf_1", "shelf_2", "shelf_3", "shelf_4"}
    assert shelves.isdisjoint(_labels(SHELF, "from +z"))
    assert shelves <= set(_labels(SHELF, "from -y"))


def test_touching_pieces_do_not_hide_each_other():
    # b stands right beside a, face to face
    source = "(a:2x4 =400)\n(b:2x4 =400)\na -[RF<0 LF<0]- b\n"
    assert _labels(source, "from +z") == ["a", "b"]
    assert _labels(source, "from -y") == ["a", "b"]
    # Seen from +x, b is in front of a
    assert _labels(source, "from +x") == ["b"]


def test_labels_sit_on_their_piece():
    assembly = Assembly.of(parse_dsl(SHELF))
    for view in VIEWS:
        for label in visible_labels(assembly, view):
            piece = assembly.model.pieces[label.piece_id]
            low, high = assembly.placement.poses[label.piece_id].bounds(piece)
            corners = [
                project(view, (x, y, z))
                for x in (low.x, high.x)
                for y in (low.y, high.y)
                for z in (low.z, high.z)
            ]
            assert min(x for x, _ in corners) <= label.x <= max(x for x, _ in corners)
            assert min(y for _, y in corners) <= label.y <= max(y for _, y in corners)


def test_axis_views_match_the_views_they_share_a_caption_with():
    shared = {view.caption: view for view in VIEWS}
    for axis in range(3):
        for sign in (1, -1):
            view = axis_view(axis, sign)
            if view.caption in shared:
                assert (view.origin, view.up) == (
                    shared[view.caption].origin,
                    shared[view.caption].up,
                )


def test_axis_views_look_from_their_side_with_z_up():
    assert axis_view(0, -1).caption == "from -x"
    assert axis_view(0, -1).origin == (-100.0, 0.0, 0.0)
    assert axis_view(1, 1).up == (0, 0, 1)
    # Looking along z, +y is up
    assert axis_view(2, -1).up == (0, 1, 0)
