"""The check image: four labelled views on one square sheet."""

import re
import struct
from pathlib import Path

import pytest

pytest.importorskip("build123d")

from nichiyou_daiku.core.assembly import Assembly  # noqa: E402
from nichiyou_daiku.dsl import parse_dsl  # noqa: E402
from nichiyou_daiku.shell.build123d_export import assembly_to_build123d  # noqa: E402
from nichiyou_daiku.shell.render import render_sheet  # noqa: E402
from nichiyou_daiku.shell.views import VIEWS  # noqa: E402

ROOT = Path(__file__).parents[2]
SHELF = (ROOT / "skills" / "design" / "examples" / "two-tier-shelf.nd").read_text()
CORNER = "(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n"


def _sheet(source: str, size: int = 1400, title: str = "design.nd"):
    assembly = Assembly.of(parse_dsl(source))
    part = assembly_to_build123d(assembly, fillet_radius=0)
    return render_sheet(part, assembly, title=title, size=size)


@pytest.fixture(scope="module")
def shelf():
    return _sheet(SHELF, title="two-tier-shelf.nd")


def test_the_image_is_a_square_png_of_the_requested_size():
    png = _sheet(CORNER, size=600).png()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", png[16:24]) == (600, 600)


def test_lines_stay_at_least_a_pixel_wide():
    # At size/1000 they would be 0.4px here and all but vanish
    svg = _sheet(CORNER, size=400).svg
    group = re.search(r'<g [^>]*id="Visible"[^>]*>', svg).group(0)
    assert float(re.search(r'stroke-width="([\d.]+)"', group).group(1)) >= 1


def test_the_image_is_not_blank():
    image_module = pytest.importorskip("PIL.Image")
    import io

    png = _sheet(CORNER, size=400).png()
    image = image_module.open(io.BytesIO(png)).convert("L")
    dark = sum(1 for value in image.getdata() if value < 128)
    assert dark > 500


def _note_top(sheet) -> float:
    """Top edge of the note's highest line."""
    size = sheet.size
    note_size = max(10, size / 60)
    return size * 0.04 / 2 + (len(sheet.note) - 1) * note_size * 1.3 + note_size / 2


def test_views_sit_in_their_cells_at_one_scale(shelf):
    size = shelf.size
    margin = size * 0.04
    note_size = max(10, size / 60)
    # Room for three note lines below the views
    bottom = margin / 2 + 2 * note_size * 1.3 + note_size
    cell_width = (size - 2 * margin) / 2
    cell_height = (size - margin - bottom) / 2
    for view in VIEWS:
        x0, y0, x1, y1 = shelf.view_boxes[view.caption]
        left = margin + view.column * cell_width
        top = size - margin - view.row * cell_height
        assert left <= x0 < x1 <= left + cell_width
        assert top - cell_height <= y0 < y1 <= top
    # The largest view fills 90% of a cell's drawing area (below the caption)
    largest = max(max(x1 - x0, y1 - y0) for x0, y0, x1, y1 in shelf.view_boxes.values())
    assert largest == pytest.approx(min(cell_width, cell_height - margin) * 0.9)


@pytest.mark.parametrize("size", [400, 1400])
def test_the_note_stays_below_the_views(size):
    sheet = _sheet(SHELF, size=size, title="two-tier-shelf.nd")
    lowest = min(y0 for _, y0, _, _ in sheet.view_boxes.values())
    assert _note_top(sheet) <= lowest


def test_a_long_list_of_unlabelled_pieces_is_cut_short():
    # Forty boards face to face: from +x only the last shows, and from the
    # other directions their labels crowd each other out
    count = 40
    pieces = "".join(f"(shelf_board_{i:02d}:1x4 =300)\n" for i in range(count))
    joints = "".join(
        f"shelf_board_{i:02d} -[FL<0 BL<0]- shelf_board_{i + 1:02d}\n"
        for i in range(count - 1)
    )
    sheet = _sheet(pieces + joints, size=600, title="boards.nd")
    assert len(sheet.unlabelled) > 10
    assert len(sheet.note) <= 3
    assert sheet.note[-1].endswith("more)")
    lowest = min(y0 for _, y0, _, _ in sheet.view_boxes.values())
    assert _note_top(sheet) <= lowest


def test_labels_sit_inside_their_view(shelf):
    assert shelf.labels
    for label in shelf.labels:
        x0, y0, x1, y1 = shelf.view_boxes[label.caption]
        assert x0 <= label.x <= x1 and y0 <= label.y <= y1


def test_a_shelf_under_the_top_has_no_label_from_above(shelf):
    from_above = {
        label.piece_id for label in shelf.labels if label.caption == "from +z"
    }
    assert from_above.isdisjoint({"shelf_1", "shelf_2", "shelf_3", "shelf_4"})


def test_labels_in_one_view_do_not_overlap(shelf):
    height = max(10, shelf.size / 80)
    for view in VIEWS:
        boxes = [
            (
                label.x - len(label.piece_id) * height * 0.3,
                label.x + len(label.piece_id) * height * 0.3,
                label.y,
            )
            for label in shelf.labels
            if label.caption == view.caption
        ]
        for i, (a0, a1, ay) in enumerate(boxes):
            for b0, b1, by in boxes[i + 1 :]:
                assert not (a0 < b1 and b0 < a1 and abs(ay - by) < height)


def test_every_piece_is_labelled_or_listed(shelf):
    labelled = {label.piece_id for label in shelf.labels}
    pieces = set(Assembly.of(parse_dsl(SHELF)).model.pieces)
    assert labelled | set(shelf.unlabelled) == pieces
    assert labelled.isdisjoint(shelf.unlabelled)
    if shelf.unlabelled:
        assert shelf.note[1].startswith("not labelled: ")
        listed = " ".join(shelf.note[1:])
        assert all(piece_id in listed for piece_id in shelf.unlabelled)


def test_the_note_wraps_to_the_sheet_width():
    size = 600
    sheet = _sheet(SHELF, size=size, title="two-tier-shelf.nd")
    font = max(10, size / 60)
    assert len(sheet.note) >= 2
    for line in sheet.note:
        assert len(line) * font * 0.55 <= size - 2 * size * 0.04
        assert f">{line}</text>" in sheet.svg


def test_the_svg_has_the_captions_labels_and_note(shelf):
    for view in VIEWS:
        assert f">{view.caption}</text>" in shelf.svg
    for label in shelf.labels:
        assert f">{label.piece_id}</text>" in shelf.svg
    assert "two-tier-shelf.nd  600 x 300 x 800 mm (x × y × z)" in shelf.svg


def test_unconnected_pieces_are_noted():
    sheet = _sheet("(a:2x4 =400)\n(b:2x4 =300)\n", title="loose.nd")
    assert "loose.nd  pieces not connected" in sheet.svg
    assert sheet.png()[:8] == b"\x89PNG\r\n\x1a\n"


def test_a_single_piece_is_labelled_at_its_center():
    sheet = _sheet("(a:2x4 =400)\n")
    for label in sheet.labels:
        x0, y0, x1, y1 = sheet.view_boxes[label.caption]
        assert label.x == pytest.approx((x0 + x1) / 2)
        assert label.y == pytest.approx((y0 + y1) / 2)
    assert len(sheet.labels) == 4
