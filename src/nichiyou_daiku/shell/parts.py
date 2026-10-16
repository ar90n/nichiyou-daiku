"""Part drawings: one sheet per group of pieces made the same way, an
isometric view with the drilled faces lettered and the reference end
marked, then each drilled face seen from outside with its holes
dimensioned from the reference end.

Needs build123d, so ``nichiyou_daiku.shell`` does not import this module.
"""

import io
import re
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import cairosvg
import numpy as np
from build123d import (
    Align,
    Box,
    Compound,
    Cylinder,
    Edge,
    ExportSVG,
    LineType,
    Polygon,
    Pos,
    Rot,
    Shape,
    Unit,
    scale,
)
from ezdxf.colors import RGB

from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.assembly.parts import (
    PartGroup,
    edge_neighbours,
    face_letters,
    face_point,
    face_size,
    view_direction,
)
from nichiyou_daiku.core.geometry import Face
from nichiyou_daiku.core.placement import face_normal
from nichiyou_daiku.shell.diagnostics import format_mm
from nichiyou_daiku.shell.dimensioning import chain_from_stops
from nichiyou_daiku.shell.drawing import (
    _arrow_points,
    _Dimensions,
    _dimension,
    _levels,
    _line_height,
    _text,
    _text_size,
    _View,
)

# Page mm, as wide as a step image
PAGE_WIDTH = 280.0
MARGIN = 6.0
ISO_WIDTH = 70.0
ISO_HEIGHT = 60.0
LETTER_COLUMN = 16.0  # a face's letter and the letters of its neighbours
MIN_FACE_HEIGHT = 22.0  # a thin face is drawn taller so its values fit
MAX_SCALE = 0.8
FACE_GAP = 10.0
MARK = 3.5  # length of the reference end's triangle

Rect = tuple[float, float, float, float]
_ADVICE = "The report's Pilot Holes table lists the same holes"


@dataclass
class PartSheet:
    """What one part drawing shows, in page mm, and its SVG."""

    group: PartGroup
    letters: dict[Face, str]
    faces: dict[Face, Rect]
    """Each drilled face's outline."""
    texts: list[tuple[str, Rect]]
    """Every word and number drawn, with its box."""
    dimensions: _Dimensions
    svg: str

    def png(self, size: int) -> bytes:
        buffer = io.BytesIO()
        cairosvg.svg2png(
            bytestring=self.svg.encode(),
            write_to=buffer,
            output_width=size,
            background_color="white",
        )
        return buffer.getvalue()


def part_title(assembly: Assembly, group: PartGroup) -> str:
    """Pieces, count, lumber, length and holes per piece, e.g.
    ``shelf_1, shelf_2 ×2   2x4   300   φ8 ↧15 ×2``."""
    lumber = assembly.model.pieces[group.pieces[0]].type.value
    kinds = Counter((hole.diameter, hole.depth) for hole in group.holes)
    holes = [
        f"φ{format_mm(diameter)}"
        + ("" if depth is None else f" ↧{format_mm(depth)}")
        + f" ×{n}"
        # Blind holes first, through holes (no depth) last
        for (diameter, depth), n in sorted(
            kinds.items(),
            key=lambda kind: (kind[0][0], kind[0][1] is None, kind[0][1] or 0),
        )
    ]
    return "   ".join([group.name, lumber, format_mm(group.size[2]), *holes])


def _title_lines(title: str) -> list[str]:
    """The title in lines as wide as the page allows, broken after a comma
    or between its fields."""
    lines = [""]
    for word in re.split(r"(?<=, )|(?<=   )", title):
        wider = (
            _text_size((lines[-1] + word).rstrip(), 0.0)[0] > PAGE_WIDTH - 2 * MARGIN
        )
        if lines[-1] and wider:
            lines.append(word)
        else:
            lines[-1] += word
    return [line.rstrip() for line in lines]


def _solid(group: PartGroup) -> Compound:
    """The piece in its own axes with its holes drilled."""
    extent = np.array(group.size)
    solid: Compound = Box(*extent, align=(Align.MIN, Align.MIN, Align.MIN))
    for hole in group.holes:
        normal = face_normal(hole.face)
        axis = int(np.argmax(np.abs(normal)))
        # A hole without a depth goes through
        depth = hole.depth if hole.depth is not None else float(extent[axis])
        centre = np.array(hole.point) - normal * depth / 2
        turn = {0: Rot(0, 90, 0), 1: Rot(90, 0, 0), 2: Rot(0, 0, 0)}[axis]
        cylinder = Cylinder(
            hole.diameter / 2,
            depth + 0.2,
            align=(Align.CENTER, Align.CENTER, Align.CENTER),
        )
        solid = solid - Pos(*centre) * (turn * cylinder)
    return solid


