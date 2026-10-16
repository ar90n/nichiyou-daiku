# Drawing Dimensions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The `drawing` command's technical drawing carries the overall size and chain dimensions of where the pieces go (JIS style), draws the orthographic views as large as the page allows, and writes the real scale in the title block.

**Architecture:** A new build123d-free module `shell/dimensioning.py` decides the dimension chains (stops per view and axis, which stretches are lumber sizes) from the `Assembly`, and lays out crowded values in one dimension (`spread`). `shell/drawing.py` gets a new page layout (orthographic block left of the title block at one exact scale, isometric above the title block), draws the chains (extension lines, filled arrows, values, leaders, overall) and warns with `CrowdedDimensionsWarning` when values cannot be placed. `technical_drawing` takes the `assembly` to dimension; the CLI passes it unless `--no-dimensions`.

**Tech Stack:** Python 3.13, build123d (`TechnicalDrawing`, `ExportSVG`, `Text`, `project_to_viewport`), click, pytest. Run everything with `uv run` from the repository root on branch `feat/drawing-dimensions`.

**Spec:** `docs/superpowers/specs/2026-10-16-drawing-dimensions-design.md` (Japanese; binding). Every value and rule below comes from it.

## Global Constraints

- Code, comments, docstrings, docs and messages in English. Comments are few and say why. Warning messages say what is wrong and how to fix it.
- `shell/dimensioning.py` does not import build123d. `shell/__init__.py` does not import `shell/drawing.py`.
- JIS Z 8317-1: figures 2.5mm; filled arrows 2mm; extension lines start 1mm off the outline and run 2mm past their dimension line; values sit 0.6mm above their line; vertical values are rotated 90° counter-clockwise (read from the right of the page), so they sit left of their line.
- Chain dimension line 8mm from the view; overall dimension 4mm beyond the row of values that do not fit; 12mm between views; drawing 4mm inside the frame.
- Scale: the largest that fits, the denominator rounded up to 0.1 and never below 1 (no enlargement); the title block shows `1:` + the denominator (`1:6`, `1:6.3`).
- Values: `format_mm` (0.1mm). A stretch equal to a piece's width or thickness is written only where it fits; every other stretch is always written, in the outside row with a leader when it does not fit. Stops closer than 0.05mm merge.
- Line weights: outlines 0.3mm, dimension lines 0.13mm, hidden lines unchanged.
- No dimensions (and no bands) when the assembly is not given or its pieces are not all connected.
- Run `make check` before every commit and commit only if it passes: `make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log; [ $rc -eq 0 ] && git commit ...`.
- Never commit dotfiles or `CLAUDE.md`.

## Review Focus

1. **Fonts in the CI container.** Text sizes come from the font build123d finds; the overlap tests measure real text. A different font in Dagger's container could make a value overlap. `make ci-local` must pass before merging.
2. **The CLI's default 5mm fillets.** Most tests draw with `fillet_radius=0`; the drawn size and a clean layout must hold with fillets. Pinned by `test_fillets_do_not_change_the_drawn_size` (Task 2).
3. **A4 and A1 pages.** The bands are a fixed depth, so they take a bigger share of A4. Pinned by `test_smallest_and_largest_pages_are_clean` (Task 2).
4. **Wide furniture,** where the width sets the scale. Pinned by `test_wide_model_is_clean` (Task 2).
5. **Other warnings while drawing.** The CLI records warnings to print the crowded ones; it must not swallow the rest. Pinned by `test_drawing_warns_about_crowded_dimensions` (Task 3).

Known and accepted (the approved prototype looks this way): in a stretch shorter than two arrows (a 13.2mm gap at 1:6 is 2.2mm), the two arrows overlap each other.

---

### Task 1: Dimension chains (`shell/dimensioning.py`)

**Files:**
- Create: `src/nichiyou_daiku/shell/dimensioning.py`
- Test: `tests/shell/test_dimensioning.py`

**Interfaces:**
- Consumes: `Assembly` (`assembly.model.pieces: dict[str, Piece]`, `assembly.placement.poses[id].bounds(piece) -> (Point3D, Point3D)`, `assembly.placement.poses[id].rotation` (3x3 ints), `assembly.placement.groups`), `get_shape(piece).width/.height`, `format_mm`.
- Produces:
  - `PRECISION_MM = 0.05`
  - `Axis = Literal["x", "y", "z"]`, `Side = Literal["left", "below"]`
  - `VIEW_NAMES: dict[str, str]` — `{"from +z": "top", "from -y": "front", "from +x": "right side"}`
  - `class CrowdedDimensionsWarning(UserWarning)`
  - `class Segment(NamedTuple)`: `start: float`, `end: float`, `lumber: bool`; property `text -> str`
  - `class Chain(NamedTuple)`: `view: str` (caption in `views.VIEWS`), `axis: Axis`, `side: Side`, `stops: tuple[float, ...]` (ascending, both model ends included), `segments: tuple[Segment, ...]` (empty when only the overall size is drawn); property `overall -> Segment`
  - `chains(assembly: Assembly) -> list[Chain]` — in this order: `("from -y", "z", "left")`, `("from -y", "x", "below")`, `("from +x", "y", "below")`, `("from +z", "x", "below")`, `("from +z", "y", "left")`; `[]` when not exactly one placement group
  - `spread(wanted: Sequence[float], sizes: Sequence[float], low: float, high: float, gap: float) -> tuple[list[float], bool]`
  - private `_stops(ends: Iterable[float], low: float, high: float) -> tuple[float, ...]` (tested directly)

- [ ] **Step 1: Write the failing tests**

