"""Tests for the part drawings."""

from functools import lru_cache
from itertools import combinations
from pathlib import Path

import pytest

pytest.importorskip("build123d")

from nichiyou_daiku.core.assembly import Assembly  # noqa: E402
from nichiyou_daiku.core.assembly.parts import (  # noqa: E402
    LocalHole,
    PartGroup,
    part_groups,
)
from nichiyou_daiku.dsl import parse_dsl  # noqa: E402
from nichiyou_daiku.shell.drawing import arrow_points, text_size  # noqa: E402
from nichiyou_daiku.shell.parts import (  # noqa: E402
    PAGE_WIDTH,
    part_sheet,
    part_title,
)

ROOT = Path(__file__).parents[2]
EXAMPLES = sorted(
    [
        *(ROOT / "examples" / "nd_files").glob("*.nd"),
        *(ROOT / "skills" / "design" / "examples").glob("*.nd"),
    ]
)
SHELF = ROOT / "skills" / "design" / "examples" / "two-tier-shelf.nd"
# The screwed shelf of patterns.md with its bottom shelf on dowels instead:
# a post then has through holes and blind holes of two sizes on one face
MIXED = """(side_l:2x4 =800)
(side_r:2x4 =800)
(shelf_bottom:2x4 =600)
(shelf_top:2x4 =600)
side_l -[BL<100 DL<0 D(:8x30)]- shelf_bottom
side_r -[FL<100 TL<0 D(:8x30)]- shelf_bottom
shelf_top -[DL<0 BL>38 S(Slim:3.8x65)]- side_l
shelf_top -[TL<0 FL>38 S(Slim:3.8x65)]- side_r
"""
# Slats with long names dowelled along a rail: one part whose names are
# wider than the page
SLATS = "(rail:2x4 =1200)\n" + "".join(
    f"(slat_with_a_long_name_{i:02d}:2x2 =300)\n"
    f"rail -[RF<{i * 90:g} BT<0 D(:8x30)]- slat_with_a_long_name_{i:02d}\n"
    for i in range(12)
)

# A post with a piece dowelled to each of its six faces
SIX = """(c:2x4 =300)
(up:2x4 =200)
(dn:2x4 =200)
(f:2x4 =200)
(b:2x4 =200)
(l:2x4 =200)
(r:2x4 =200)
c -[TF<0 DF<0 D(:8x30)]- up
c -[DF<0 TF<0 D(:8x30)]- dn
c -[FL<100 DF<0 D(:8x30)]- f
c -[BL<100 DB<0 D(:8x30)]- b
c -[LF<100 DF<0 D(:8x30)]- l
c -[RF<100 DF<0 D(:8x30)]- r
"""


@lru_cache(maxsize=None)
def _sheets(source: str):
    # Drawing takes about a second a part, so each design is drawn once
    assembly = Assembly.of(parse_dsl(source))
    return assembly, [
        part_sheet(assembly, group) for group in part_groups(assembly) if group.holes
    ]


@pytest.fixture(scope="module")
def shelf():
    return _sheets(SHELF.read_text())


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _crosses(rect, segment, margin: float = 1e-6) -> bool:
    """Whether a segment passes through the inside of a rectangle."""
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


def _problems(sheet) -> list:
    """Texts on each other or off the page, values on dimension lines,
    crowded values."""
    boxes = [box for _, box in sheet.texts]
    segments = list(sheet.dimensions.lines)
    for arrow in sheet.dimensions.arrows:
        a, b, c = arrow_points(*arrow)
        segments += [(a, b), (b, c), (c, a)]
    values = [label.box for label in sheet.dimensions.labels]
    return (
        [(a, b) for a, b in combinations(boxes, 2) if _overlap(a, b)]
        + [box for box in boxes if box[0] < 0 or box[2] > PAGE_WIDTH]
        + [(v, s) for v in values for s in segments if _crosses(v, s)]
        + sheet.dimensions.crowded
    )


def test_title_names_the_pieces_lumber_length_and_holes_per_piece(shelf):
    assembly, _ = shelf
    groups = {group.pieces[0]: group for group in part_groups(assembly)}
    assert part_title(assembly, groups["leg_1"]) == "leg_1   2x4   781   φ8 ↧15 ×10"
    assert part_title(assembly, groups["shelf_1"]) == (
        "shelf_1, shelf_2, shelf_3, shelf_4 ×4   2x4   300   φ8 ↧15 ×2"
    )


