"""Tests for the assembly instructions: step images and the steps page."""

from itertools import combinations
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("build123d")

from nichiyou_daiku.core.assembly import Assembly  # noqa: E402
from nichiyou_daiku.core.assembly.steps import (  # noqa: E402
    _ISOMETRIC_SIDE,
    plan_steps,
)
from nichiyou_daiku.dsl import parse_dsl  # noqa: E402
from nichiyou_daiku.shell.build123d_export import assembly_to_build123d  # noqa: E402
from nichiyou_daiku.shell.drawing import arrow_points  # noqa: E402
from nichiyou_daiku.shell.instructions import (  # noqa: E402
    _ISOMETRIC,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    _advice,
    _cue,
    image_name,
    part_image_name,
    step_image,
    steps_markdown,
    write_instructions,
)
from nichiyou_daiku.shell.views import project  # noqa: E402

SHELF = (
    Path(__file__).parents[2] / "skills" / "design" / "examples" / "two-tier-shelf.nd"
).read_text()
CORNER = "(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n"
# The corner joined with dowels: both pieces drilled, each its own part
DOWELLED = "(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0 D(:8x30)]- b\n"
# A third piece across the far end of b: two steps without a steps block
THREE = CORNER + "(c:2x4 =400)\nb -[TF<0 BD<0]- c\n"
# Without a steps block each step adds one piece; step 4 adds leg_3 at the
# back, so its dimension view looks from the back
TABLE = (
    Path(__file__).parents[2] / "examples" / "nd_files" / "simple_table_compact.nd"
).read_text()
# 39 slats 12.5mm apart up a 2m post, all in one step
CROWDED = (
    "(rail:2x4 =2000)\n"
    + "".join(
        f"(s{i}:2x2 =300)\nrail -[RF<{i * 50.5:g} BT<0]- s{i}\n" for i in range(39)
    )
    + 'steps {\n  "All": rail, '
    + ", ".join(f"s{i}" for i in range(39))
    + "\n}\n"
)


# Two boards on a rail, seen from above one above the other on the page
BOARDS = """(leg_1:2x4 =720)
(leg_3:2x4 =720)
(apron_left:2x4 =524)
(board_a:1x4 =300)
(board_b:1x4 =300)
leg_1 -[BR<100 DB<0]- apron_left
leg_3 -[FR<100 TB<0]- apron_left
apron_left -[RF<50 BT<0]- board_a
apron_left -[RF<350 BT<0]- board_b
steps {
  "Frame": leg_1, leg_3, apron_left
  "Boards": board_a, board_b
}
"""


@pytest.fixture(scope="module")
def table():
    """Steps 1, 4 and 13 of the table: the first leg alone, a leg at the
    back, and a top board."""
    assembly = Assembly.of(parse_dsl(TABLE))
    part = assembly_to_build123d(assembly, fillet_radius=0)
    steps = plan_steps(assembly).steps
    return {n: step_image(assembly, part, steps[n - 1]) for n in (1, 4, 13)}


@pytest.fixture(scope="module")
def table_step_4(table):
    return table[4]


def _points(lines, leave_out=()) -> np.ndarray:
    """Points along the visible lines of every piece but ``leave_out``."""
    return np.array(
        [
            (p.X, p.Y)
            for piece_id, piece in lines.items()
            if piece_id not in leave_out
            for shape in piece.visible
            for edge in shape.edges()
            for p in (edge.position_at(t / 40) for t in range(41))
        ]
    )


def _inside(points: np.ndarray, box) -> bool:
    return bool(
        (
            (points[:, 0] > box[0])
            & (points[:, 0] < box[2])
            & (points[:, 1] > box[1])
            & (points[:, 1] < box[3])
        ).any()
    )


def _direction(cue) -> np.ndarray:
    """The way an arrow points: from the middle of its tail to its tip."""
    tail = (np.array(cue[0]) + np.array(cue[-1])) / 2
    way = np.array(cue[3]) - tail
    return way / np.linalg.norm(way)