Create `tests/shell/test_dimensioning.py`:

```python
"""Tests for which dimensions the technical drawing writes."""

from pathlib import Path

import pytest

from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.shell.dimensioning import Chain, _stops, chains, spread

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
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/shell/test_dimensioning.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'nichiyou_daiku.shell.dimensioning'`

- [ ] **Step 3: Write the module**

Create `src/nichiyou_daiku/shell/dimensioning.py`:

```python
"""Which dimensions the technical drawing writes, and where crowded values go.

Free of build123d, like ``views``: the drawing measures and draws the text.
A chain runs along one world axis of one view, from stop to stop; the stops
are both ends of the chosen pieces and of the whole model.
"""

from typing import Iterable, Literal, NamedTuple, Sequence

from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.geometry import Point3D
from nichiyou_daiku.core.piece import Piece, get_shape
from nichiyou_daiku.shell.diagnostics import format_mm

PRECISION_MM = 0.05
"""Stops closer than this print as the same value, so they are merged."""

# Placement rounds positions to 1e-6mm, so the top layer is found exactly
_TOP_TOLERANCE_MM = 1e-6

Axis = Literal["x", "y", "z"]
Side = Literal["left", "below"]

VIEW_NAMES = {"from +z": "top", "from -y": "front", "from +x": "right side"}
"""Names of the dimensioned views, by their caption in ``views.VIEWS``."""


class CrowdedDimensionsWarning(UserWarning):
    """Dimension values that overlap: they do not fit beside their chain."""


class Segment(NamedTuple):
    """A stretch between neighbouring stops, in world mm along the axis.

    ``lumber`` marks the width or thickness of a piece that fills the
    stretch: readers know it from the lumber size, so the drawing writes it
    only where it fits.
    """

    start: float
    end: float
    lumber: bool

    @property
    def text(self) -> str:
        return format_mm(self.end - self.start)


class Chain(NamedTuple):
    """Chain dimensions along one world axis of one view.

    ``segments`` is empty when there is nothing between the model's ends;
    then only the overall size is drawn.
    """

    view: str
    axis: Axis
    side: Side
    stops: tuple[float, ...]
    segments: tuple[Segment, ...]

    @property
    def overall(self) -> Segment:
        return Segment(self.stops[0], self.stops[-1], lumber=False)


def _stops(ends: Iterable[float], low: float, high: float) -> tuple[float, ...]:
    """``low``, ``high`` and the ends between them, merged within PRECISION_MM."""
    stops = [low]
    for value in sorted(
        e for e in ends if low + PRECISION_MM <= e <= high - PRECISION_MM
    ):
        if value - stops[-1] >= PRECISION_MM:
            stops.append(value)
    stops.append(high)
    return tuple(stops)


def _is_lumber(
    start: float,
    end: float,
    extents: Sequence[tuple[float, float, Piece]],
) -> bool:
    for low, high, piece in extents:
        shape = get_shape(piece)
        if (
            abs(low - start) < PRECISION_MM
            and abs(high - end) < PRECISION_MM
            and min(abs(end - start - shape.width), abs(end - start - shape.height))
            < PRECISION_MM
        ):
            return True
    return False


def _chain(
    view: str,
    axis: Axis,
    side: Side,
    bounds: dict[str, tuple[Point3D, Point3D]],
    pieces: dict[str, Piece],
    chosen: Sequence[str],
) -> Chain:
    low = min(getattr(box[0], axis) for box in bounds.values())
    high = max(getattr(box[1], axis) for box in bounds.values())
    extents = [
        (getattr(bounds[i][0], axis), getattr(bounds[i][1], axis), pieces[i])
        for i in chosen
    ]
    stops = _stops((end for e in extents for end in e[:2]), low, high)
    segments = (
        tuple(
            Segment(a, b, _is_lumber(a, b, extents)) for a, b in zip(stops, stops[1:])
        )
        if len(stops) > 2
        else ()
    )
    return Chain(view, axis, side, stops, segments)


def chains(assembly: Assembly) -> list[Chain]:
    """The drawing's dimension chains; none when the pieces are not all
    connected, since then the overall size means nothing.

    Heights in the front view stop at every piece. Widths in the front view
    and depths in the side view stop at the upright pieces (length along z),
    the top view's at the top layer (pieces whose top is the model's top).
    """
    if len(assembly.placement.groups) != 1:
        return []
    pieces = dict(assembly.model.pieces)
    bounds = {
        piece_id: assembly.placement.poses[piece_id].bounds(piece)
        for piece_id, piece in pieces.items()
    }
    upright = [
        piece_id
        for piece_id in pieces
        if abs(assembly.placement.poses[piece_id].rotation[2][2]) == 1
    ]
    top = max(box[1].z for box in bounds.values())
    top_layer = [
        piece_id
        for piece_id, box in bounds.items()
        if box[1].z >= top - _TOP_TOLERANCE_MM
    ]
    return [
        _chain("from -y", "z", "left", bounds, pieces, list(pieces)),
        _chain("from -y", "x", "below", bounds, pieces, upright),
        _chain("from +x", "y", "below", bounds, pieces, upright),
        _chain("from +z", "x", "below", bounds, pieces, top_layer),
        _chain("from +z", "y", "left", bounds, pieces, top_layer),
    ]


def _span(
    labels: Sequence[int],
    wanted: Sequence[float],
    sizes: Sequence[float],
    low: float,
    high: float,
    gap: float,
) -> tuple[float, float]:
    total = sum(sizes[i] for i in labels) + gap * (len(labels) - 1)
    start = sum(wanted[i] for i in labels) / len(labels) - total / 2
    start = max(low, min(start, high - total))
    return start, start + total


def spread(
    wanted: Sequence[float],
    sizes: Sequence[float],
    low: float,
    high: float,
    gap: float,
) -> tuple[list[float], bool]:
    """Centres for labels along a line, and whether they all fit.

    Labels keep the order of ``wanted`` (ascending) and stay ``gap`` apart;
    each run of labels that would touch is centred on where its labels want
    to be, then moved inside ``low``..``high``. A run longer than that range
    starts at ``low`` and does not fit.

    Examples:
        >>> spread([0.0, 1.0], [2.0, 2.0], -10.0, 10.0, 1.0)
        ([-1.0, 2.0], True)
        >>> spread([0.0], [4.0], 0.0, 10.0, 1.0)
        ([2.0], True)
    """
    runs = [[i] for i in range(len(wanted))]
    while True:
        spans = [_span(run, wanted, sizes, low, high, gap) for run in runs]
        touching = next(
            (k for k in range(len(runs) - 1) if spans[k + 1][0] < spans[k][1] + gap),
            None,
        )
        if touching is None:
            break
        runs[touching : touching + 2] = [runs[touching] + runs[touching + 1]]

    centres = [0.0] * len(wanted)
    fits = True
    for run, (start, end) in zip(runs, spans):
        fits = fits and start >= low - 1e-9 and end <= high + 1e-9
        cursor = start
        for i in run:
            centres[i] = cursor + sizes[i] / 2
            cursor += sizes[i] + gap
    return centres, fits
```

