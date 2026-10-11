"""Technical drawings: four orthographic views of a model on a titled page.

Needs build123d, so ``nichiyou_daiku.shell`` does not import this module.
"""

from dataclasses import dataclass
from datetime import date

from build123d import (
    Compound,
    ExportSVG,
    LineType,
    PageSize,
    Pos,
    ShapeList,
    TechnicalDrawing,
    Unit,
    scale,
)
from ezdxf.colors import RGB

PAGE_SIZES = ("A4", "A3", "A2", "A1")

VIEW_FILL = 0.7
"""Share of a grid cell taken by the largest view."""

# (viewport origin, viewport up, grid column, grid row). The order is the order
# the edges are written in, kept from the original command.
_VIEWS = (
    ((0, 0, 100), (0, 1, 0), 0, 0),  # top
    ((0, -100, 0), (0, 0, 1), 0, 1),  # front
    ((100, 100, 100), (0, 0, 1), 1, 0),  # isometric
    ((100, 0, 0), (0, 0, 1), 1, 1),  # right side
)


@dataclass
class _View:
    visible: ShapeList
    hidden: ShapeList


def _project(
    part: Compound,
    origin: tuple[float, float, float],
    up: tuple[float, float, float],
    scale_factor: float,
    page_origin: tuple[float, float],
) -> _View:
    scaled = part if scale_factor == 1.0 else scale(part, scale_factor)
    visible, hidden = scaled.project_to_viewport(origin, up, look_at=(0, 0, 0))
    return _View(
        visible=ShapeList([Pos(*page_origin) * e for e in visible]),
        hidden=ShapeList([Pos(*page_origin) * e for e in hidden]),
    )


def _layout_views(part: Compound, width: float, height: float) -> list[_View]:
    """Project the four views and place them on a 2x2 grid at one scale."""
    # Border ~20mm, title block ~40mm high
    area_width = width - 40
    area_height = height - 80
    margin = 10
    cell = min(area_width / 2 - margin, area_height / 2 - margin)
    y_offset = 10

    bounds = []
    for origin, up, _, _ in _VIEWS:
        view = _project(part, origin, up, 1.0, (0, 0))
        bounds.append(Compound(children=view.visible + view.hidden).bounding_box())
    largest = max(max(box.size.X, box.size.Y) for box in bounds)
    view_scale = cell * VIEW_FILL / largest if largest > 0 else 1.0

    views = []
    for (origin, up, column, row), box in zip(_VIEWS, bounds):
        center_x = (area_width if column else -area_width) / 4
        center_y = (-area_height if row else area_height) / 4 + y_offset
        # A view's bounds scale with it, so the unscaled bounds tell where the
        # scaled view lands without projecting it a third time
        x = center_x - box.center().X * view_scale
        y = center_y - box.center().Y * view_scale
        views.append(_project(part, origin, up, view_scale, (x, y)))
    return views


def technical_drawing(
    part: Compound,
    *,
    title: str,
    drawing_number: str,
    designed_by: str,
    page_size: str = "A3",
    design_date: date | None = None,
) -> ExportSVG:
    """Top, front, right-side and isometric views of ``part`` with a titled
    border, on a Visible and a Hidden layer.

    Args:
        part: Model to draw
        title: Drawing title
        drawing_number: Number shown in the title block
        designed_by: Designer shown in the title block
        page_size: One of ``PAGE_SIZES`` (case-insensitive)
        design_date: Date shown in the title block; today when omitted
    """
    if page_size.upper() not in PAGE_SIZES:
        raise ValueError(
            f"page_size must be one of {', '.join(PAGE_SIZES)}, got '{page_size}'"
        )
    border = TechnicalDrawing(
        designed_by=designed_by,
        design_date=design_date or date.today(),
        page_size=PageSize[page_size.upper()],
        title=title,
        sub_title="Units: mm",
        drawing_number=drawing_number,
        sheet_number=1,
        drawing_scale=1,
    )
    size = border.bounding_box().size
    views = _layout_views(part, size.X, size.Y)

    exporter = ExportSVG(unit=Unit.MM)
    exporter.add_layer("Visible")
    exporter.add_layer("Hidden", line_color=RGB(99, 99, 99), line_type=LineType.ISO_DOT)
    exporter.add_shape([e for view in views for e in view.visible], layer="Visible")
    exporter.add_shape([e for view in views for e in view.hidden], layer="Hidden")
    exporter.add_shape(border, layer="Visible")
    return exporter
