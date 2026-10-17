"""Assembly instructions: a Markdown page and one image per step, each an
isometric view (earlier pieces grey, this step's black) beside a view
dimensioning where this step's pieces go.

Needs build123d, so ``nichiyou_daiku.shell`` does not import this module.
"""

import io
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import cairosvg
from build123d import (
    Compound,
    Edge,
    ExportSVG,
    LineType,
    Polygon,
    Pos,
    Shape,
    Unit,
    scale,
)
from build123d.topology import downcast
from ezdxf.colors import RGB

# OCP's classes live in a compiled module that pyright cannot read
from OCP.BRepLib import BRepLib  # pyright: ignore[reportAttributeAccessIssue]
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt  # pyright: ignore[reportAttributeAccessIssue]
from OCP.HLRAlgo import HLRAlgo_Projector  # pyright: ignore[reportAttributeAccessIssue]
from OCP.HLRBRep import HLRBRep_Algo  # pyright: ignore[reportAttributeAccessIssue]
from OCP.HLRBRep import HLRBRep_HLRToShape  # pyright: ignore[reportAttributeAccessIssue]
from OCP.TopAbs import TopAbs_ShapeEnum  # pyright: ignore[reportAttributeAccessIssue]
from OCP.TopExp import TopExp_Explorer  # pyright: ignore[reportAttributeAccessIssue]
from OCP.TopoDS import TopoDS_Shape  # pyright: ignore[reportAttributeAccessIssue]

from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.assembly.parts import PartGroup, part_groups
from nichiyou_daiku.core.assembly.steps import PlannedStep, StepPlan, plan_steps
from nichiyou_daiku.shell.diagnostics import format_mm
from nichiyou_daiku.shell.dimensioning import Axis, chain_for
from nichiyou_daiku.shell.drawing import (
    arrow_points,
    DrawnDimensions,
    draw_chain,
    dimension_levels,
    text_shape,
    text_size,
    PlacedView,
)
from nichiyou_daiku.shell.parts import part_sheet
from nichiyou_daiku.shell.resources import count_hardware
from nichiyou_daiku.shell.views import VIEWS, View, axis_view, label_at, project

# Page mm of a step image: an isometric half and a dimensioned half. Small
# enough that 2.5mm figures stay readable at the default 1600px.
PAGE_WIDTH = 280.0
PAGE_HEIGHT = 140.0
MARGIN = 6.0
HEADING = 10.0  # band at the top for the step's heading
ISO_FILL = 0.9

_ISOMETRIC = next(view for view in VIEWS if view.caption == "from -x +y +z")
_KIND_MARKS = {"sub-assembly": " (sub-assembly)", "join": " (join)"}
_SPLIT_ADVICE = "Split the step into steps that add fewer pieces"
_ONE_PIECE_ADVICE = "The report's Anchor Details give where each connection is"
_IMAGE = re.compile(r"(step|part)-\d+\.png")

Rect = tuple[float, float, float, float]


@dataclass
class _PieceLines:
    visible: list[Shape] = field(default_factory=list)
    hidden: list[Shape] = field(default_factory=list)


@dataclass
class StepImage:
    """What one step's image shows, in page mm, and its SVG."""

    step: PlannedStep
    lines: dict[str, _PieceLines]
    """Isometric lines of each piece shown."""
    dimension_lines: dict[str, _PieceLines]
    """The dimension view's lines of each piece shown."""
    labels: dict[str, Rect]
    """Boxes of the labels naming this step's pieces."""
    view: View
    """The view dimensioning this step."""
    dimensions: DrawnDimensions
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


def _edges(shape: TopoDS_Shape) -> list[Shape]:
    if shape.IsNull():
        return []
    edges: list[Shape] = []
    explorer = TopExp_Explorer(shape, TopAbs_ShapeEnum.TopAbs_EDGE)
    while explorer.More():
        edge = downcast(explorer.Current())
        # The projected edges have no 3D curves until they are built
        BRepLib.BuildCurves3d_s(edge, 1e-5)
        edges.append(Edge(edge))
        explorer.Next()
    return edges