- [ ] **Step 4: Run the tests and the doctests**

Run: `uv run pytest tests/shell/test_dimensioning.py src/nichiyou_daiku/shell/dimensioning.py --doctest-modules -q`
Expected: `14 passed`

- [ ] **Step 5: Check that the top-layer test can fail**

Temporarily change the top view's x chain in `chains` to use every piece:
`_chain("from +z", "x", "below", bounds, pieces, list(pieces))`.
Run: `uv run pytest tests/shell/test_dimensioning.py -q`
Expected: `1 failed` (`test_top_view_stops_at_the_top_boards_and_their_gaps`: the lower shelf boards add stops). Restore `top_layer` and rerun: `13 passed`.

- [ ] **Step 6: Commit**

```bash
make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log
[ $rc -eq 0 ] && git add src/nichiyou_daiku/shell/dimensioning.py tests/shell/test_dimensioning.py && git commit -m "feat: Find the dimension chains of a technical drawing

Stops at both ends of the chosen pieces per view and axis, stretches
that are a lumber width or thickness marked, and a 1D layout for the
values that do not fit."
```

---

### Task 2: Page layout, scale and dimensions (`shell/drawing.py`)

**Files:**
- Modify (replace): `src/nichiyou_daiku/shell/drawing.py`
- Test (replace): `tests/shell/test_drawing.py`

**Interfaces:**
- Consumes: Task 1's `Chain`, `Side`, `chains`, `spread`, `VIEW_NAMES`, `CrowdedDimensionsWarning`; `views.VIEWS`, `views.project(view, point) -> (x, y)`.
- Produces:
  - `technical_drawing(part, *, title, drawing_number, designed_by, page_size="A3", design_date=None, assembly: Assembly | None = None) -> ExportSVG` — dimensions when `assembly` is given; warns `CrowdedDimensionsWarning` once per crowded chain, with the message saying what to do
  - `PAGE_SIZES`, layout constants `TEXT_SIZE, ARROW, GAP, OVER, PAD, FIRST, SLANT, OVERALL, SPACE, INSET, ISO_FILL`
  - private, used by the tests: `_frame(page_size: str) -> (frame: Rect, title_block: Rect)`; `_compose(part, assembly | None, page_size: str) -> _Sheet` with `frame`, `title_block`, `denominator: float`, `views: dict[caption, _View]` (`_View.box: Rect`, `offset`, `scale`, `visible`, `hidden`), `dimensions: _Dimensions` (`lines: list[(Point, Point)]`, `arrows: list[(tip, unit direction)]`, `labels: list[_Label]` with `text, centre, rotation, box, view, side`, `crowded: list[str]`); `_arrow_points(tip, direction) -> 3 points`
  - SVG layers: `Visible` (0.3mm), `Hidden` (grey dots), `Dimensions` (0.13mm), `DimensionText` (filled arrows and figures)
- The old `_layout_views`, `_project` and `VIEW_FILL` are removed; nothing outside `drawing.py` and its tests uses them (check with `grep -rn "_layout_views\|VIEW_FILL" src tests`).

- [ ] **Step 1: Write the failing tests**

Replace `tests/shell/test_drawing.py` with:

```python
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


def test_no_dimensions_without_an_assembly(part):
    sheet = _compose(part, None, "A3")
    assert sheet.dimensions.lines == []
    assert sheet.dimensions.labels == []


def test_crowded_values_warn_and_say_what_to_do():
    part, assembly = _model(CROWDED)
    with pytest.warns(CrowdedDimensionsWarning, match="front view") as caught:
        technical_drawing(
            part, title="t", drawing_number="1", designed_by="me", assembly=assembly
        )
    message = str(caught[0].message)
    assert "--page-size A2" in message
    assert "--no-dimensions" in message
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/shell/test_drawing.py -q`
Expected: collection error, `ImportError: cannot import name 'FIRST' from 'nichiyou_daiku.shell.drawing'`

- [ ] **Step 3: Write the module**

Replace `src/nichiyou_daiku/shell/drawing.py` with:

