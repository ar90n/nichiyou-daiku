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
from nichiyou_daiku.shell.views import VIEWS, axis_view, project

PAGE_SIZES = ("A4", "A3", "A2", "A1")

# Page mm. Figures, arrows and extension lines follow JIS Z 8317-1.
TEXT_SIZE = 2.5  # height of the figures, which JIS sizes lettering by
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

_VIEW = {
    view.caption: view
    for view in [*(axis_view(a, s) for a in range(3) for s in (1, -1)), *VIEWS]
}
_ISOMETRIC = "from -x +y +z"


@dataclass
class PlacedView:
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
class DrawnDimensions:
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
    views: dict[str, PlacedView]
    dimensions: DrawnDimensions


def _frame(page_size: str) -> tuple[Rect, Rect]:
    """The border's frame and title block, as TechnicalDrawing draws them."""
    width, _ = TechnicalDrawing.page_sizes[PageSize[page_size]]
    frame_width = width - 2 * TechnicalDrawing.margin - 2 * _TITLE_TEXT
    frame_height = 2 * frame_width / 3
    frame = (-frame_width / 2, -frame_height / 2, frame_width / 2, frame_height / 2)
    title_block = (0.0, -frame_height / 2, frame_width / 2, -frame_height / 4)
    return frame, title_block


@lru_cache(maxsize=1)
def _font_size() -> float:
    """Font size whose figures are TEXT_SIZE high; a font size is the em,
    which is taller than the figures."""
    figures = Text("0123456789", font_size=TEXT_SIZE).bounding_box().size.Y
    return TEXT_SIZE * TEXT_SIZE / figures


def text_shape(content: str, rotation: float) -> Shape:
    return Rot(0, 0, rotation) * Text(
        content, font_size=_font_size(), align=(Align.CENTER, Align.CENTER)
    )


@lru_cache(maxsize=None)
def text_size(content: str, rotation: float) -> Point:
    box = text_shape(content, rotation).bounding_box()
    return box.size.X, box.size.Y


@lru_cache(maxsize=1)
def figure_line_height() -> float:
    """Height of a line of figures; the bands leave room for one."""
    return max(text_size(figure, 0.0)[1] for figure in "0123456789.")


class _Levels(NamedTuple):
    """Distances out from a view's edge, in page mm."""

    line: float  # the chain's dimension line
    bend: float  # where leaders stop running straight out
    row: float  # inner edge of the row of values that do not fit
    overall: float  # the overall dimension line
    depth: float  # the farthest thing drawn: the band's depth


def dimension_levels(side: Side) -> _Levels:
    height = figure_line_height()
    # Values sit above their line: toward the view below it, and away from
    # the view beside it (read from the right of the page)
    beyond = OVER if side == "below" else max(OVER, PAD + height + PAD)
    line = FIRST
    bend = line + beyond
    row = bend + SLANT
    # Keep the band depth fixed even when no value needs the outside row, so
    # the layout needs one scale pass (spec: band depth independent of scale)
    overall = row + PAD + height + PAD + OVERALL
    text_beyond = PAD + height if side == "left" else 0.0
    return _Levels(line, bend, row, overall, overall + max(OVER, text_beyond))


def _place(edges: ShapeList, factor: float, offset: Point) -> list[Shape]:
    if not edges:
        return []
    return [Pos(*offset) * scale(Compound(children=list(edges)), factor)]