class _Page:
    """Shapes and texts in page mm, collected for the exporter."""

    def __init__(self) -> None:
        self.lines: list[Shape] = []
        self.hidden: list[Shape] = []
        self.thin: list[Shape] = []
        self.fills: list[Shape] = []
        self.texts: list[tuple[str, Rect]] = []

    def text(self, content: str, x: float, y: float) -> None:
        width, height = _text_size(content, 0.0)
        self.fills.append(Pos(x, y) * _text(content, 0.0))
        self.texts.append(
            (content, (x - width / 2, y - height / 2, x + width / 2, y + height / 2))
        )

    def letter(self, content: str, x: float, y: float, hidden: bool = False) -> None:
        ring = Pos(x, y) * Edge.make_circle(_line_height() * 0.9)
        (self.hidden if hidden else self.thin).append(ring)
        self.text(content, x, y)

    def triangle(self, tip: np.ndarray, direction: np.ndarray) -> None:
        d = direction / np.linalg.norm(direction)
        side = np.array([-d[1], d[0]]) * MARK / 2
        back = tip - d * MARK
        self.fills.append(
            Polygon(tuple(tip), tuple(back + side), tuple(back - side), align=None)
        )


def _isometric(
    group: PartGroup, letters: dict[Face, str], page: _Page, top: float
) -> None:
    """The piece seen diagonally, its lettered faces named in a column at
    its right with leaders, and the reference end marked."""
    extent = np.array(group.size)
    centre = extent / 2
    direction = np.array(view_direction(list(letters)), dtype=float)
    visible, hidden = _solid(group).project_to_viewport(
        tuple(centre + direction * 2000), (0, 0, 1), look_at=tuple(centre)
    )
    box = Compound(children=list(visible) + list(hidden)).bounding_box()
    factor = 0.85 * min(ISO_WIDTH / box.size.X, ISO_HEIGHT / box.size.Y)
    origin = (
        MARGIN + ISO_WIDTH / 2 - box.center().X * factor,
        top - ISO_HEIGHT / 2 - box.center().Y * factor,
    )
    page.lines.append(Pos(*origin) * scale(Compound(children=list(visible)), factor))
    if hidden:
        page.hidden.append(
            Pos(*origin) * scale(Compound(children=list(hidden)), factor)
        )

    # The same projection as project_to_viewport, for points of the piece
    toward = direction / np.linalg.norm(direction)
    up = np.array([0.0, 0.0, 1.0]) - toward[2] * toward
    up /= np.linalg.norm(up)
    right = np.cross(up, toward)

    def on_page(point: np.ndarray) -> np.ndarray:
        q = point - centre
        return np.array([origin[0] + q @ right * factor, origin[1] + q @ up * factor])

    column = MARGIN + ISO_WIDTH + 8
    targets: list[tuple[Face, np.ndarray]] = sorted(
        ((face, on_page(centre + face_normal(face) * extent / 2)) for face in letters),
        key=lambda target: -target[1][1],
    )
    step = _line_height() * 2.6
    first = top - ISO_HEIGHT / 2 + step * (len(targets) - 1) / 2
    for i, (face, point) in enumerate(targets):
        y = first - i * step
        hidden_face = bool(face_normal(face) @ toward <= 0)
        page.letter(letters[face], column, y, hidden_face)
        leader = Edge.make_line((column - _line_height() * 0.9, y), tuple(point))
        (page.hidden if hidden_face else page.thin).append(leader)
    # The reference (down) end: a triangle pointing at it from beyond it
    end = on_page(centre - np.array([0.0, 0.0, extent[2] / 2]))
    beyond = on_page(centre - np.array([0.0, 0.0, extent[2] / 2 + 60 / factor]))
    # Its tip stops short of the end so it does not cover the outline
    toward_end = (end - beyond) / np.linalg.norm(end - beyond)
    page.triangle(end - toward_end * 3.0, toward_end)


def _mark_height(stops: list[float], bottom: float, top: float) -> float:
    """Where the reference end's triangle goes on a face's left edge: the
    middle, unless an extension line is there; then the widest gap."""
    middle = (bottom + top) / 2
    if all(abs(middle - stop) > MARK for stop in stops):
        return middle
    ordered = sorted(stops)
    a, b = max(zip(ordered, ordered[1:]), key=lambda gap: gap[1] - gap[0])
    return (a + b) / 2