```python
"""Technical drawings: four views of a model on a titled page, with the
overall size and where the pieces go dimensioned in the orthographic views.

Needs build123d, so ``nichiyou_daiku.shell`` does not import this module.
"""

import math
import warnings
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from typing import NamedTuple

from build123d import (
    Align,
    Compound,
    Edge,
    ExportSVG,
    LineType,
    PageSize,
    Polygon,
    Pos,
    Rot,
    Shape,
    ShapeList,
    TechnicalDrawing,
    Text,
    Unit,
    scale,
)
from ezdxf.colors import RGB

from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.shell.dimensioning import (
    VIEW_NAMES,
    Chain,
    CrowdedDimensionsWarning,
    Side,
    chains,
    spread,
)
from nichiyou_daiku.shell.views import VIEWS, project

PAGE_SIZES = ("A4", "A3", "A2", "A1")

# Page mm. Figures, arrows and extension lines follow JIS Z 8317-1.
TEXT_SIZE = 2.5
ARROW = 2.0
GAP = 1.0  # outline to the start of an extension line
OVER = 2.0  # extension line beyond its dimension line
PAD = 0.6  # text to the lines around it
FIRST = 8.0  # view to the chain's dimension line
SLANT = 2.5  # depth a leader slants across to reach its value
OVERALL = 4.0  # outside row to the overall dimension line
SPACE = 12.0  # between views
INSET = 4.0  # frame to the drawing
ISO_FILL = 0.9  # share of its space the isometric view takes
_TITLE_TEXT = 10.0  # TechnicalDrawing's nominal text size, which sets its frame

Point = tuple[float, float]
Rect = tuple[float, float, float, float]
"""min x, min y, max x, max y on the page."""

_VIEW = {view.caption: view for view in VIEWS}
_ISOMETRIC = "from +x +y +z"


@dataclass
class _View:
    """A view's projected lines, placed on the page."""

    caption: str
    offset: Point
    scale: float
    box: Rect
    visible: list[Shape]
    hidden: list[Shape]


class _Label(NamedTuple):
    text: str
    centre: Point
    rotation: float
    box: Rect
    view: str
    side: Side


@dataclass
class _Dimensions:
    lines: list[tuple[Point, Point]] = field(default_factory=list)
    arrows: list[tuple[Point, Point]] = field(default_factory=list)
    """Tip and the unit direction it points in."""
    labels: list[_Label] = field(default_factory=list)
    crowded: list[str] = field(default_factory=list)
    """What to tell the user about values that do not fit."""


@dataclass
class _Sheet:
    frame: Rect
    title_block: Rect
    denominator: float
    views: dict[str, _View]
    dimensions: _Dimensions


def _frame(page_size: str) -> tuple[Rect, Rect]:
    """The border's frame and title block, as TechnicalDrawing draws them."""
    width, _ = TechnicalDrawing.page_sizes[PageSize[page_size]]
    frame_width = width - 2 * TechnicalDrawing.margin - 2 * _TITLE_TEXT
    frame_height = 2 * frame_width / 3
    frame = (-frame_width / 2, -frame_height / 2, frame_width / 2, frame_height / 2)
    title_block = (0.0, -frame_height / 2, frame_width / 2, -frame_height / 4)
    return frame, title_block


def _text(content: str, rotation: float) -> Shape:
    return Rot(0, 0, rotation) * Text(
        content, font_size=TEXT_SIZE, align=(Align.CENTER, Align.CENTER)
    )


@lru_cache(maxsize=None)
def _text_size(content: str, rotation: float) -> Point:
    box = _text(content, rotation).bounding_box()
    return box.size.X, box.size.Y


@lru_cache(maxsize=1)
def _line_height() -> float:
    """Height of a line of figures; the bands leave room for one."""
    return max(_text_size(figure, 0.0)[1] for figure in "0123456789.")


class _Levels(NamedTuple):
    """Distances out from a view's edge, in page mm."""

    line: float  # the chain's dimension line
    bend: float  # where leaders stop running straight out
    row: float  # inner edge of the row of values that do not fit
    overall: float  # the overall dimension line
    depth: float  # the farthest thing drawn: the band's depth


def _levels(side: Side) -> _Levels:
    height = _line_height()
    # Values sit above their line: toward the view below it, and away from
    # the view beside it (read from the right of the page)
    beyond = OVER if side == "below" else max(OVER, PAD + height + PAD)
    line = FIRST
    bend = line + beyond
    row = bend + SLANT
    overall = row + PAD + height + PAD + OVERALL
    text_beyond = PAD + height if side == "left" else 0.0
    return _Levels(line, bend, row, overall, overall + max(OVER, text_beyond))


def _place(edges: ShapeList, factor: float, offset: Point) -> list[Shape]:
    if not edges:
        return []
    return [Pos(*offset) * scale(Compound(children=list(edges)), factor)]


def _layout(
    part: Compound, frame: Rect, title_block: Rect, bands: bool
) -> tuple[float, dict[str, _View]]:
    """Scale denominator and placed views: the orthographic views at one
    scale left of the title block, the isometric one above it at its own."""
    projections = {}
    for view in VIEWS:
        visible, hidden = part.project_to_viewport(
            view.origin, view.up, look_at=(0, 0, 0)
        )
        box = Compound(children=list(visible) + list(hidden)).bounding_box()
        projections[view.caption] = (visible, hidden, box)
    top, front, side = (projections[c][2] for c in ("from +z", "from -y", "from +x"))
    left_band = _levels("left").depth if bands else 0.0
    bottom_band = _levels("below").depth if bands else 0.0

    left, bottom, top_edge = frame[0] + INSET, frame[1] + INSET, frame[3] - INSET
    right = title_block[0] - INSET
    column = max(top.size.X, front.size.X)
    row = max(front.size.Y, side.size.Y)
    largest = min(
        (right - left - left_band - SPACE) / (column + side.size.X),
        (top_edge - bottom - 2 * bottom_band - SPACE) / (top.size.Y + row),
    )
    # Round the denominator up so the scale written is the scale drawn
    denominator = max(1.0, math.ceil(10 / largest - 1e-9) / 10)
    factor = 1 / denominator

    x0 = left + left_band
    lower = top_edge - top.size.Y * factor - bottom_band - SPACE
    corners = {
        "from +z": (x0, top_edge),
        "from -y": (x0, lower),
        "from +x": (x0 + column * factor + SPACE, lower),
    }
    views = {}
    for caption, (x, y) in corners.items():
        visible, hidden, box = projections[caption]
        offset = (x - box.min.X * factor, y - box.max.Y * factor)
        views[caption] = _View(
            caption,
            offset,
            factor,
            (x, y - box.size.Y * factor, x + box.size.X * factor, y),
            _place(visible, factor, offset),
            _place(hidden, factor, offset),
        )

    visible, hidden, box = projections[_ISOMETRIC]
    space = (
        views["from +x"].box[2] + SPACE,
        title_block[3] + INSET,
        frame[2] - INSET,
        top_edge,
    )
    factor = ISO_FILL * min(
        (space[2] - space[0]) / box.size.X, (space[3] - space[1]) / box.size.Y
    )
    cx, cy = (space[0] + space[2]) / 2, (space[1] + space[3]) / 2
    offset = (cx - box.center().X * factor, cy - box.center().Y * factor)
    half_width, half_height = box.size.X * factor / 2, box.size.Y * factor / 2
    views[_ISOMETRIC] = _View(
        _ISOMETRIC,
        offset,
        factor,
        (cx - half_width, cy - half_height, cx + half_width, cy + half_height),
        _place(visible, factor, offset),
        _place(hidden, factor, offset),
    )
    return denominator, views


def _arrow_points(tip: Point, direction: Point) -> tuple[Point, Point, Point]:
    back = (tip[0] - direction[0] * ARROW, tip[1] - direction[1] * ARROW)
    normal = (-direction[1] * ARROW / 6, direction[0] * ARROW / 6)
    return (
        tip,
        (back[0] + normal[0], back[1] + normal[1]),
        (back[0] - normal[0], back[1] - normal[1]),
    )


def _dimension(chain: Chain, view: _View, out: _Dimensions) -> None:
    """Draw one chain beside its view: extension lines, the chain with its
    values (inside their stretch, else in a row with leaders), the overall."""
    horizontal = chain.side == "below"
    levels = _levels(chain.side)
    edge = view.box[1] if horizontal else view.box[0]
    rotation = 0.0 if horizontal else 90.0
    # Depth of a value's top: toward the view below, away from it beside
    up = -1.0 if horizontal else 1.0
    axis = "xyz".index(chain.axis)

    def along(value: float) -> float:
        point = [0.0, 0.0, 0.0]
        point[axis] = value
        x, y = project(_VIEW[chain.view], point)
        if horizontal:
            return view.offset[0] + x * view.scale
        return view.offset[1] + y * view.scale

    def at(position: float, depth: float) -> Point:
        # Dimensions go below or left: page y or x decreases with depth
        return (position, edge - depth) if horizontal else (edge - depth, position)

    def sizes(text: str) -> Point:
        """Size along the dimension line and across it."""
        width, height = _text_size(text, rotation)
        return (width, height) if horizontal else (height, width)

    def label(text: str, position: float, depth: float) -> None:
        centre = at(position, depth)
        width, height = _text_size(text, rotation)
        box = (
            centre[0] - width / 2,
            centre[1] - height / 2,
            centre[0] + width / 2,
            centre[1] + height / 2,
        )
        out.labels.append(_Label(text, centre, rotation, box, chain.view, chain.side))

    def dimension_line(low: float, high: float, depth: float) -> None:
        out.lines.append((at(low, depth), at(high, depth)))
        backward = (-1.0, 0.0) if horizontal else (0.0, -1.0)
        forward = (1.0, 0.0) if horizontal else (0.0, 1.0)
        out.arrows.append((at(low, depth), backward))
        out.arrows.append((at(high, depth), forward))

    low, high = sorted((along(chain.stops[0]), along(chain.stops[-1])))
    if chain.segments:
        for stop in chain.stops:
            out.lines.append(
                (at(along(stop), GAP), at(along(stop), levels.line + OVER))
            )
        outside = []
        for segment in chain.segments:
            a, b = sorted((along(segment.start), along(segment.end)))
            dimension_line(a, b, levels.line)
            length, across = sizes(segment.text)
            if length + 2 * PAD <= b - a:
                label(segment.text, (a + b) / 2, levels.line + up * (PAD + across / 2))
            elif not segment.lumber:
                outside.append((segment.text, (a + b) / 2, length, across))
        if outside:
            centres, fits = spread(
                [middle for _, middle, _, _ in outside],
                [length for _, _, length, _ in outside],
                low + PAD,
                high - PAD,
                2 * PAD,
            )
            if not fits:
                out.crowded.append(
                    f"{len(outside)} dimension values along {chain.axis} in the "
                    f"{VIEW_NAMES[chain.view]} view do not fit beside their chain "
                    "and overlap. Use a larger page (drawing --page-size A2) or "
                    "leave the dimensions out (drawing --no-dimensions)"
                )
            for (text, middle, _, across), centre in zip(outside, centres):
                out.lines.append((at(middle, levels.line), at(middle, levels.bend)))
                out.lines.append((at(middle, levels.bend), at(centre, levels.row)))
                label(text, centre, levels.row + PAD + across / 2)
        overall, start = levels.overall, levels.line + OVER
    else:
        overall, start = levels.line, GAP
    for end in (low, high):
        out.lines.append((at(end, start), at(end, overall + OVER)))
    dimension_line(low, high, overall)
    text = chain.overall.text
    label(text, (low + high) / 2, overall + up * (PAD + sizes(text)[1] / 2))


def _compose(part: Compound, assembly: Assembly | None, page_size: str) -> _Sheet:
    """Lay out the page: views, and the assembly's dimensions when given."""
    frame, title_block = _frame(page_size)
    found = chains(assembly) if assembly is not None else []
    denominator, views = _layout(part, frame, title_block, bands=bool(found))
    dimensions = _Dimensions()
    for chain in found:
        _dimension(chain, views[chain.view], dimensions)
    return _Sheet(frame, title_block, denominator, views, dimensions)


def technical_drawing(
    part: Compound,
    *,
    title: str,
    drawing_number: str,
    designed_by: str,
    page_size: str = "A3",
    design_date: date | None = None,
    assembly: Assembly | None = None,
) -> ExportSVG:
    """Top, front, right-side and isometric views of ``part`` with a titled
    border, on Visible, Hidden and dimension layers.

    The orthographic views share the largest scale that fits (1:1 at most,
    the denominator in 0.1 steps, written in the title block). With
    ``assembly`` (the one ``part`` was built from) they carry the overall
    size and chain dimensions of where the pieces go; values that cannot be
    placed without overlapping raise ``CrowdedDimensionsWarning``.

    Args:
        part: Model to draw
        title: Drawing title
        drawing_number: Number shown in the title block
        designed_by: Designer shown in the title block
        page_size: One of ``PAGE_SIZES`` (case-insensitive)
        design_date: Date shown in the title block; today when omitted
        assembly: Assembly to dimension; no dimensions when omitted or when
            its pieces are not all connected
    """
    if page_size.upper() not in PAGE_SIZES:
        raise ValueError(
            f"page_size must be one of {', '.join(PAGE_SIZES)}, got '{page_size}'"
        )
    sheet = _compose(part, assembly, page_size.upper())
    for message in sheet.dimensions.crowded:
        warnings.warn(CrowdedDimensionsWarning(message), stacklevel=2)
    denominator = sheet.denominator
    border = TechnicalDrawing(
        designed_by=designed_by,
        design_date=design_date or date.today(),
        page_size=PageSize[page_size.upper()],
        title=title,
        sub_title="Units: mm",
        drawing_number=drawing_number,
        sheet_number=1,
        # Shown as "1:" + str(value), so 6 rather than 6.0
        drawing_scale=int(denominator) if denominator.is_integer() else denominator,
        nominal_text_size=_TITLE_TEXT,
    )

    dimensions = sheet.dimensions
    exporter = ExportSVG(unit=Unit.MM)
    # JIS: thick outlines, thin dimension lines
    exporter.add_layer("Visible", line_weight=0.3)
    exporter.add_layer("Hidden", line_color=RGB(99, 99, 99), line_type=LineType.ISO_DOT)
    exporter.add_layer("Dimensions", line_weight=0.13)
    exporter.add_layer(
        "DimensionText",
        fill_color=RGB(0, 0, 0),
        line_color=RGB(0, 0, 0),
        line_weight=0.01,
    )
    views = sheet.views.values()
    exporter.add_shape([c for v in views for c in v.visible], layer="Visible")
    exporter.add_shape([c for v in views for c in v.hidden], layer="Hidden")
    exporter.add_shape(border, layer="Visible")
    if dimensions.lines:
        exporter.add_shape(
            [Edge.make_line(a, b) for a, b in dimensions.lines], layer="Dimensions"
        )
        exporter.add_shape(
            [Polygon(*_arrow_points(*arrow), align=None) for arrow in dimensions.arrows]
            + [
                Pos(*label.centre) * _text(label.text, label.rotation)
                for label in dimensions.labels
            ],
            layer="DimensionText",
        )
    return exporter
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/shell/test_drawing.py -q`
Expected: `81 passed` (about 15s: every example file is drawn once)

