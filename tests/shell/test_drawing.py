"""Tests for the technical drawing: layout, scale and dimensions."""

from datetime import date
from itertools import combinations
from pathlib import Path

import pytest

pytest.importorskip("build123d")

from build123d import Compound  # noqa: E402

import nichiyou_daiku.shell.drawing as drawing_module  # noqa: E402
from nichiyou_daiku.core.assembly import Assembly  # noqa: E402
from nichiyou_daiku.dsl import parse_dsl  # noqa: E402
from nichiyou_daiku.shell.build123d_export import assembly_to_build123d  # noqa: E402
from nichiyou_daiku.shell.dimensioning import CrowdedDimensionsWarning  # noqa: E402
from nichiyou_daiku.shell.drawing import (  # noqa: E402
    FIRST,
    PAD,
    _arrow_points,
    _compose,
    _crowded_advice,
    _frame,
    technical_drawing,
)

ROOT = Path(__file__).parents[2]
EXAMPLES = sorted(
    [
        *(ROOT / "examples" / "nd_files").glob("*.nd"),
        *(ROOT / "skills" / "design" / "examples").glob("*.nd"),
    ]
)
SHELF = ROOT / "skills" / "design" / "examples" / "two-tier-shelf.nd"
CORNER = "(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n"
# 39 slats 12.5mm apart up a 2m post: far too many gaps to number on A3
CROWDED = "(rail:2x4 =2000)\n" + "".join(
    f"(s{i}:2x2 =300)\nrail -[RF<{i * 50.5:g} BT<0]- s{i}\n" for i in range(39)
)
ORTHOGRAPHIC = ("from +z", "from -y", "from +x")


def _model(source: str) -> tuple[Compound, Assembly]:
    assembly = Assembly.of(parse_dsl(source))
    return assembly_to_build123d(assembly, fillet_radius=0), assembly


def _sheet(source: str, dimensions: bool = True):
    part, assembly = _model(source)
    return _compose(part, assembly if dimensions else None, "A3")


@pytest.fixture(scope="module")
def sheets():
    return {path.name: _sheet(path.read_text()) for path in EXAMPLES}


@pytest.fixture(scope="module")
def shelf(sheets):
    return sheets[SHELF.name]


@pytest.fixture(scope="module")
def shelf_model() -> tuple[Compound, Assembly]:
    return _model(SHELF.read_text())


@pytest.fixture(scope="module")
def part() -> Compound:
    return _model(CORNER)[0]


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _within(inner, outer) -> bool:
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and inner[2] <= outer[2]
        and inner[3] <= outer[3]
    )


def _crosses(rect, segment, margin: float = 1e-6) -> bool:
    """Whether a segment passes through the inside of a rectangle
    (Liang-Barsky clipping; touching the edge does not count)."""
    x0, y0, x1, y1 = (
        rect[0] + margin,
        rect[1] + margin,
        rect[2] - margin,
        rect[3] - margin,
    )
    (ax, ay), (bx, by) = segment
    dx, dy = bx - ax, by - ay
    start, end = 0.0, 1.0
    for p, q in ((-dx, ax - x0), (dx, x1 - ax), (-dy, ay - y0), (dy, y1 - ay)):
        if p == 0:
            if q < 0:
                return False
        elif p < 0:
            start = max(start, q / p)
        else:
            end = min(end, q / p)
    return start <= end


def _segments(sheet):
    """Every dimension line, leader and arrow edge."""
    segments = list(sheet.dimensions.lines)
    for arrow in sheet.dimensions.arrows:
        a, b, c = _arrow_points(*arrow)
        segments += [(a, b), (b, c), (c, a)]
    return segments


def _view_boxes(sheet):
    return [view.box for view in sheet.views.values()]