def _unit(vector) -> np.ndarray:
    v = np.asarray(vector, dtype=float)
    return v / np.linalg.norm(v)


def _box(points):
    xs, ys = [x for x, _ in points], [y for _, y in points]
    return min(xs), min(ys), max(xs), max(ys)


@pytest.fixture(scope="module")
def shelf():
    assembly = Assembly.of(parse_dsl(SHELF))
    part = assembly_to_build123d(assembly, fillet_radius=0)
    plan = plan_steps(assembly)
    return assembly, plan, [step_image(assembly, part, step) for step in plan.steps]


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


def _layer(svg: str, name: str) -> str:
    return svg.split(f'id="{name}"', 1)[1].split("</g>", 1)[0]


def _drawn(svg: str, layer: str) -> int:
    body = _layer(svg, layer)
    return body.count("<line") + body.count("<path")


def test_this_steps_pieces_are_black_and_earlier_ones_grey(shelf):
    _, plan, images = shelf
    assert set(images[3].lines) == set(plan.steps[3].shown)
    # The first step has nothing earlier: its grey layer holds the border only
    border = 4
    assert _drawn(images[0].svg, "Before") == border
    assert _drawn(images[0].svg, "New") > 0
    assert _drawn(images[3].svg, "Before") > border
    assert _drawn(images[3].svg, "New") > 0


def test_hidden_lines_are_left_out(shelf):
    # Dashed back edges only crowd the image; what shows is enough to build
    _, _, images = shelf
    for image in images:
        assert any(piece.hidden for piece in image.lines.values())
        assert "stroke-dasharray" not in image.svg, image.step.name


def test_every_new_piece_is_named_in_every_step(shelf):
    # A piece whose centre is hidden is named where some of it shows
    _, _, images = shelf
    for image in images:
        names = set(image.labels) - set(image.references)
        assert names == set(image.step.pieces), image.step.name


def test_rewriting_removes_images_of_steps_that_are_gone(tmp_path):
    for source in (THREE, CORNER):
        assembly = Assembly.of(parse_dsl(source))
        part = assembly_to_build123d(assembly, fillet_radius=0)
        write_instructions(assembly, part, tmp_path, "design", size=400)
    (tmp_path / "notes.txt").write_text("mine")
    write_instructions(assembly, part, tmp_path, "design", size=400)
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "notes.txt",
        "step-01.png",
        "steps.md",
    ]


def test_labels_name_this_steps_pieces_without_overlapping(shelf):
    _, plan, images = shelf
    top = images[4]
    assert set(top.labels) - set(top.references) == set(plan.steps[4].pieces)
    for image in images:
        assert set(image.labels) <= {*image.step.pieces, *image.references}
        boxes = list(image.labels.values())
        assert [(a, b) for a, b in combinations(boxes, 2) if _overlap(a, b)] == []


def test_pieces_not_drawn_hide_no_labels(shelf):
    # The right frame is drawn alone; the left frame does not hide its aprons
    _, _, images = shelf
    assert {"apron_upper_right", "apron_lower_right"} <= set(images[1].labels)


def test_dimension_view_shows_where_the_shelf_boards_go(shelf):
    _, _, images = shelf
    texts = [label.text for label in images[3].dimensions.labels]
    assert texts.count("22") == 3
    assert "600" in texts


def test_frame_heights_are_dimensioned_from_the_side(shelf):
    _, _, images = shelf
    assert images[0].view.caption == "from -x"
    texts = [label.text for label in images[0].dimensions.labels]
    assert {"150", "453", "781", "224", "300"} <= set(texts)


def test_dimension_values_touch_no_line_and_no_other_value(shelf):
    _, _, images = shelf
    for image in images:
        out = image.dimensions
        segments = list(out.lines)
        for arrow in out.arrows:
            a, b, c = arrow_points(*arrow)
            segments += [(a, b), (b, c), (c, a)]
        boxes = [label.box for label in out.labels]
        assert [
            (box, s) for box in boxes for s in segments if _crosses(box, s)
        ] == [], image.step.name
        assert [(a, b) for a, b in combinations(boxes, 2) if _overlap(a, b)] == []
        assert out.crowded == []