- [ ] **Step 5: Check that the JIS test can fail**

Temporarily set `up = -1.0` in `_dimension` (vertical values toward the view, as in prototype v10).
Run: `uv run pytest tests/shell/test_drawing.py -q -k vertical`
Expected: `1 failed`. Restore `up = -1.0 if horizontal else 1.0` and rerun: `1 passed`.

- [ ] **Step 6: Look at a drawing**

```bash
uv run python - <<'EOF'
from datetime import date
from pathlib import Path
import cairosvg
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.shell.build123d_export import assembly_to_build123d
from nichiyou_daiku.shell.drawing import technical_drawing
a = Assembly.of(parse_dsl(Path("skills/design/examples/two-tier-shelf.nd").read_text()))
technical_drawing(assembly_to_build123d(a), title="two-tier-shelf", drawing_number="ND-1",
                  designed_by="nichiyou-daiku", design_date=date(2026, 10, 16), assembly=a).write("/tmp/shelf.svg")
cairosvg.svg2png(url="/tmp/shelf.svg", write_to="/tmp/shelf.png", output_width=2400, background_color="white")
EOF
```

Read `/tmp/shelf.png`. Expected: scale `1:6`; heights 150 / 89 / 38 / 415 / 89 and 800 left of the front view with the figures left of their lines; 89 / 422 / 89 and 600 below it; 38 / 224 / 38 and 300 below the side view; the top view's 89s with five 13.2s on leaders below, 600, and 300 on its left; the isometric view above the title block.

