"""The check image: four views of a model on one square sheet, with piece
labels, for an agent or a person to look at.

Needs build123d, so ``nichiyou_daiku.shell`` does not import this module.
"""

import io
import tempfile
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import cairosvg
from build123d import Compound, ExportSVG, Pos, Unit, scale

from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.placement import overall_bounds
from nichiyou_daiku.shell.diagnostics import format_mm
from nichiyou_daiku.shell.views import VIEWS, visible_labels

SVG_NAMESPACE = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NAMESPACE)

VIEW_FILL = 0.9
"""Share of a cell's drawing area taken by the largest view."""

_MARGIN = 0.04
"""Margin and caption band, as a share of the sheet size."""


@dataclass(frozen=True)
class PlacedLabel:
    """A piece ID on the sheet, in px with y up from the bottom."""

    caption: str
    piece_id: str
    x: float
    y: float


@dataclass(frozen=True)
class Sheet:
    """The SVG of the check image and what was placed on it."""

    svg: str
    size: int
    labels: tuple[PlacedLabel, ...]
    view_boxes: dict[str, tuple[float, float, float, float]]
    unlabelled: tuple[str, ...]
    note: tuple[str, ...]

    def png(self) -> bytes:
        buffer = io.BytesIO()
        cairosvg.svg2png(
            bytestring=self.svg.encode(),
            write_to=buffer,
            output_width=self.size,
            output_height=self.size,
            background_color="white",
        )
        return buffer.getvalue()


class _Text(NamedTuple):
    x: float
    y: float
    text: str
    size: float
    color: str
    anchor: str


def _overlaps(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _note(
    assembly: Assembly, title: str, unlabelled: list[str], width: int
) -> list[str]:
    """The note's lines: the title and size, then the unlabelled pieces
    wrapped to ``width`` characters."""
    if len(assembly.placement.groups) == 1:
        low, high = overall_bounds(assembly.model, assembly.placement)
        sizes = " x ".join(
            format_mm(value)
            for value in (high.x - low.x, high.y - low.y, high.z - low.z)
        )
        head = f"{title}  {sizes} mm (x × y × z)"
    else:
        head = f"{title}  pieces not connected"
    if not unlabelled:
        return [head]
    return [head, *textwrap.wrap("not labelled: " + ", ".join(unlabelled), width)]


def _svg(exporter: ExportSVG, texts: list[_Text], size: int) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "sheet.svg"
        exporter.write(str(path))
        root = ET.fromstring(path.read_text())
    groups = list(root)
    if len(groups) != 1 or groups[0].get("transform") != "scale(1,-1)":
        raise RuntimeError(
            "Unexpected SVG from build123d: expected one group flipped with "
            "scale(1,-1), so the labels would not line up with the lines"
        )
    # The exporter fits its view box to the lines; the sheet is the whole
    # square. Lines are drawn in a y-up group, so y is negated here and below.
    root.set("width", str(size))
    root.set("height", str(size))
    root.set("viewBox", f"0 {-size} {size} {size}")
    for text in texts:
        # A white outline underneath keeps the text readable across lines
        outline = {"stroke": "white", "stroke-width": f"{text.size / 5:.2f}"}
        for extra in (outline | {"fill": "white"}, {}):
            element = ET.SubElement(
                root,
                f"{{{SVG_NAMESPACE}}}text",
                {
                    "x": f"{text.x:.2f}",
                    "y": f"{-text.y:.2f}",
                    "font-family": "sans-serif",
                    "font-size": f"{text.size:.2f}",
                    "text-anchor": text.anchor,
                    "dominant-baseline": "middle",
                    "fill": text.color,
                    **extra,
                },
            )
            element.text = text.text
    return ET.tostring(root, encoding="unicode")


def render_sheet(
    part: Compound, assembly: Assembly, *, title: str, size: int = 1400
) -> Sheet:
    """Draw the visible lines of ``part`` from the four ``VIEWS`` on a square
    sheet ``size`` px wide, at one scale, with captions, piece labels and a
    note naming ``title`` and the overall size."""
    margin = size * _MARGIN
    caption_height = size * _MARGIN
    cell = (size - 2 * margin) / 2
    # Floors keep small images readable
    label_size = max(10.0, size / 80)
    caption_size = max(12.0, size / 50)
    note_size = max(10.0, size / 60)

    projected = []
    for view in VIEWS:
        visible, _ = part.project_to_viewport(view.origin, view.up, look_at=(0, 0, 0))
        lines = Compound(children=list(visible))
        projected.append((view, lines, lines.bounding_box()))
    largest = max(max(box.size.X, box.size.Y) for _, _, box in projected)
    view_scale = (cell - caption_height) * VIEW_FILL / largest if largest > 0 else 1.0

    exporter = ExportSVG(unit=Unit.MM)
    exporter.add_layer("Visible", line_weight=max(1.0, size / 1000))
    texts: list[_Text] = []
    labels: list[PlacedLabel] = []
    view_boxes: dict[str, tuple[float, float, float, float]] = {}
    for view, lines, box in projected:
        center_x = margin + view.column * cell + cell / 2
        cell_top = size - margin - view.row * cell
        center_y = cell_top - caption_height - (cell - caption_height) / 2
        dx = center_x - box.center().X * view_scale
        dy = center_y - box.center().Y * view_scale
        exporter.add_shape(Pos(dx, dy) * scale(lines, view_scale), layer="Visible")
        view_boxes[view.caption] = (
            dx + box.min.X * view_scale,
            dy + box.min.Y * view_scale,
            dx + box.max.X * view_scale,
            dy + box.max.Y * view_scale,
        )
        texts.append(
            _Text(
                center_x,
                cell_top - caption_height / 2,
                view.caption,
                caption_size,
                "black",
                "middle",
            )
        )
        taken: list[tuple[float, float, float, float]] = []
        for label in visible_labels(assembly, view):
            x = dx + label.x * view_scale
            y = dy + label.y * view_scale
            half = len(label.piece_id) * label_size * 0.3
            area = (x - half, y - label_size / 2, x + half, y + label_size / 2)
            if any(_overlaps(area, other) for other in taken):
                continue
            taken.append(area)
            labels.append(PlacedLabel(view.caption, label.piece_id, x, y))
            texts.append(_Text(x, y, label.piece_id, label_size, "#b00000", "middle"))

    labelled = {label.piece_id for label in labels}
    unlabelled = [
        piece_id for piece_id in assembly.model.pieces if piece_id not in labelled
    ]
    # About 0.55 em per character in a sans-serif font
    note = _note(
        assembly, title, unlabelled, int((size - 2 * margin) / (note_size * 0.55))
    )
    for index, line in enumerate(reversed(note)):
        # The last line sits in the bottom margin; earlier lines stack above
        y = margin / 2 + index * note_size * 1.3
        texts.append(_Text(margin, y, line, note_size, "black", "start"))
    return Sheet(
        svg=_svg(exporter, texts, size),
        size=size,
        labels=tuple(labels),
        view_boxes=view_boxes,
        unlabelled=tuple(unlabelled),
        note=tuple(note),
    )