def _piece_lines(
    shapes: dict[str, Compound], pieces: tuple[str, ...], view: View
) -> dict[str, _PieceLines]:
    """Each piece's visible and hidden lines from ``view``, with every piece
    in ``pieces`` hiding the others. build123d's projection treats a part as
    one shape, so this runs OCCT's hidden-line removal with one shape per
    piece and reads the lines back per piece."""
    algorithm = HLRBRep_Algo()
    for piece_id in pieces:
        algorithm.Add(shapes[piece_id].wrapped)
    toward_viewer = gp_Dir(*view.origin)
    axes = gp_Ax2(gp_Pnt(*view.origin), toward_viewer)
    axes.SetYDirection(gp_Dir(*view.up))
    algorithm.Projector(HLRAlgo_Projector(axes))
    algorithm.Update()
    algorithm.Hide()
    to_shape = HLRBRep_HLRToShape(algorithm)
    lines = {}
    for piece_id in pieces:
        shape = shapes[piece_id].wrapped
        lines[piece_id] = _PieceLines(
            visible=_edges(to_shape.VCompound(shape))
            + _edges(to_shape.OutLineVCompound(shape))
            + _edges(to_shape.Rg1LineVCompound(shape)),
            hidden=_edges(to_shape.HCompound(shape))
            + _edges(to_shape.OutLineHCompound(shape))
            + _edges(to_shape.Rg1LineHCompound(shape)),
        )
    return lines


def _bounds(lines: dict[str, _PieceLines]) -> Rect:
    box = Compound(
        children=[e for piece in lines.values() for e in piece.visible + piece.hidden]
    ).bounding_box()
    return box.min.X, box.min.Y, box.max.X, box.max.Y


def _fit(bounds: Rect, area: Rect, fill: float) -> tuple[float, tuple[float, float]]:
    """Scale and offset that centre ``bounds`` in ``area``, ``fill`` of it."""
    width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
    factor = fill * min((area[2] - area[0]) / width, (area[3] - area[1]) / height)
    centre = ((area[0] + area[2]) / 2, (area[1] + area[3]) / 2)
    return factor, (
        centre[0] - (bounds[0] + bounds[2]) / 2 * factor,
        centre[1] - (bounds[1] + bounds[3]) / 2 * factor,
    )


def _placed(
    lines: dict[str, _PieceLines], factor: float, offset: tuple[float, float]
) -> dict[str, _PieceLines]:
    def place(edges: list[Shape]) -> list[Shape]:
        # One compound per piece: moving edges one by one copies each of them
        if not edges:
            return []
        return [Pos(*offset) * scale(Compound(children=edges), factor)]

    return {
        piece_id: _PieceLines(place(piece.visible), place(piece.hidden))
        for piece_id, piece in lines.items()
    }


def _advice(step: PlannedStep) -> str:
    """What to do when a step's values do not fit: a step of one piece
    cannot be split, so the report has to give its places."""
    return _SPLIT_ADVICE if len(step.pieces) > 1 else _ONE_PIECE_ADVICE


def _heading(step: PlannedStep) -> str:
    name = f" - {step.name}" if step.name else ""
    return f"Step {step.number}{name}{_KIND_MARKS.get(step.kind, '')}"


def _dimension_view(
    assembly: Assembly, step: PlannedStep, lines: dict[str, _PieceLines], area: Rect
) -> tuple[View, PlacedView, DrawnDimensions]:
    """The step's view placed in ``area`` with its chains drawn: the shown
    pieces as the extent, stops at this step's pieces and their partners."""
    view = axis_view(*step.view)
    left, below = dimension_levels("left").depth, dimension_levels("below").depth
    inner = (area[0] + left, area[1] + below, area[2], area[3])
    bounds = _bounds(lines)
    factor = min(
        (inner[2] - inner[0]) / (bounds[2] - bounds[0]),
        (inner[3] - inner[1]) / (bounds[3] - bounds[1]),
    )
    offset = (inner[0] - bounds[0] * factor, inner[3] - bounds[3] * factor)
    box = (
        inner[0],
        inner[3] - (bounds[3] - bounds[1]) * factor,
        inner[0] + (bounds[2] - bounds[0]) * factor,
        inner[3],
    )
    placed = PlacedView(view.caption, offset, factor, box, [], [])

    model, poses = assembly.model, assembly.placement.poses
    partners = {
        piece_id
        for key in step.connections
        for piece_id in key
        if piece_id not in step.pieces
    }
    chosen = [*step.pieces, *sorted(partners)]
    world = {p: poses[p].bounds(model.pieces[p]) for p in step.shown}
    dimensions = DrawnDimensions()
    names: tuple[Axis, Axis, Axis] = ("x", "y", "z")
    for axis in (a for a in range(3) if a != step.view[0]):
        unit = [0.0, 0.0, 0.0]
        unit[axis] = 1.0
        x, y = project(view, unit)
        side = "below" if abs(x) > abs(y) else "left"
        chain = chain_for(
            view.caption, names[axis], side, world, dict(model.pieces), chosen
        )
        draw_chain(chain, placed, dimensions, f"step {step.number}", _advice(step))
    return view, placed, dimensions