- [ ] **Step 7: Commit**

```bash
make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log
[ $rc -eq 0 ] && git add src/nichiyou_daiku/shell/drawing.py tests/shell/test_drawing.py && git commit -m "feat: Dimension the technical drawing and draw it at a real scale

The orthographic views fill the page left of the title block at the
largest scale with a 0.1 denominator, which the title block now shows.
With the assembly they carry the overall size and chain dimensions of
where the pieces go, drawn as JIS Z 8317-1 does; values that cannot be
placed raise CrowdedDimensionsWarning."
```

---

### Task 3: CLI `--no-dimensions` and the crowded warning

**Files:**
- Modify: `src/nichiyou_daiku/cli/commands/drawing.py`
- Test: `tests/cli/commands/test_drawing.py`

**Interfaces:**
- Consumes: Task 2's `technical_drawing(..., assembly=...)`; Task 1's `CrowdedDimensionsWarning` (importable without build123d).
- Produces: `nichiyou-daiku drawing FILE [--no-dimensions]`; crowded warnings printed as `Warning: <message>` in yellow on stderr, exit code 0.

- [ ] **Step 1: Write the failing tests**

Append to `tests/cli/commands/test_drawing.py`:

```python
def _record_drawing_options(monkeypatch, *warn: Warning) -> dict:
    """Replace technical_drawing with one that records its options and
    raises the warnings ``warn``."""
    import warnings

    import nichiyou_daiku.shell.drawing as drawing_module

    real = drawing_module.technical_drawing
    options: dict = {}

    def recording(part, **kwargs):
        options.update(kwargs)
        for warning in warn:
            warnings.warn(warning)
        return real(part, **kwargs)

    monkeypatch.setattr(drawing_module, "technical_drawing", recording)
    return options


def test_drawing_has_dimensions_unless_asked_not_to(
    runner, tmp_path, beam_file, monkeypatch
):
    pytest.importorskip("build123d")
    options = _record_drawing_options(monkeypatch)
    output_file = tmp_path / "out.svg"

    result = runner.invoke(cli, ["drawing", str(beam_file), "-o", str(output_file)])
    assert result.exit_code == 0, result.output
    assert options["assembly"] is not None

    result = runner.invoke(
        cli, ["drawing", str(beam_file), "-o", str(output_file), "--no-dimensions"]
    )
    assert result.exit_code == 0, result.output
    assert options["assembly"] is None


def test_drawing_warns_about_crowded_dimensions(
    runner, tmp_path, beam_file, monkeypatch
):
    pytest.importorskip("build123d")
    from nichiyou_daiku.shell.dimensioning import CrowdedDimensionsWarning

    _record_drawing_options(
        monkeypatch,
        CrowdedDimensionsWarning("5 dimension values overlap"),
        UserWarning("a library has something to say"),
    )
    output_file = tmp_path / "out.svg"

    # Other warnings are passed on, not swallowed
    with pytest.warns(UserWarning, match="a library has something to say"):
        result = runner.invoke(cli, ["drawing", str(beam_file), "-o", str(output_file)])

    assert result.exit_code == 0, result.output
    assert "Warning: 5 dimension values overlap" in result.stderr
    assert output_file.exists()
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/cli/commands/test_drawing.py -q`
Expected: `2 failed, 11 passed` (`KeyError: 'assembly'`; no `Warning: 5 dimension values overlap` in stderr)