def _problems(sheet) -> list:
    """Every overlap, every escape from the drawing area, every crowded chain."""
    boxes = [label.box for label in sheet.dimensions.labels]
    views = _view_boxes(sheet)
    return (
        [(b, s) for b in boxes for s in _segments(sheet) if _crosses(b, s)]
        + [(a, b) for a, b in combinations(boxes + views, 2) if _overlap(a, b)]
        + [
            box
            for box in views + boxes
            if not _within(box, sheet.frame) or _overlap(box, sheet.title_block)
        ]
        + sheet.dimensions.crowded
    )


def _texts(sheet, view, side):
    return [
        label.text
        for label in sheet.dimensions.labels
        if label.view == view and label.side == side
    ]


# Layout and scale


def test_frame_and_title_block_follow_build123d():
    # A3: the frame is 390 x 260 around the page centre; the title block
    # fills the bottom right quarter of its height
    assert _frame("A3") == ((-195.0, -130.0, 195.0, 130.0), (0.0, -130.0, 195.0, -65.0))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_views_stay_inside_the_frame_and_off_the_title_block(sheets, path):
    sheet = sheets[path.name]
    for box in _view_boxes(sheet):
        assert _within(box, sheet.frame)
        assert not _overlap(box, sheet.title_block)


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_views_do_not_overlap(sheets, path):
    for a, b in combinations(_view_boxes(sheets[path.name]), 2):
        assert not _overlap(a, b)


def test_orthographic_views_line_up_in_third_angle(shelf):
    top, front, side = (shelf.views[c].box for c in ORTHOGRAPHIC)
    assert top[0] == pytest.approx(front[0])  # top above front, same left edge
    assert top[1] > front[3]
    assert side[3] == pytest.approx(front[3])  # side right of front, same top
    assert side[0] > front[2]


def test_drawn_size_is_the_scale_written(shelf):
    # The shelf is 600 x 300 x 800
    front, side = shelf.views["from -y"].box, shelf.views["from +x"].box
    assert front[2] - front[0] == pytest.approx(600 / shelf.denominator)
    assert front[3] - front[1] == pytest.approx(800 / shelf.denominator)
    assert side[2] - side[0] == pytest.approx(300 / shelf.denominator)


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_scale_denominator_has_one_decimal(sheets, path):
    denominator = sheets[path.name].denominator
    assert denominator * 10 == pytest.approx(round(denominator * 10))


def test_small_models_are_not_drawn_larger_than_life():
    assert _sheet("(block:2x2 =50)").denominator == 1.0


def test_title_block_shows_the_scale(part, monkeypatch):
    shown = {}

    class Recording(drawing_module.TechnicalDrawing):
        def __init__(self, **options):
            shown.update(options)
            super().__init__(**options)

    monkeypatch.setattr(drawing_module, "TechnicalDrawing", Recording)
    technical_drawing(part, title="t", drawing_number="1", designed_by="me")
    assert shown["drawing_scale"] == _compose(part, None, "A3").denominator


def test_dimension_bands_take_room_from_the_views(shelf, shelf_model):
    without = _compose(shelf_model[0], None, "A3")
    assert without.denominator < shelf.denominator


def test_unconnected_pieces_get_no_dimensions_and_no_bands():
    source = "(a:2x4 =400)\n(b:2x4 =400)\n"
    sheet = _sheet(source)
    assert sheet.dimensions.labels == []
    assert sheet.denominator == _sheet(source, dimensions=False).denominator


def _draw(part, path, **options):
    technical_drawing(
        part, title="Corner", drawing_number="ND-1", designed_by="me", **options
    ).write(str(path))
    return path.read_text()


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