def test_steps_page_lists_each_step_with_its_pieces_and_fasteners(shelf):
    assembly, plan, _ = shelf
    page = steps_markdown(assembly, plan, "two-tier-shelf")
    assert page.startswith("# two-tier-shelf: assembly steps\n")
    assert "## Step 1 - Left frame\n" in page
    assert "## Step 2 - Right frame (sub-assembly)\n" in page
    assert "## Step 3 - Join (join)\n" in page
    assert "![Step 4](step-04.png)" in page
    assert "| shelf_2 | 2x4 | 300 |" in page
    first = page.split("## Step 2", 1)[0]
    # Four connections, two dowels each
    assert "| Dowel 8x30 | 8 |" in first
    assert "No steps block" not in page


def test_steps_page_lists_the_parts_before_the_steps(shelf):
    assembly, plan, _ = shelf
    page = steps_markdown(assembly, plan, "two-tier-shelf")
    parts = page.split("## Step 1", 1)[0]
    assert "## Parts\n" in parts
    assert "| Pieces | Lumber | Length (mm) | Count | Drawing |" in parts
    assert "| leg_1 | 2x4 | 781 | 1 | [part-01.png](part-01.png) |" in parts
    assert (
        "| shelf_1, shelf_2, shelf_3, shelf_4 | 2x4 | 300 | 4 "
        "| [part-10.png](part-10.png) |"
    ) in parts
    assert (
        "### shelf_1, shelf_2, shelf_3, shelf_4 ×4\n\n![Part 10](part-10.png)" in parts
    )


def test_parts_without_holes_are_listed_without_a_drawing():
    assembly = Assembly.of(parse_dsl(CORNER))
    page = steps_markdown(assembly, plan_steps(assembly), "corner")
    assert "| a, b | 2x4 | 400 | 2 |  |" in page
    assert "part-" not in page


def test_steps_page_without_steps_says_how_to_group_them():
    assembly = Assembly.of(parse_dsl(THREE))
    page = steps_markdown(assembly, plan_steps(assembly), "three")
    assert "No steps block: each step adds one piece" in page
    assert '`steps { "Frame": a, b, ... }`' in page
    assert "## Step 1\n" in page
    assert "## Step 2\n" in page


def test_a_single_step_needs_no_word_about_grouping():
    assembly = Assembly.of(parse_dsl(CORNER))
    assert "No steps block" not in steps_markdown(
        assembly, plan_steps(assembly), "corner"
    )


def test_write_instructions_writes_the_page_and_one_image_per_step(tmp_path):
    assembly = Assembly.of(parse_dsl(CORNER))
    part = assembly_to_build123d(assembly, fillet_radius=0)
    result = write_instructions(assembly, part, tmp_path / "out", "corner", size=400)
    assert [path.name for path in result.files] == ["steps.md", "step-01.png"]
    assert (tmp_path / "out" / "step-01.png").read_bytes().startswith(b"\x89PNG")
    assert not result.declared
    assert result.crowded == []


def test_write_instructions_draws_each_drilled_part(tmp_path):
    assembly = Assembly.of(parse_dsl(DOWELLED))
    part = assembly_to_build123d(assembly, fillet_radius=0)
    result = write_instructions(assembly, part, tmp_path, "corner", size=400)
    assert [path.name for path in result.files] == [
        "steps.md",
        "part-01.png",
        "part-02.png",
        "step-01.png",
    ]
    assert result.drawings == 2
    assert (tmp_path / "part-01.png").read_bytes().startswith(b"\x89PNG")


def test_rewriting_removes_drawings_of_parts_that_are_gone(tmp_path):
    for source in (DOWELLED, CORNER):
        assembly = Assembly.of(parse_dsl(source))
        part = assembly_to_build123d(assembly, fillet_radius=0)
        write_instructions(assembly, part, tmp_path, "design", size=400)
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "step-01.png",
        "steps.md",
    ]