- [ ] **Step 3: Implement**

In `src/nichiyou_daiku/cli/commands/drawing.py`:

Add `import warnings` after `import tempfile`, and after the `nichiyou_daiku.cli.utils` import block:

```python
from nichiyou_daiku.shell.dimensioning import CrowdedDimensionsWarning
```

Add the option after `--page-size` (before `@click.pass_context`):

```python
@click.option(
    "--no-dimensions",
    is_flag=True,
    help="Leave out the dimensions (overall size and where the pieces go)",
)
```

Add `no_dimensions: bool,` after `page_size: str,` in the function's parameters. In the docstring, add `    - Dimensions: overall size and where the pieces go` after `    - Isometric view`, and `        nichiyou-daiku drawing shelf.nd --no-dimensions` after the `--page-size A2` example.

Replace the `try: exporter = technical_drawing(...) except ...` block with:

```python
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", CrowdedDimensionsWarning)
            exporter = technical_drawing(
                compound,
                title=title or source_stem,
                drawing_number=drawing_number,
                designed_by=designed_by,
                page_size=page_size,
                assembly=None if no_dimensions else assembly,
            )
    except Exception as e:
        echo.exception(f"Error creating drawing: {e}")
        sys.exit(1)
    for warning in caught:
        if issubclass(warning.category, CrowdedDimensionsWarning):
            echo.info(click.style(f"Warning: {warning.message}", fg="yellow"))
        else:
            # Recording catches every warning; pass the others on
            warnings.warn_explicit(
                warning.message, warning.category, warning.filename, warning.lineno
            )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/cli/commands/test_drawing.py -q`
Expected: `13 passed`

- [ ] **Step 5: Try it**

Run: `uv run nichiyou-daiku drawing skills/design/examples/two-tier-shelf.nd -o /tmp/shelf.pdf && uv run nichiyou-daiku drawing skills/design/examples/two-tier-shelf.nd --no-dimensions -o /tmp/shelf-plain.svg`
Expected: both succeed with no warning; `/tmp/shelf-plain.svg` has no `id="Dimensions"` layer (`grep -c 'id="Dimensions"' /tmp/shelf-plain.svg` prints 0).