# Dimensions


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_values_touch_no_line_and_no_other_value(sheets, path):
    sheet = sheets[path.name]
    boxes = [label.box for label in sheet.dimensions.labels]
    assert boxes
    assert [
        (box, segment)
        for box in boxes
        for segment in _segments(sheet)
        if _crosses(box, segment)
    ] == []
    assert [(a, b) for a, b in combinations(boxes, 2) if _overlap(a, b)] == []


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_dimensions_stay_outside_the_views(sheets, path):
    sheet = sheets[path.name]
    for view in _view_boxes(sheet):
        assert not any(_crosses(view, segment) for segment in _segments(sheet))
        assert not any(_overlap(view, label.box) for label in sheet.dimensions.labels)


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_dimensions_stay_inside_the_frame_and_off_the_title_block(sheets, path):
    sheet = sheets[path.name]
    for a, b in _segments(sheet):
        for point in (a, b):
            assert _within((*point, *point), sheet.frame)
        assert not _crosses(sheet.title_block, (a, b))
    for label in sheet.dimensions.labels:
        assert _within(label.box, sheet.frame)
        assert not _overlap(label.box, sheet.title_block)


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_values_all_fit(sheets, path):
    assert sheets[path.name].dimensions.crowded == []


def test_vertical_values_sit_left_of_their_dimension_line(shelf):
    # JIS: read from the right of the page, so above the line is its left
    for caption in ("from -y", "from +z"):
        line = shelf.views[caption].box[0] - FIRST
        boxes = [
            label.box
            for label in shelf.dimensions.labels
            if label.view == caption and label.side == "left"
        ]
        assert boxes
        assert all(box[2] <= line - PAD + 1e-6 for box in boxes)


def test_shelf_values(shelf):
    heights = _texts(shelf, "from -y", "left")
    # 19 (the top boards' thickness) is lumber and does not fit at this scale
    assert sorted(heights) == sorted(["150", "89", "38", "415", "89", "800"])
    assert sorted(_texts(shelf, "from -y", "below")) == ["422", "600", "89", "89"]
    assert sorted(_texts(shelf, "from +x", "below")) == ["224", "300", "38", "38"]
    top = _texts(shelf, "from +z", "below")
    assert top.count("13.2") == 5 and top.count("600") == 1
    assert _texts(shelf, "from +z", "left") == ["300"]


@pytest.mark.parametrize("page_size", ["A4", "A1"])
def test_smallest_and_largest_pages_are_clean(shelf_model, page_size):
    assert _problems(_compose(*shelf_model, page_size)) == []


def test_wide_model_is_clean():
    # The side view is 1.8m wide, so the width sets the scale
    assert _problems(_sheet("(a:2x4 =300)\n(b:2x4 =1800)\na -[TF<0 BD<0]- b\n")) == []


def test_fillets_do_not_change_the_drawn_size(shelf_model):
    assembly = shelf_model[1]
    part = assembly_to_build123d(assembly, fillet_radius=5)
    sheet = _compose(part, assembly, "A3")
    front = sheet.views["from -y"].box
    assert front[2] - front[0] == pytest.approx(600 / sheet.denominator)
    assert _problems(sheet) == []


@pytest.mark.parametrize(
    ("source", "page_size"),
    [("(board:1x4 =1800)", "A3"), ("(post:2x4 =2000)", "A4")],
)
def test_overall_values_wider_than_their_stretch_go_beside_it(source, page_size):
    # A 19mm or 38mm extent drawn this small has no room for its value
    part, assembly = _model(source)
    assert _problems(_compose(part, assembly, page_size)) == []


def test_no_dimensions_without_an_assembly(part):
    sheet = _compose(part, None, "A3")
    assert sheet.dimensions.lines == []
    assert sheet.dimensions.labels == []


def test_crowded_advice_names_the_next_larger_page():
    assert "--page-size A2" in _crowded_advice("A3")
    assert "--page-size A1" in _crowded_advice("A2")
    largest = _crowded_advice("A1")
    assert "--page-size" not in largest
    assert "--no-dimensions" in largest


def test_crowded_values_warn_and_say_what_to_do():
    part, assembly = _model(CROWDED)
    with pytest.warns(CrowdedDimensionsWarning, match="front view") as caught:
        technical_drawing(
            part, title="t", drawing_number="1", designed_by="me", assembly=assembly
        )
    message = str(caught[0].message)
    assert "--page-size A2" in message
    assert "--no-dimensions" in message