def _layout(
    part: Compound, frame: Rect, title_block: Rect, bands: bool
) -> tuple[float, dict[str, PlacedView]]:
    """Scale denominator and placed views: the orthographic views at one
    scale left of the title block, the isometric one above it at its own."""
    projections = {}
    for view in VIEWS:
        visible, hidden = part.project_to_viewport(
            view.origin, view.up, look_at=(0, 0, 0)
        )
        box = Compound(children=list(visible) + list(hidden)).bounding_box()
        projections[view.caption] = (visible, hidden, box)
    top, front, side = (projections[c][2] for c in ("from +z", "from +y", "from -x"))
    left_band = dimension_levels("left").depth if bands else 0.0
    bottom_band = dimension_levels("below").depth if bands else 0.0

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
        "from +y": (x0, lower),
        "from -x": (x0 + column * factor + SPACE, lower),
    }
    views = {}
    for caption, (x, y) in corners.items():
        visible, hidden, box = projections[caption]
        offset = (x - box.min.X * factor, y - box.max.Y * factor)
        views[caption] = PlacedView(
            caption,
            offset,
            factor,
            (x, y - box.size.Y * factor, x + box.size.X * factor, y),
            _place(visible, factor, offset),
            _place(hidden, factor, offset),
        )

    visible, hidden, box = projections[_ISOMETRIC]
    space = (
        views["from -x"].box[2] + SPACE,
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
    views[_ISOMETRIC] = PlacedView(
        _ISOMETRIC,
        offset,
        factor,
        (cx - half_width, cy - half_height, cx + half_width, cy + half_height),
        _place(visible, factor, offset),
        _place(hidden, factor, offset),
    )
    return denominator, views


def arrow_points(tip: Point, direction: Point) -> tuple[Point, Point, Point]:
    back = (tip[0] - direction[0] * ARROW, tip[1] - direction[1] * ARROW)
    normal = (-direction[1] * ARROW / 6, direction[0] * ARROW / 6)
    return (
        tip,
        (back[0] + normal[0], back[1] + normal[1]),
        (back[0] - normal[0], back[1] - normal[1]),
    )


def _crowded_advice(page_size: str) -> str:
    """How to make room for crowded values on a ``page_size`` page."""
    leave_out = "leave the dimensions out (drawing --no-dimensions)"
    larger = PAGE_SIZES.index(page_size) + 1
    if larger == len(PAGE_SIZES):
        return leave_out.capitalize()
    return (
        f"Use a larger page (drawing --page-size {PAGE_SIZES[larger]}) or {leave_out}"
    )


def draw_chain(
    chain: Chain, view: PlacedView, out: DrawnDimensions, where: str, advice: str
) -> None:
    """Draw one chain beside its view: extension lines, the chain with its
    values (inside their stretch, else in a row with leaders), the overall.
    Values that do not fit are reported as being in ``where``, with
    ``advice`` on making room."""
    horizontal = chain.side == "below"
    levels = dimension_levels(chain.side)
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
        width, height = text_size(text, rotation)
        return (width, height) if horizontal else (height, width)

    def label(text: str, position: float, depth: float) -> None:
        centre = at(position, depth)
        width, height = text_size(text, rotation)
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
            # A view can run the axis leftward or down; spread wants them in page order
            outside.sort(key=lambda value: value[1])
            centres, fits = spread(
                [middle for _, middle, _, _ in outside],
                [length for _, _, length, _ in outside],
                low + PAD,
                high - PAD,
                2 * PAD,
            )
            if not fits:
                out.crowded.append(
                    f"{len(outside)} dimension values along {chain.axis} in "
                    f"{where} do not fit beside their chain without crossing "
                    f"its lines. {advice}"
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
    length, across = sizes(text)
    if length + 2 * PAD <= high - low:
        position = (low + high) / 2
    else:
        # Too long for the stretch: beyond its low end, on the dimension
        # line extended under it (JIS); the bands leave room there
        position = low - PAD - length / 2
        out.lines.append((at(low, overall), at(low - 2 * PAD - length, overall)))
    label(text, position, overall + up * (PAD + across / 2))


def _compose(part: Compound, assembly: Assembly | None, page_size: str) -> _Sheet:
    """Lay out the page: views, and the assembly's dimensions when given."""
    frame, title_block = _frame(page_size)
    found = chains(assembly) if assembly is not None else []
    denominator, views = _layout(part, frame, title_block, bands=bool(found))
    dimensions = DrawnDimensions()
    for chain in found:
        draw_chain(
            chain,
            views[chain.view],
            dimensions,
            f"the {VIEW_NAMES[chain.view]} view",
            _crowded_advice(page_size),
        )
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
            [Polygon(*arrow_points(*arrow), align=None) for arrow in dimensions.arrows]
            + [
                Pos(*label.centre) * text_shape(label.text, label.rotation)
                for label in dimensions.labels
            ],
            layer="DimensionText",
        )
    return exporter