- [ ] **Step 6: Commit**

```bash
make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log
[ $rc -eq 0 ] && git add src/nichiyou_daiku/cli/commands/drawing.py tests/cli/commands/test_drawing.py && git commit -m "feat: Dimension drawings from the CLI unless --no-dimensions

Crowded dimension values are reported as warnings; other warnings
raised while drawing are passed on."
```

---

### Task 4: Documentation and a look at every example

**Files:**
- Modify: `docs/dsl-specification.md` (Technical Drawing section)
- Modify: `docs/api-specification.md` (new Technical Drawing section after 3D Export)
- Modify: `README.md` (the `drawing` line of the quick start)
- Local only, not committed: `CLAUDE.md`

**Interfaces:**
- Consumes: the CLI option and API from Tasks 2 and 3.
- Produces: docs checked by `tests/test_docs.py` (the API spec's Python imports are executed; build123d is installed in `make check` and CI).

- [ ] **Step 1: DSL specification**

In `docs/dsl-specification.md`, replace the Technical Drawing section's body (from its ```` ```bash ```` block through the paragraph ending "fill in the title block.") with:

````markdown
```bash
nichiyou-daiku drawing furniture.nd -o furniture.pdf
nichiyou-daiku drawing furniture.nd -o furniture.svg --page-size A4 --title "Side Table"
nichiyou-daiku drawing furniture.nd --no-dimensions
```

Draws the top, front, right-side and isometric views on one page (A4 to A1, default A3); an output ending in `.svg` is written as SVG instead of PDF. `--drawing-number` and `--designed-by` fill in the title block.

The top, front and right-side views are in third-angle projection at one scale: the largest that fits left of the title block, never above 1:1, with the denominator rounded up to 0.1 and written in the title block (e.g. 1:6.3). The isometric view fills the space above the title block at its own scale. The orthographic views carry dimensions in mm, drawn as JIS Z 8317-1 does (filled arrows, 2.5mm figures, vertical values read from the right):

- **Overall size**: width, depth and height, outermost.
- **Where the pieces go**: chain dimensions inside the overall ones, from stop to stop. The front view's heights stop at both ends of every piece; its widths and the side view's depths stop at the upright pieces (length along z); the top view stops at the top layer (the pieces whose top is the model's top).
- **Values**: a stretch that is a piece's width or thickness (89, 38, 19, ...) is written only where its value fits, since the lumber size gives it; every other stretch, such as a gap, is always written, beside the chain with a leader when it does not fit. If those values still do not fit, the drawing warns and suggests a larger `--page-size` or `--no-dimensions`.

Piece lengths are not dimensioned (the cut list in `report` has them), nor are the positions of lying pieces below the top layer. Unconnected pieces get no dimensions, and `--no-dimensions` leaves them out to draw the views larger.
````

- [ ] **Step 2: API specification**

In `docs/api-specification.md`, after the 3D Export example block (it ends with `>>> # Use with ocp-vscode or export to STL/STEP` and a closing fence), insert:

````markdown
### Technical Drawing (Optional)

Requires `build123d` package.

```python
from nichiyou_daiku.shell.drawing import technical_drawing

def technical_drawing(
    part: "Compound",
    *,
    title: str,
    drawing_number: str,
    designed_by: str,
    page_size: str = "A3",
    design_date: date | None = None,
    assembly: Assembly | None = None,
) -> "ExportSVG":
    """Top, front, right-side and isometric views on a titled page (A4-A1)."""
```

Pass the `assembly` that `part` was built from to dimension the drawing (overall size and where the pieces go; see `drawing` in the [DSL Specification](./dsl-specification.md)). Values that cannot be placed without overlapping raise `nichiyou_daiku.shell.dimensioning.CrowdedDimensionsWarning`. `exporter.write("drawing.svg")` writes the page as SVG.
````

- [ ] **Step 3: README**

In `README.md`, change the comment on the `nichiyou-daiku drawing corner.nd` line to `# technical drawing PDF with dimensions (needs the viz extra)` (keep the column alignment).

- [ ] **Step 4: Run the doc tests**

Run: `uv run pytest tests/test_docs.py -q`
Expected: `48 passed`

- [ ] **Step 5: Look at every example**

```bash
mkdir -p /tmp/ndk-drawings
for f in examples/nd_files/*.nd skills/design/examples/*.nd; do
  n=$(basename "$f" .nd)
  uv run nichiyou-daiku drawing "$f" -o "/tmp/ndk-drawings/$n.svg" 2>&1 | grep -i warn
  uv run python -c "import cairosvg; cairosvg.svg2png(url='/tmp/ndk-drawings/$n.svg', write_to='/tmp/ndk-drawings/$n.png', output_width=2400, background_color='white')"
done
ls /tmp/ndk-drawings/*.png
```

Expected: no warnings printed; nine PNGs. Read each PNG: no value touches a line or another value, every view and dimension is inside the frame and off the title block, vertical values read from the right and sit left of their lines.

- [ ] **Step 6: CLAUDE.md (local, not committed)**

In `CLAUDE.md`'s 構成と責務 `shell/` bullet, after `drawing.py`（図面。build123d 必須なので `shell/__init__` から import しない）, add: `、dimensioning.py`（図面の寸法の区切りと配置。build123d に依存しない）.

- [ ] **Step 7: Commit**

```bash
make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log
[ $rc -eq 0 ] && git add docs/dsl-specification.md docs/api-specification.md README.md && git commit -m "docs: Describe the drawing's dimensions and scale"
```