def _face_view(
    group: PartGroup,
    face: Face,
    letters: dict[Face, str],
    page: _Page,
    dimensions: _Dimensions,
    bottom: float,
) -> Rect:
    """Draw one drilled face with its lower edge at ``bottom``; return its
    outline."""
    width, height = face_size(face, group.size)
    left = MARGIN + LETTER_COLUMN + _levels("left").depth
    along = min((PAGE_WIDTH - MARGIN - left) / width, MAX_SCALE)
    across = max(along, MIN_FACE_HEIGHT / height)
    rect = (left, bottom, left + width * along, bottom + height * across)
    corners = [
        (rect[0], rect[1]),
        (rect[2], rect[1]),
        (rect[2], rect[3]),
        (rect[0], rect[3]),
    ]
    page.lines += [
        Edge.make_line(a, b) for a, b in zip(corners, corners[1:] + corners[:1])
    ]

    us, vs = [0.0, width], [0.0, height]
    for hole in group.holes:
        if hole.face != face:
            continue
        u, v = face_point(face, hole.point, group.size)
        us.append(u)
        vs.append(v)
        radius = max(1.0, hole.diameter / 2 * min(along, across))
        page.lines.append(
            Pos(left + u * along, bottom + v * across) * Edge.make_circle(radius)
        )
    where = f"face {letters[face]} of {group.pieces[0]}"
    # "from -y" puts a chain's x along the page and its z up the page
    _dimension(
        chain_from_stops("from -y", "x", "below", us),
        _View("from -y", (left, bottom), along, rect, [], []),
        dimensions,
        where,
        _ADVICE,
    )
    _dimension(
        chain_from_stops("from -y", "z", "left", vs),
        _View("from -y", (left, bottom), across, rect, [], []),
        dimensions,
        where,
        _ADVICE,
    )

    column = MARGIN + LETTER_COLUMN / 2
    middle = (rect[1] + rect[3]) / 2
    page.letter(letters[face], column, middle)
    neighbours = edge_neighbours(face)
    for edge, y in (("top", rect[3]), ("bottom", rect[1])):
        if neighbours[edge] in letters:
            page.text(letters[neighbours[edge]], column, y)
    if face in ("top", "down"):
        # An end turns freely about the length, so its sides are named too
        offset = _line_height() * 2
        for edge, x in (("left", column - offset), ("right", column + offset)):
            if neighbours[edge] in letters:
                page.text(letters[neighbours[edge]], x, middle)
    else:
        y = _mark_height([bottom + v * across for v in vs], rect[1], rect[3])
        page.triangle(np.array([left - 0.6, y]), np.array([1.0, 0.0]))
    return rect


def part_sheet(assembly: Assembly, group: PartGroup) -> PartSheet:
    """The drawing of one part: the title, the isometric view and every
    drilled face, top to bottom."""
    letters = face_letters(group.holes, group.size)
    drilled: list[Face] = [
        face for face in letters if any(h.face == face for h in group.holes)
    ]
    page = _Page()
    dimensions = _Dimensions()

    # Faces from the bottom of the page up, the first lettered at the top
    below = _levels("below").depth
    y = MARGIN + below
    faces: dict[Face, Rect] = {}
    for face in reversed(drilled):
        faces[face] = _face_view(group, face, letters, page, dimensions, y)
        y = faces[face][3] + _line_height() + FACE_GAP + below
    top = y - below + ISO_HEIGHT
    _isometric(group, letters, page, top)
    lines = _title_lines(part_title(assembly, group))
    spacing = _line_height() * 1.6
    for i, line in enumerate(reversed(lines)):
        width, _ = _text_size(line, 0.0)
        page.text(line, MARGIN + width / 2, top + 8 + i * spacing)
    height = top + 14 + (len(lines) - 1) * spacing

    exporter = ExportSVG(unit=Unit.MM)
    exporter.add_layer("Piece", line_weight=0.35)
    exporter.add_layer(
        "Hidden",
        line_color=RGB(120, 120, 120),
        line_weight=0.15,
        line_type=LineType.ISO_DASH,
    )
    exporter.add_layer("Thin", line_weight=0.13)
    exporter.add_layer(
        "Text", fill_color=RGB(0, 0, 0), line_color=RGB(0, 0, 0), line_weight=0.01
    )
    border = [(0.0, 0.0), (PAGE_WIDTH, 0.0), (PAGE_WIDTH, height), (0.0, height)]
    page.thin += [Edge.make_line(a, b) for a, b in zip(border, border[1:] + border[:1])]
    page.thin += [Edge.make_line(a, b) for a, b in dimensions.lines]
    for shapes, layer in (
        (page.lines, "Piece"),
        (page.hidden, "Hidden"),
        (page.thin, "Thin"),
    ):
        if shapes:
            exporter.add_shape(shapes, layer=layer)
    labels = [
        Pos(*label.centre) * _text(label.text, label.rotation)
        for label in dimensions.labels
    ]
    arrows = [
        Polygon(*_arrow_points(*arrow), align=None) for arrow in dimensions.arrows
    ]
    exporter.add_shape(page.fills + labels + arrows, layer="Text")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "part.svg"
        exporter.write(str(path))
        svg = path.read_text()
    texts = page.texts + [(label.text, label.box) for label in dimensions.labels]
    return PartSheet(group, letters, faces, texts, dimensions, svg)