def test_unconnected_pieces_get_a_step_each(tmp_path):
    # Two loose posts: each step draws its own part
    assembly = Assembly.of(parse_dsl("(a:2x4 =400)\n(b:2x4 =400)\n"))
    part = assembly_to_build123d(assembly, fillet_radius=0)
    result = write_instructions(assembly, part, tmp_path, "loose", size=400)
    assert [path.name for path in result.files] == [
        "steps.md",
        "step-01.png",
        "step-02.png",
    ]
    assert "## Step 2 (sub-assembly)" in (tmp_path / "steps.md").read_text()


def test_image_names_are_wide_enough_for_every_step(shelf):
    _, plan, _ = shelf
    assert image_name(plan.steps[2], 5) == "step-03.png"
    assert image_name(plan.steps[2], 120) == "step-003.png"
    assert part_image_name(3, 120) == "part-003.png"


def test_crowded_values_say_to_split_the_step():
    assembly = Assembly.of(parse_dsl(CROWDED))
    part = assembly_to_build123d(assembly, fillet_radius=0)
    image = step_image(assembly, part, plan_steps(assembly).steps[0])
    assert image.dimensions.crowded
    assert "step 1" in image.dimensions.crowded[0]
    assert "Split the step" in image.dimensions.crowded[0]


def test_a_one_piece_step_is_not_told_to_split():
    # Step 1 adds a and b; step 2 adds c alone and cannot be split
    plan = plan_steps(Assembly.of(parse_dsl(THREE)))
    assert "Split the step" in _advice(plan.steps[0])
    assert "Anchor Details" in _advice(plan.steps[1])


def test_ties_look_from_the_isometrics_side():
    # The plan, free of build123d, keeps its own copy of the image's side
    assert tuple(1 if c > 0 else -1 for c in _ISOMETRIC.origin) == _ISOMETRIC_SIDE


def test_the_arrow_points_the_way_the_dimension_view_looks(shelf, table_step_4):
    # The table's step is seen from the back, looking toward +y; the shelf's
    # boards from above, looking down
    assert table_step_4.view.caption == "from -y"
    assert _direction(table_step_4.cue) == pytest.approx(
        _unit(project(_ISOMETRIC, (0.0, 1.0, 0.0)))
    )
    _, _, images = shelf
    assert images[3].view.caption == "from +z"
    assert _direction(images[3].cue) == pytest.approx((0.0, -1.0))


def test_the_arrow_keeps_its_place_and_clear_of_the_drawing(shelf, table_step_4):
    _, _, images = shelf
    boxes = {_box(image.cue) for image in [*images, table_step_4]}
    # Only its direction changes: every arrow fits one corner box
    corner = (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )
    assert corner[2] < PAGE_WIDTH / 4 and corner[3] < PAGE_HEIGHT / 3
    for image in [*images, table_step_4]:
        cue = _box(image.cue)
        for piece in image.lines.values():
            for shape in piece.visible + piece.hidden:
                for edge in shape.edges():
                    points = [edge.position_at(t / 20) for t in range(21)]
                    assert not any(
                        cue[0] <= p.X <= cue[2] and cue[1] <= p.Y <= cue[3]
                        for p in points
                    ), image.step.name
        assert not any(_overlap(cue, box) for box in image.labels.values())


def test_the_dimension_view_names_the_steps_pieces(shelf):
    _, plan, images = shelf
    frame = images[0]
    assert set(frame.dimension_labels) <= set(plan.steps[0].pieces)
    assert {"leg_1", "leg_3"} <= set(frame.dimension_labels)
    # leg_1 and leg_3 sit apart in both halves: they tell left from right
    assert frame.references == []


def test_a_reference_piece_tells_left_from_right_when_the_step_cannot(
    table_step_4,
):
    # leg_3 alone cannot show which way round the view is, so one earlier
    # piece is named in grey in both halves
    [reference] = table_step_4.references
    assert reference not in table_step_4.step.pieces
    assert reference in table_step_4.labels
    assert reference in table_step_4.dimension_labels