def step_image(assembly: Assembly, part: Compound, step: PlannedStep) -> StepImage:
    """The step's image: the isometric view on the left, the dimension view
    on the right, the heading at the top."""
    shapes = {child.label: child for child in part.children}
    iso_area = (MARGIN, MARGIN, PAGE_WIDTH / 2 - MARGIN, PAGE_HEIGHT - HEADING)
    iso_lines = _piece_lines(shapes, step.shown, _ISOMETRIC)
    factor, offset = _fit(_bounds(iso_lines), iso_area, ISO_FILL)
    iso = _placed(iso_lines, factor, offset)
    labels: dict[str, Rect] = {}
    for piece_id in step.pieces:
        label = label_at(assembly, _ISOMETRIC, piece_id, step.shown)
        if label is None:
            continue
        x, y = offset[0] + label.x * factor, offset[1] + label.y * factor
        width, height = text_size(label.piece_id, 0.0)
        box = (x - width / 2, y - height / 2, x + width / 2, y + height / 2)
        # A label that would cover another is left out; the table names it
        if all(
            box[2] <= b[0] or b[2] <= box[0] or box[3] <= b[1] or b[3] <= box[1]
            for b in labels.values()
        ):
            labels[label.piece_id] = box

    dim_area = (
        PAGE_WIDTH / 2 + MARGIN,
        MARGIN,
        PAGE_WIDTH - MARGIN,
        PAGE_HEIGHT - HEADING,
    )
    view = axis_view(*step.view)
    dim_lines = _piece_lines(shapes, step.shown, view)
    view, placed, dimensions = _dimension_view(assembly, step, dim_lines, dim_area)
    dims = _placed(dim_lines, placed.scale, placed.offset)

    exporter = ExportSVG(unit=Unit.MM)
    exporter.add_layer("Before", line_color=RGB(160, 160, 160), line_weight=0.18)
    exporter.add_layer("New", line_weight=0.5)
    exporter.add_layer("NewHidden", line_weight=0.25, line_type=LineType.ISO_DASH)
    exporter.add_layer("Dimensions", line_weight=0.13)
    # A white ground under each piece name keeps it readable over the lines
    exporter.add_layer(
        "LabelGround",
        fill_color=RGB(255, 255, 255),
        line_color=RGB(255, 255, 255),
        line_weight=0.01,
    )
    exporter.add_layer(
        "Text", fill_color=RGB(0, 0, 0), line_color=RGB(0, 0, 0), line_weight=0.01
    )
    # A light border keeps every step's image the same size
    corners = [(0, 0), (PAGE_WIDTH, 0), (PAGE_WIDTH, PAGE_HEIGHT), (0, PAGE_HEIGHT)]
    exporter.add_shape(
        [Edge.make_line(a, b) for a, b in zip(corners, corners[1:] + corners[:1])],
        layer="Before",
    )
    for drawn in (iso, dims):
        for piece_id, piece in drawn.items():
            new = piece_id in step.pieces
            if piece.visible:
                exporter.add_shape(piece.visible, layer="New" if new else "Before")
            if new and piece.hidden:
                exporter.add_shape(piece.hidden, layer="NewHidden")
    if dimensions.lines:
        exporter.add_shape(
            [Edge.make_line(a, b) for a, b in dimensions.lines], layer="Dimensions"
        )
    if labels:
        exporter.add_shape(
            [
                Polygon(
                    (b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]), align=None
                )
                for b in labels.values()
            ],
            layer="LabelGround",
        )
    heading_size = text_size(_heading(step), 0.0)
    texts = [
        Pos(MARGIN + heading_size[0] / 2, PAGE_HEIGHT - HEADING / 2)
        * text_shape(_heading(step), 0.0),
        *(
            Pos((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) * text_shape(piece_id, 0.0)
            for piece_id, b in labels.items()
        ),
        *(
            Pos(*label.centre) * text_shape(label.text, label.rotation)
            for label in dimensions.labels
        ),
        *(Polygon(*arrow_points(*arrow), align=None) for arrow in dimensions.arrows),
    ]
    exporter.add_shape(texts, layer="Text")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "step.svg"
        exporter.write(str(path))
        svg = path.read_text()
    return StepImage(step, iso, dims, labels, view, dimensions, svg)


def image_name(step: PlannedStep, count: int) -> str:
    """step-01.png, ...; wide enough for every step number."""
    return f"step-{step.number:0{max(2, len(str(count)))}d}.png"


def part_image_name(number: int, count: int) -> str:
    """part-01.png, ...; wide enough for every drawn part."""
    return f"part-{number:0{max(2, len(str(count)))}d}.png"


def _drawn(groups: list[PartGroup]) -> list[PartGroup]:
    # A part without holes is only cut to length: the table is enough
    return [group for group in groups if group.holes]


def _parts(assembly: Assembly) -> list[str]:
    """Every part's lumber, length and count, then the drawings of the
    drilled ones."""
    groups = part_groups(assembly)
    drawn = _drawn(groups)
    images = {
        group.pieces: part_image_name(number, len(drawn))
        for number, group in enumerate(drawn, 1)
    }
    lines = [
        "## Parts",
        "",
        "| Pieces | Lumber | Length (mm) | Count | Drawing |",
        "|--------|--------|-------------|-------|---------|",
    ]
    for group in groups:
        image = images.get(group.pieces)
        lumber = assembly.model.pieces[group.pieces[0]].type.value
        lines.append(
            f"| {', '.join(group.pieces)} | {lumber} | {format_mm(group.size[2])} "
            f"| {len(group.pieces)} | {f'[{image}]({image})' if image else ''} |"
        )
    lines.append("")
    for number, group in enumerate(drawn, 1):
        lines += [
            f"### {group.name}",
            "",
            f"![Part {number}]({images[group.pieces]})",
            "",
        ]
    return lines


def grouping_hint(plan: StepPlan) -> str | None:
    """How to group the steps, with the design's own first pieces; None when
    a steps block is declared or there is one step only, nothing to group."""
    if plan.declared or len(plan.steps) < 2:
        return None
    first = ", ".join(plan.steps[0].pieces)
    return (
        "No steps block: each step adds one piece. Group pieces with a steps "
        f'block, e.g. `steps {{ "Frame": {first}, ... }}`.'
    )


def steps_markdown(assembly: Assembly, plan: StepPlan, title: str) -> str:
    """The instructions page: the parts to make, then per step its heading,
    image, pieces and fasteners. No prose: the images and numbers tell how."""
    lines = [f"# {title}: assembly steps", ""]
    hint = grouping_hint(plan)
    if hint:
        lines += [hint, ""]
    lines += _parts(assembly)
    for step in plan.steps:
        lines += [
            f"## {_heading(step)}",
            "",
            f"![Step {step.number}]({image_name(step, len(plan.steps))})",
            "",
            "| Piece | Lumber | Length (mm) |",
            "|-------|--------|-------------|",
        ]
        for piece_id in step.pieces:
            piece = assembly.model.pieces[piece_id]
            length = format_mm(piece.length) if piece.length is not None else "?"
            lines.append(f"| {piece_id} | {piece.type.value} | {length} |")
        hardware = count_hardware(assembly, step.connections)
        if hardware:
            lines += ["", "| Fastener | Count |", "|----------|-------|"]
            lines += [f"| {item.name} | {item.count} |" for item in hardware]
        lines.append("")
    return "\n".join(lines)


@dataclass
class Instructions:
    """The written files and what the user should hear about them."""

    files: list[Path]
    drawings: int
    """How many of ``files`` are part drawings."""
    declared: bool
    crowded: list[str]
    hint: str | None
    """How to group the steps (see ``grouping_hint``)."""


def write_instructions(
    assembly: Assembly, part: Compound, directory: Path, title: str, size: int = 1600
) -> Instructions:
    """Write ``steps.md``, one PNG per drilled part and one per step
    (``size`` px wide) into ``directory``, creating it if needed. Images
    left there by an earlier run with more parts or steps are removed."""
    plan = plan_steps(assembly)
    drawn = _drawn(part_groups(assembly))
    directory.mkdir(parents=True, exist_ok=True)
    files, crowded = [], []
    for number, group in enumerate(drawn, 1):
        sheet = part_sheet(assembly, group)
        path = directory / part_image_name(number, len(drawn))
        path.write_bytes(sheet.png(size))
        files.append(path)
        crowded += sheet.dimensions.crowded
    for step in plan.steps:
        image = step_image(assembly, part, step)
        path = directory / image_name(step, len(plan.steps))
        path.write_bytes(image.png(size))
        files.append(path)
        crowded += image.dimensions.crowded
    page = directory / "steps.md"
    page.write_text(steps_markdown(assembly, plan, title))
    # An old image would pass for a part or a step of this design
    for old in directory.iterdir():
        if _IMAGE.fullmatch(old.name) and old not in files:
            old.unlink()
    return Instructions(
        [page, *files], len(drawn), plan.declared, crowded, grouping_hint(plan)
    )
