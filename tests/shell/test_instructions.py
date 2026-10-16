"""Tests for the assembly instructions: step images and the steps page."""

from itertools import combinations
from pathlib import Path

import pytest

pytest.importorskip("build123d")

from nichiyou_daiku.core.assembly import Assembly  # noqa: E402
from nichiyou_daiku.core.assembly.steps import plan_steps  # noqa: E402
from nichiyou_daiku.dsl import parse_dsl  # noqa: E402
from nichiyou_daiku.shell.build123d_export import assembly_to_build123d  # noqa: E402
from nichiyou_daiku.shell.drawing import _arrow_points  # noqa: E402
from nichiyou_daiku.shell.instructions import (  # noqa: E402
    image_name,
    step_image,
    steps_markdown,
    write_instructions,
)

SHELF = (
    Path(__file__).parents[2] / "skills" / "design" / "examples" / "two-tier-shelf.nd"
).read_text()
CORNER = "(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n"
# A third piece across the far end of b: two steps without a steps block
THREE = CORNER + "(c:2x4 =400)\nb -[TF<0 BD<0]- c\n"
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


def test_hidden_lines_are_drawn_for_this_steps_pieces_only(shelf):
    _, plan, images = shelf
    join = images[2]
    assert any(join.lines[p].hidden for p in plan.steps[2].pieces)
    assert 'id="NewHidden"' in join.svg


def test_every_new_piece_is_named_in_every_step(shelf):
    # A piece whose centre is hidden is named where some of it shows
    _, _, images = shelf
    for image in images:
        assert set(image.labels) == set(image.step.pieces), image.step.name


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
    assert set(top.labels) == set(plan.steps[4].pieces)
    for image in images:
        assert set(image.labels) <= set(image.step.pieces)
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
    assert images[0].view.caption == "from +x"
    texts = [label.text for label in images[0].dimensions.labels]
    assert {"150", "453", "781", "224", "300"} <= set(texts)


def test_dimension_values_touch_no_line_and_no_other_value(shelf):
    _, _, images = shelf
    for image in images:
        out = image.dimensions
        segments = list(out.lines)
        for arrow in out.arrows:
            a, b, c = _arrow_points(*arrow)
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


def test_crowded_values_say_to_split_the_step():
    assembly = Assembly.of(parse_dsl(CROWDED))
    part = assembly_to_build123d(assembly, fillet_radius=0)
    image = step_image(assembly, part, plan_steps(assembly).steps[0])
    assert image.dimensions.crowded
    assert "step 1" in image.dimensions.crowded[0]
    assert "Split the step" in image.dimensions.crowded[0]