def test_through_holes_are_written_without_a_depth():
    assembly = Assembly.of(parse_dsl(MIXED))
    post = next(g for g in part_groups(assembly) if g.pieces[0] == "side_l")
    # Blind dowel holes and the screws' through holes on one face
    assert part_title(assembly, post) == (
        "side_l, side_r ×2   2x4   800   φ2.5 ×2   φ8 ↧15 ×2"
    )


def test_a_title_wider_than_the_page_is_wrapped():
    _, sheets = _sheets(SLATS)
    slats = next(sheet for sheet in sheets if len(sheet.group.pieces) == 12)
    assert _problems(slats) == []
    written = " ".join(text for text, _ in slats.texts)
    assert all(name in written for name in slats.group.pieces)


def test_every_face_drilled_is_lettered_without_clashes():
    _, sheets = _sheets(SIX)
    post = sheets[0]
    assert post.letters == {
        "front": "A",
        "back": "B",
        "left": "C",
        "right": "D",
        "top": "E",
        "down": "F",
    }
    assert _problems(post) == []


def test_values_that_do_not_fit_point_to_the_pilot_holes_table():
    # Holes 12.5mm apart along 2m leave no room for their values
    holes = tuple(
        LocalHole("front", (44.5, 38.0, 10 + 12.5 * i), 8.0, 15.0) for i in range(150)
    )
    group = PartGroup(pieces=("rail",), size=(89.0, 38.0, 2000.0), holes=holes)
    sheet = part_sheet(Assembly.of(parse_dsl("(rail:2x4 =2000)")), group)
    assert len(sheet.dimensions.crowded) == 1
    assert "face A of rail" in sheet.dimensions.crowded[0]
    assert "Pilot Holes table" in sheet.dimensions.crowded[0]


def test_one_sheet_per_drilled_part(shelf):
    _, sheets = shelf
    assert [sheet.group.pieces[0] for sheet in sheets] == [
        "leg_1",
        "leg_2",
        "leg_3",
        "leg_4",
        "apron_upper_front",
        "apron_upper_back",
        "apron_upper_left",
        "apron_lower_front",
        "top_1",
        "shelf_1",
    ]


def test_leg_holes_are_dimensioned_from_the_reference_end(shelf):
    _, sheets = shelf
    texts = [label.text for label in sheets[0].dimensions.labels]
    for value in ("172.2", "44.5", "497.5", "22.2", "781", "19", "70", "89"):
        assert value in texts
    assert sheets[0].letters == {"back": "A", "left": "B", "top": "C"}


def test_thin_faces_are_drawn_tall_enough_for_their_values(shelf):
    _, sheets = shelf
    # leg_1's narrow face (38) is drawn 22 high; its wide face (89) fits
    # at the scale along the length, which both share
    narrow, wide = sheets[0].faces["left"], sheets[0].faces["back"]
    assert narrow[3] - narrow[1] == pytest.approx(22.0)
    scale = (wide[2] - wide[0]) / 781
    assert wide[3] - wide[1] == pytest.approx(89 * scale)
    assert narrow[2] - narrow[0] == pytest.approx(wide[2] - wide[0])


def test_neighbours_name_the_faces_beside_each_face(shelf):
    _, sheets = shelf
    # Each letter is in the isometric and beside its own face. A is also at
    # B's and C's bottom edges; B at A's top edge and beside C's left edge
    words = [text for text, _ in sheets[0].texts]
    assert words.count("A") == 4
    assert words.count("B") == 4
    assert words.count("C") == 2


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_part_drawings_are_clean(path):
    _, sheets = _sheets(path.read_text())
    for sheet in sheets:
        assert _problems(sheet) == [], sheet.group.pieces[0]


def test_mixed_holes_draw_cleanly():
    _, sheets = _sheets(MIXED)
    assert sheets
    for sheet in sheets:
        assert _problems(sheet) == [], sheet.group.pieces[0]


def test_the_depth_symbol_is_drawn():
    # A font without it would draw nothing
    assert text_size("↧", 0.0)[0] > 0


def test_png_is_written(shelf):
    _, sheets = shelf
    assert sheets[-1].png(400).startswith(b"\x89PNG")
