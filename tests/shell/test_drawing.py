"""Tests for the technical drawing layout."""

from datetime import date
from itertools import combinations

import pytest

pytest.importorskip("build123d")

from build123d import Compound  # noqa: E402

from nichiyou_daiku.core.assembly import Assembly  # noqa: E402
from nichiyou_daiku.dsl import parse_dsl  # noqa: E402
from nichiyou_daiku.shell.build123d_export import assembly_to_build123d  # noqa: E402
from nichiyou_daiku.shell.drawing import (  # noqa: E402
    VIEW_FILL,
    _layout_views,
    technical_drawing,
)

CORNER = "(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n"
A3_WIDTH, A3_HEIGHT = 420.0, 297.0


@pytest.fixture(scope="module")
def part() -> Compound:
    return assembly_to_build123d(Assembly.of(parse_dsl(CORNER)), fillet_radius=0)


def _bounds(view):
    return Compound(children=list(view.visible) + list(view.hidden)).bounding_box()


def _draw(part, path, **options):
    technical_drawing(
        part, title="Corner", drawing_number="ND-1", designed_by="me", **options
    ).write(str(path))
    return path.read_text()


def test_views_fit_inside_the_drawing_area_without_overlapping(part):
    boxes = [_bounds(view) for view in _layout_views(part, A3_WIDTH, A3_HEIGHT)]
    assert len(boxes) == 4
    # The drawing area leaves 20mm side margins and a 40mm title block,
    # and its centre sits 10mm above the page centre
    half_width = (A3_WIDTH - 40) / 2
    half_height = (A3_HEIGHT - 80) / 2
    for box in boxes:
        assert -half_width <= box.min.X and box.max.X <= half_width
        assert -half_height + 10 <= box.min.Y and box.max.Y <= half_height + 10
    for a, b in combinations(boxes, 2):
        assert (
            a.max.X <= b.min.X
            or b.max.X <= a.min.X
            or a.max.Y <= b.min.Y
            or b.max.Y <= a.min.Y
        )


def test_largest_view_fills_the_set_share_of_a_grid_cell(part):
    views = _layout_views(part, A3_WIDTH, A3_HEIGHT)
    cell = min((A3_WIDTH - 40) / 2 - 10, (A3_HEIGHT - 80) / 2 - 10)
    largest = max(max(box.size.X, box.size.Y) for box in map(_bounds, views))
    assert largest == pytest.approx(cell * VIEW_FILL)


def test_drawing_has_visible_and_hidden_lines(part, tmp_path):
    svg = _draw(part, tmp_path / "drawing.svg", design_date=date(2026, 1, 1))
    assert 'id="Visible"' in svg
    hidden_layer = svg.split('id="Hidden"', 1)[1].split("</g>", 1)[0]
    # Straight edges are written as <line>, curves as <path>
    assert "<line" in hidden_layer or "<path" in hidden_layer


def test_page_size_sets_the_border_and_ignores_case(part, tmp_path):
    def width(svg: str) -> float:
        return float(svg.split('width="', 1)[1].split("mm", 1)[0])

    a4 = width(_draw(part, tmp_path / "a4.svg", page_size="A4"))
    a3 = width(_draw(part, tmp_path / "a3.svg", page_size="a3"))
    assert a4 < a3


def test_unknown_page_size_is_rejected(part):
    with pytest.raises(ValueError, match="A0"):
        technical_drawing(
            part, title="t", drawing_number="1", designed_by="me", page_size="A0"
        )