def test_a_step_named_in_one_half_only_gets_two_references():
    # The side table's joining aprons hide behind the legs seen from the
    # side, so two earlier pieces, apart across the view, show which way
    # round it is
    source = (
        Path(__file__).parents[2] / "skills" / "design" / "examples" / "side-table.nd"
    ).read_text()
    assembly = Assembly.of(parse_dsl(source))
    part = assembly_to_build123d(assembly, fillet_radius=0)
    join = step_image(assembly, part, plan_steps(assembly).steps[2])
    assert len(join.references) == 2
    a, b = (join.dimension_labels[p] for p in join.references)
    assert abs((a[0] + a[2]) / 2 - (b[0] + b[2]) / 2) >= 10


def test_one_grey_name_alone_is_left_out(shelf):
    # Only one earlier piece of the shelf's join can be named clear of the
    # others: a lone name cannot tell which way round the view is, and the
    # arrow already does
    _, _, images = shelf
    assert images[2].references == []


def test_grey_names_cover_no_other_piece(shelf, table):
    # A grey name stands on its own piece: its ground would hide the lines
    # of any other, and on another piece it would seem to name that one
    _, _, images = shelf
    for image in [*images, *table.values()]:
        for reference in image.references:
            for lines, boxes in (
                (image.lines, image.labels),
                (image.dimension_lines, image.dimension_labels),
            ):
                others = _points(lines, leave_out=(reference,))
                assert not _inside(others, boxes[reference]), (
                    image.step.number,
                    reference,
                )


def test_the_arrow_keeps_well_clear_of_a_drawing_that_reaches_its_corner(table):
    # The first leg alone is tall enough to reach the corner, so it is drawn
    # smaller; even so the arrow's tip must not seem to push at it
    first = table[1]
    every = np.array(
        [
            (p.X, p.Y)
            for piece in first.lines.values()
            for shape in piece.visible + piece.hidden
            for edge in shape.edges()
            for p in (edge.position_at(t / 40) for t in range(41))
        ]
    )
    width = every[:, 0].max() - every[:, 0].min()
    height = every[:, 1].max() - every[:, 1].min()
    area = (PAGE_WIDTH / 2 - 2 * 6.0, PAGE_HEIGHT - 10.0 - 6.0)
    assert max(width / area[0], height / area[1]) < 0.85
    drawn = _points(first.lines)
    gaps = np.linalg.norm(drawn - np.array(first.cue[3]), axis=1)
    assert gaps.min() >= 6.0


def test_a_grey_name_sits_apart_from_the_steps_own(table_step_4):
    [reference] = table_step_4.references
    leg, other = (table_step_4.dimension_labels[p] for p in ("leg_3", reference))
    assert abs((leg[0] + leg[2]) / 2 - (other[0] + other[2]) / 2) >= 10


def test_from_below_the_arrow_points_up():
    assert _direction(_cue((2, -1))) == pytest.approx((0.0, 1.0))


def test_a_top_view_needs_no_grey_name_when_its_names_sit_apart_up_the_page():
    # Seen from above nothing is mirrored: names one above the other already
    # tie the view to the isometric
    assembly = Assembly.of(parse_dsl(BOARDS))
    part = assembly_to_build123d(assembly, fillet_radius=0)
    boards = step_image(assembly, part, plan_steps(assembly).steps[1])
    assert boards.view.caption == "from +z"
    assert {"board_a", "board_b"} <= set(boards.dimension_labels)
    assert boards.references == []


def test_names_on_the_dimension_view_cross_no_dimension_line():
    assembly = Assembly.of(parse_dsl(CROWDED))
    part = assembly_to_build123d(assembly, fillet_radius=0)
    image = step_image(assembly, part, plan_steps(assembly).steps[0])
    segments = list(image.dimensions.lines)
    for arrow in image.dimensions.arrows:
        a, b, c = arrow_points(*arrow)
        segments += [(a, b), (b, c), (c, a)]
    assert [
        name
        for name, box in image.dimension_labels.items()
        if any(_crosses(box, segment) for segment in segments)
    ] == []
