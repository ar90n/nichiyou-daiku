# Part Drawings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `nichiyou-daiku steps design.nd` starts its instructions with the parts to make. A table lists every part (pieces made the same way grouped) with its lumber, length and count. Each drilled part gets a drawing: an isometric view with the drilled faces lettered and the reference end marked, then each drilled face seen from outside with its holes dimensioned from the reference end.

**Architecture:**
- **Parts (pure):** `core/assembly/parts.py` puts each piece's pilot holes in the piece's own axes. It groups pieces that match after a turn that brings the board onto itself, and gives each face's frame seen from outside (right, up, the faces across its edges), the face letters and the isometric's view direction.
- **Drawing:** `shell/parts.py` draws one part sheet. The isometric re-makes the piece with its holes and projects it with build123d's `project_to_viewport`. Each face view reuses the M4-3 dimensioning (`drawing._dimension`) through a chain made from the hole centres (`dimensioning.chain_from_stops`).
- **Instructions:** `shell/instructions.py` writes the Parts section of `steps.md` and `part-NN.png`; the `steps` command says how many drawings it wrote.

**Tech Stack:** Python 3.13, numpy, pydantic, build123d (`project_to_viewport`, `ExportSVG`), cairosvg, click, pytest. Run commands with `uv run` from the repository root on branch `feat/part-drawings`.

**Spec:** `docs/superpowers/specs/2026-10-16-part-drawings-design.md` (Japanese; binding).

**How the code was checked:** every patch below was written and run in a scratch copy before this plan. In a fresh clone of this branch, applying each task's test patch and then its implementation patch passes `ruff format --check`, `ruff check`, `pyright` and the whole suite. Each task's tests fail before its implementation patch, as each step's `Expected:` says.

## Global Constraints

- **No prose:** drawings, letters and numbers only. Titles, headings and table rows hold piece names, lumber, sizes and hole notes.
- **No text clashes:** in every part drawing of every example file, no text lies on other text or off the page, no dimension value lies on a dimension line or arrow, and no values are crowded.
- **Grouping:** the same lumber and size, and holes (face, centre, diameter, depth) that match within `TOLERANCE_MM = 0.05` after the identity or a half turn about z, x or y. Mirrored pieces stay apart. The drawing shows the first piece's holes.
- **Orientation:** a face is seen from outside: right × up is its outward normal. On a long face right is +z, so the down end (the reference end) is on the left. On top right is +x; on down it is −x.
- **Letters:** A, B, ... for the drilled faces in the order front, back, left, right, top, down. The front is lettered too when only the two ends are drilled and their holes change under a half turn about z. No other undrilled face gets a letter or a leader.
- **Hole notes:** `φ8 ↧15` (diameter, depth). A through hole is `φ2.5`, without a depth. Title counts are per piece, blind holes before through holes.
- **Scales:** along a face, as wide as the page allows and at most 0.8. Across, the same, unless the face would be under 22mm high; then it is stretched to 22mm. Values are true sizes. Hole circles have radius max(1, d/2 × the smaller scale).
- **Page:** 280mm wide and as high as the faces need. PNG at `--size` px wide (default 1600).
- **Parts section:** after the page title and the grouping hint, before the steps. Columns `Pieces | Lumber | Length (mm) | Count | Drawing`, in declaration order. The Drawing column links `part-NN.png`; the drawings follow the table under `### <names ×n>` headings. (The spec's §1 example showed `![](part-01.png)` in the table, which would show each drawing twice; the spec now shows the link.)
- **Dependencies:** `core/` does not import build123d. `shell/parts.py` needs build123d and is not imported by `shell/__init__.py`; `shell/instructions.py` imports it.
- **Messages:** code, comments, docstrings, docs and messages are in English. Comments are few and say why.
- **Patches:** apply each patch exactly with `git apply` from the repository root. Each one sits between the `git apply <<'EOF'` line and the closing `EOF` line.
- **Commits:** run `make check` before every commit and commit only if it passes: `make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log; [ $rc -eq 0 ] && git commit ...`.
- **Never commit:** dotfiles or `CLAUDE.md`.

## Review Focus

1. **Fonts in the CI container.** Text boxes come from the font build123d finds, and the clash tests measure them (`test_part_drawings_are_clean` over every example, Task 2). `make ci-local` must pass before merging.
2. **A part of many pieces.** Its title, which names every piece, wraps to the page width (`test_a_title_wider_than_the_page_is_wrapped`, Task 2). The Markdown heading and table row stay one line.
3. **Holes too dense to dimension.** Values that do not fit go to a row with leaders. When even that row overlaps, the command warns, naming the face and pointing to the report's Pilot Holes table, and still writes the drawing (`test_values_that_do_not_fit_point_to_the_pilot_holes_table`, Task 2).
4. **Every face drilled.** Letters A to F, the end faces with letters on all four sides, and no clashes (`test_every_face_drilled_is_lettered_without_clashes`, Task 2).
5. **A board turned end for end.** It is the same part, turned half about its width or its thickness (`test_boards_turned_end_for_end_are_one_part`, Task 1).

---

### Task 1: Pieces as parts (`core/assembly/parts.py`)

**Files:**
- Create: `src/nichiyou_daiku/core/assembly/parts.py`
- Test: `tests/core/test_parts.py` (new)

**Interfaces:**
- Consumes: `Assembly.boxes[piece_id]`, `Assembly.pilot_holes[piece_id]` (a list of `(SurfacePoint, Hole)`), `Point3D.of(box, surface_point)` (`core/geometry`), `face_normal(face)` (`core/placement.py`), `get_shape(piece)` (`core/piece.py`).
- Produces (all in `nichiyou_daiku.core.assembly.parts`):
  - `FACE_ORDER: tuple[Face, ...] = ("front", "back", "left", "right", "top", "down")`, `LONG_FACES`, `TOLERANCE_MM = 0.05`, `VIEW_ORDER` (the 8 diagonals, +z first).
  - `LocalHole(face: Face, point: tuple[float, float, float], diameter: float, depth: float | None)`: a `NamedTuple`; `point` is the centre on the face in the piece's axes (x across the width, y across the thickness, z along the length, the down end at z = 0); `depth` None is a through hole.
  - `PartGroup(pieces: tuple[str, ...], size: tuple[float, float, float], holes: tuple[LocalHole, ...])`: frozen pydantic; `.name -> str` (`"shelf_1, shelf_2 ×2"`, a single piece without `×1`).
  - `piece_size(assembly, piece_id) -> tuple[float, float, float]`, `piece_holes(assembly, piece_id) -> tuple[LocalHole, ...]`, `part_groups(assembly) -> list[PartGroup]` (declaration order).
  - `face_frame(face) -> tuple[np.ndarray, np.ndarray]` (right, up), `face_size(face, size) -> tuple[float, float]`, `face_point(face, point, size) -> tuple[float, float]` (from the face's lower-left corner seen from outside), `edge_neighbours(face) -> dict[str, Face]` (keys `top`, `bottom`, `left`, `right`).
  - `face_letters(holes, size) -> dict[Face, str]`, `view_direction(faces) -> tuple[int, int, int]`.

- [ ] **Step 1: Write the failing tests**

````bash
git apply <<'EOF'
diff --git a/tests/core/test_parts.py b/tests/core/test_parts.py
new file mode 100644
index 0000000..3b5d5b7
--- /dev/null
+++ b/tests/core/test_parts.py
@@ -0,0 +1,172 @@
+"""Tests for the parts to make: holes, groups and the faces of a drawing."""
+
+from pathlib import Path
+
+import numpy as np
+import pytest
+
+from nichiyou_daiku.core.assembly import Assembly
+from nichiyou_daiku.core.assembly.parts import (
+    FACE_ORDER,
+    LocalHole,
+    _same_holes,
+    edge_neighbours,
+    face_frame,
+    face_letters,
+    face_point,
+    face_size,
+    part_groups,
+    piece_holes,
+    view_direction,
+)
+from nichiyou_daiku.core.placement import face_normal
+from nichiyou_daiku.dsl import parse_dsl
+
+SHELF = (
+    Path(__file__).parents[2] / "skills" / "design" / "examples" / "two-tier-shelf.nd"
+).read_text()
+# The screwed shelf of patterns.md: the screws go through the posts
+SCREWED = """(side_l:2x4 =800)
+(side_r:2x4 =800)
+(shelf_bottom:2x4 =600)
+(shelf_top:2x4 =600)
+shelf_bottom -[DL<0 BL<100 S(Slim:3.8x65)]- side_l
+shelf_bottom -[TL<0 FL<100 S(Slim:3.8x65)]- side_r
+shelf_top -[DL<0 BL>38 S(Slim:3.8x65)]- side_l
+shelf_top -[TL<0 FL>38 S(Slim:3.8x65)]- side_r
+"""
+LEG = (89.0, 38.0, 781.0)
+
+
+@pytest.fixture(scope="module")
+def shelf() -> Assembly:
+    return Assembly.of(parse_dsl(SHELF))
+
+
+def _groups(assembly: Assembly) -> list[tuple[str, ...]]:
+    return [group.pieces for group in part_groups(assembly)]
+
+
+def test_piece_holes_are_in_the_pieces_own_axes(shelf):
+    holes = piece_holes(shelf, "leg_1")
+    assert len(holes) == 10
+    back = sorted(h.point for h in holes if h.face == "back")
+    # Dowels for the side aprons, 19 from the edge the left face is on
+    assert back[0] == pytest.approx((70.0, 0.0, 172.25))
+    assert {h.diameter for h in holes} == {8.0}
+    assert {h.depth for h in holes} == {15.0}
+
+
+def test_pieces_made_the_same_are_one_group(shelf):
+    groups = _groups(shelf)
+    assert ("shelf_1", "shelf_2", "shelf_3", "shelf_4") in groups
+    assert ("top_1", "top_2", "top_3", "top_4", "top_5", "top_6") in groups
+    assert len(groups) == 10
+
+
+def test_a_part_is_named_by_its_pieces(shelf):
+    groups = {group.pieces[0]: group for group in part_groups(shelf)}
+    assert groups["leg_1"].name == "leg_1"
+    assert groups["shelf_1"].name == "shelf_1, shelf_2, shelf_3, shelf_4 ×4"
+
+
+def test_mirrored_pieces_are_different_parts(shelf):
+    # The left and right front legs mirror each other: no turn matches them
+    groups = _groups(shelf)
+    assert ("leg_1",) in groups
+    assert ("leg_2",) in groups
+
+
+def test_pieces_matching_after_a_turn_are_one_part():
+    # The right post is the left post turned half about its length
+    groups = _groups(Assembly.of(parse_dsl(SCREWED)))
+    assert groups == [("side_l", "side_r"), ("shelf_bottom", "shelf_top")]
+
+
+@pytest.mark.parametrize("contact", ["FT", "BT"])
+def test_boards_turned_end_for_end_are_one_part(contact):
+    # b's holes are near its top end, a's near its down end: turning b end
+    # for end, about its width (FT) or its thickness (BT), matches them
+    source = (
+        "(post:2x4 =800)\n(a:2x4 =300)\n(b:2x4 =300)\n"
+        "post -[FL<100 BD<0 D(:8x30)]- a\n"
+        f"post -[FL<500 {contact}<0 D(:8x30)]- b\n"
+    )
+    assert ("a", "b") in _groups(Assembly.of(parse_dsl(source)))
+
+
+def test_through_holes_have_no_depth():
+    assembly = Assembly.of(parse_dsl(SCREWED))
+    post = piece_holes(assembly, "side_l")
+    shelf = piece_holes(assembly, "shelf_bottom")
+    assert {h.depth for h in post} == {None}
+    assert {h.depth for h in shelf} == {27.0}
+    assert {h.diameter for h in post + shelf} == {2.5}
+
+
+def test_holes_match_within_the_tolerance():
+    one = (LocalHole("back", (10.0, 0.0, 100.0), 8.0, 15.0),)
+    near = (LocalHole("back", (10.04, 0.0, 100.0), 8.0, 15.0),)
+    far = (LocalHole("back", (10.06, 0.0, 100.0), 8.0, 15.0),)
+    assert _same_holes(one, near)
+    assert not _same_holes(one, far)
+
+
+def test_every_face_is_seen_from_outside():
+    for face in FACE_ORDER:
+        right, up = face_frame(face)
+        assert np.cross(right, up) == pytest.approx(face_normal(face))
+
+
+def test_long_faces_have_the_down_end_on_the_left():
+    for face in ("front", "back", "left", "right"):
+        right, _ = face_frame(face)
+        assert tuple(right) == (0.0, 0.0, 1.0)
+        assert edge_neighbours(face)["left"] == "down"
+
+
+def test_face_points_are_measured_from_the_lower_left_corner(shelf):
+    holes = piece_holes(shelf, "leg_1")
+    back = sorted(face_point("back", h.point, LEG) for h in holes if h.face == "back")
+    assert back[0] == pytest.approx((172.25, 19.0))
+    top = sorted(face_point("top", h.point, LEG) for h in holes if h.face == "top")
+    assert top == [pytest.approx((22.25, 19.0)), pytest.approx((66.75, 19.0))]
+    assert face_size("back", LEG) == (781.0, 89.0)
+    assert face_size("top", LEG) == (89.0, 38.0)
+
+
+def test_neighbours_across_each_edge():
+    assert edge_neighbours("back")["top"] == "left"
+    assert edge_neighbours("back")["bottom"] == "right"
+    assert edge_neighbours("top") == {
+        "top": "front",
+        "bottom": "back",
+        "left": "left",
+        "right": "right",
+    }
+
+
+def test_drilled_faces_are_lettered_in_order(shelf):
+    holes = piece_holes(shelf, "leg_1")
+    assert face_letters(holes, LEG) == {"back": "A", "left": "B", "top": "C"}
+
+
+def test_ends_without_a_drilled_long_face_get_a_reference_when_turning_matters():
+    size = (89.0, 38.0, 400.0)
+    centred = (
+        LocalHole("top", (44.5, 19.0, 400.0), 8.0, 15.0),
+        LocalHole("down", (44.5, 19.0, 0.0), 8.0, 15.0),
+    )
+    # The same holes after a half turn: no reference needed
+    assert face_letters(centred, size) == {"top": "A", "down": "B"}
+    off_centre = (
+        LocalHole("top", (20.0, 19.0, 400.0), 8.0, 15.0),
+        LocalHole("down", (20.0, 19.0, 0.0), 8.0, 15.0),
+    )
+    assert face_letters(off_centre, size) == {"top": "A", "down": "B", "front": "C"}
+
+
+def test_view_shows_the_most_lettered_faces():
+    assert view_direction(["back", "left", "top"]) == (-1, -1, 1)
+    # A tie keeps the first diagonal
+    assert view_direction(["top"]) == (1, 1, 1)
EOF
````

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/core/test_parts.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'nichiyou_daiku.core.assembly.parts'`

- [ ] **Step 3: Implement**

````bash
git apply <<'EOF'
diff --git a/src/nichiyou_daiku/core/assembly/parts.py b/src/nichiyou_daiku/core/assembly/parts.py
new file mode 100644
index 0000000..b5dab3a
--- /dev/null
+++ b/src/nichiyou_daiku/core/assembly/parts.py
@@ -0,0 +1,248 @@
+"""The parts to make before assembling: each piece's holes in its own axes,
+pieces grouped when they are made the same, and how a part drawing shows
+each face. Free of build123d.
+
+A piece's axes: x across its width, y across its thickness, z along its
+length, from 0 at one corner; the down end is z = 0.
+"""
+
+from typing import NamedTuple, Sequence
+
+import numpy as np
+from pydantic import BaseModel
+
+from nichiyou_daiku.core.geometry import Face, Point3D
+from nichiyou_daiku.core.piece import get_shape
+from nichiyou_daiku.core.placement import face_normal
+
+from .builder import Assembly
+
+FACE_ORDER: tuple[Face, ...] = ("front", "back", "left", "right", "top", "down")
+LONG_FACES: tuple[Face, ...] = ("front", "back", "left", "right")
+TOLERANCE_MM = 0.05
+"""Holes this close are the same hole when pieces are compared."""
+
+# The turns that bring a board onto itself: none, and half turns about z, x, y
+_TURNS = (
+    np.diag([1.0, 1.0, 1.0]),
+    np.diag([-1.0, -1.0, 1.0]),
+    np.diag([1.0, -1.0, -1.0]),
+    np.diag([-1.0, 1.0, -1.0]),
+)
+
+# Seen from outside, a long face has its length to the right; the ends are
+# turned so their width runs right on top and left on the down end
+_RIGHT = {
+    "front": (0.0, 0.0, 1.0),
+    "back": (0.0, 0.0, 1.0),
+    "left": (0.0, 0.0, 1.0),
+    "right": (0.0, 0.0, 1.0),
+    "top": (1.0, 0.0, 0.0),
+    "down": (-1.0, 0.0, 0.0),
+}
+
+# The 8 diagonal views of the isometric, in the order ties are broken
+VIEW_ORDER = (
+    (1, 1, 1),
+    (1, -1, 1),
+    (-1, 1, 1),
+    (-1, -1, 1),
+    (1, 1, -1),
+    (1, -1, -1),
+    (-1, 1, -1),
+    (-1, -1, -1),
+)
+
+
+class LocalHole(NamedTuple):
+    """A hole in a piece's own axes; depth None is a hole drilled through."""
+
+    face: Face
+    point: tuple[float, float, float]
+    diameter: float
+    depth: float | None
+
+
+class PartGroup(BaseModel, frozen=True):
+    """Pieces made the same way; the drawing shows the first one's holes."""
+
+    pieces: tuple[str, ...]
+    size: tuple[float, float, float]
+    holes: tuple[LocalHole, ...]
+
+    @property
+    def name(self) -> str:
+        """The pieces, with how many when there are more than one."""
+        count = len(self.pieces)
+        return ", ".join(self.pieces) + (f" ×{count}" if count > 1 else "")
+
+
+def piece_size(assembly: Assembly, piece_id: str) -> tuple[float, float, float]:
+    """Width, thickness and length of a piece."""
+    shape = get_shape(assembly.model.pieces[piece_id])
+    return shape.width, shape.height, shape.length
+
+
+def piece_holes(assembly: Assembly, piece_id: str) -> tuple[LocalHole, ...]:
+    """The piece's holes, at their centres on the faces they are drilled into."""
+    box = assembly.boxes[piece_id]
+    holes = []
+    for position, hole in assembly.pilot_holes.get(piece_id, []):
+        point = Point3D.of(box, position)
+        holes.append(
+            LocalHole(
+                position.face, (point.x, point.y, point.z), hole.diameter, hole.depth
+            )
+        )
+    return tuple(holes)
+
+
+def _face_along(direction: np.ndarray) -> Face:
+    return next(f for f in FACE_ORDER if np.allclose(face_normal(f), direction))
+
+
+def _turned(
+    holes: Sequence[LocalHole], turn: np.ndarray, size: tuple[float, float, float]
+) -> list[LocalHole]:
+    centre = np.array(size) / 2
+    turned = []
+    for hole in holes:
+        x, y, z = turn @ (np.array(hole.point) - centre) + centre
+        turned.append(
+            LocalHole(
+                _face_along(turn @ face_normal(hole.face)),
+                (float(x), float(y), float(z)),
+                hole.diameter,
+                hole.depth,
+            )
+        )
+    return turned
+
+
+def _close(a: float | None, b: float | None) -> bool:
+    if a is None or b is None:
+        return a is None and b is None
+    return abs(a - b) <= TOLERANCE_MM
+
+
+def _same_holes(a: Sequence[LocalHole], b: Sequence[LocalHole]) -> bool:
+    if len(a) != len(b):
+        return False
+    left = list(b)
+    for hole in a:
+        match = next(
+            (
+                other
+                for other in left
+                if other.face == hole.face
+                and all(_close(p, q) for p, q in zip(hole.point, other.point))
+                and _close(hole.diameter, other.diameter)
+                and _close(hole.depth, other.depth)
+            ),
+            None,
+        )
+        if match is None:
+            return False
+        left.remove(match)
+    return True
+
+
+def part_groups(assembly: Assembly) -> list[PartGroup]:
+    """The pieces grouped by how they are made, in declaration order: the
+    same lumber and length, and holes that match after a turn that brings
+    the board onto itself (a mirrored piece is a different part)."""
+    groups: list[PartGroup] = []
+    for piece_id, piece in assembly.model.pieces.items():
+        size = piece_size(assembly, piece_id)
+        holes = piece_holes(assembly, piece_id)
+        for i, group in enumerate(groups):
+            first = assembly.model.pieces[group.pieces[0]]
+            if (
+                first.type == piece.type
+                and all(_close(p, q) for p, q in zip(group.size, size))
+                and any(
+                    _same_holes(group.holes, _turned(holes, turn, size))
+                    for turn in _TURNS
+                )
+            ):
+                groups[i] = group.model_copy(
+                    update={"pieces": (*group.pieces, piece_id)}
+                )
+                break
+        else:
+            groups.append(PartGroup(pieces=(piece_id,), size=size, holes=holes))
+    return groups
+
+
+def face_frame(face: Face) -> tuple[np.ndarray, np.ndarray]:
+    """Right and up of a face seen from outside (right x up points out)."""
+    right = np.array(_RIGHT[face])
+    return right, np.cross(face_normal(face), right)
+
+
+def face_size(face: Face, size: tuple[float, float, float]) -> tuple[float, float]:
+    """Width and height of a face seen from outside."""
+    right, up = face_frame(face)
+    extent = np.array(size)
+    return float(abs(right @ extent)), float(abs(up @ extent))
+
+
+def face_point(
+    face: Face, point: tuple[float, float, float], size: tuple[float, float, float]
+) -> tuple[float, float]:
+    """A point of the face from its lower-left corner seen from outside."""
+    right, up = face_frame(face)
+    extent = np.array(size)
+    p = np.array(point)
+
+    def from_corner(axis: np.ndarray) -> float:
+        # The face spans 0..size on each axis, so the corner is at the minimum
+        return float(p @ axis - np.minimum(axis * extent, 0).sum())
+
+    return from_corner(right), from_corner(up)
+
+
+def edge_neighbours(face: Face) -> dict[str, Face]:
+    """The faces across each edge of a face seen from outside."""
+    right, up = face_frame(face)
+    return {
+        "top": _face_along(up),
+        "bottom": _face_along(-up),
+        "left": _face_along(-right),
+        "right": _face_along(right),
+    }
+
+
+def _end_turns_free(
+    holes: Sequence[LocalHole], size: tuple[float, float, float]
+) -> bool:
+    """Whether each end's holes look the same after a half turn about z."""
+    ends = [h for h in holes if h.face in ("top", "down")]
+    return _same_holes(ends, _turned(ends, _TURNS[1], size))
+
+
+def face_letters(
+    holes: Sequence[LocalHole], size: tuple[float, float, float]
+) -> dict[Face, str]:
+    """A, B, ... for the drilled faces in ``FACE_ORDER``. A face without
+    holes gets one only when nothing else ties the two ends' turn together:
+    both ends drilled, no long face drilled and the end holes not the same
+    after a half turn; then the front is lettered too."""
+    drilled: list[Face] = [f for f in FACE_ORDER if any(h.face == f for h in holes)]
+    lettered: list[Face] = list(drilled)
+    if (
+        "top" in drilled
+        and "down" in drilled
+        and not any(f in LONG_FACES for f in drilled)
+        and not _end_turns_free(holes, size)
+    ):
+        lettered.append("front")
+    return {face: "ABCDEF"[i] for i, face in enumerate(lettered)}
+
+
+def view_direction(faces: Sequence[Face]) -> tuple[int, int, int]:
+    """The diagonal view that shows the most of ``faces``."""
+    return max(
+        VIEW_ORDER,
+        key=lambda d: sum(1 for f in faces if face_normal(f) @ np.array(d) > 0),
+    )
EOF
````

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/core/test_parts.py -q`
Expected: `16 passed`

- [ ] **Step 5: Check**

Check that the turns are what the tests rely on. (1) Temporarily delete the line `np.diag([1.0, -1.0, -1.0]),` from `_TURNS`, run `uv run pytest tests/core/test_parts.py -q -k end_for_end`, expect `1 failed, 1 passed`, and restore it. (2) Temporarily add `np.diag([-1.0, 1.0, 1.0]),` (a mirror) to `_TURNS`, run `-k mirrored`, expect `1 failed`, and restore it.

- [ ] **Step 6: Commit**

```bash
make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log
[ $rc -eq 0 ] && git add src/nichiyou_daiku/core/assembly/parts.py tests/core/test_parts.py && git commit -m "feat: Group the pieces made the same way and place their holes

Each piece's holes in its own axes; pieces that match after a turn of
the board are one part, mirrored ones are not. Each face gets its
frame seen from outside, its letter and its neighbours for drawing."
```

---

### Task 2: Part drawings (`shell/parts.py`)

**Files:**
- Modify: `src/nichiyou_daiku/shell/dimensioning.py` (add `chain_from_stops` before `chains`)
- Create: `src/nichiyou_daiku/shell/parts.py`
- Test: `tests/shell/test_dimensioning.py` (two tests), `tests/shell/test_parts.py` (new)

**Interfaces:**
- Consumes: Task 1's `PartGroup`, `part_groups`, `LocalHole`, `edge_neighbours`, `face_letters`, `face_point`, `face_size`, `view_direction`; from `shell/drawing.py` (M4-3) `_dimension(chain, view, out, where, advice)`, `_View(view, origin, scale, rect, ...)`, `_Dimensions`, `_levels`, `_line_height`, `_text`, `_text_size`, `_arrow_points`; `format_mm`.
- Produces:
  - `chain_from_stops(view: str, axis: Axis, side: Side, stops: Iterable[float]) -> Chain` in `shell/dimensioning.py`: stops sorted and merged within `PRECISION_MM`, no stretch marked as lumber, no segments when there is nothing between the ends.
  - In `nichiyou_daiku.shell.parts`: `PAGE_WIDTH = 280.0`; `PartSheet` (dataclass: `group`, `letters: dict[Face, str]`, `faces: dict[Face, Rect]` (each drilled face's outline), `texts: list[tuple[str, Rect]]` (every word and number with its box), `dimensions: _Dimensions`, `svg: str`; `.png(size: int) -> bytes`); `part_title(assembly, group) -> str` (`"leg_1   2x4   781   φ8 ↧15 ×10"`); `part_sheet(assembly, group) -> PartSheet`. Crowded values add to `sheet.dimensions.crowded` a message naming `face <letter> of <first piece>` and ending `The report's Pilot Holes table lists the same holes`.

- [ ] **Step 1: Write the failing tests**

````bash
git apply <<'EOF'
diff --git a/tests/shell/test_dimensioning.py b/tests/shell/test_dimensioning.py
index 067004c..ab1458e 100644
--- a/tests/shell/test_dimensioning.py
+++ b/tests/shell/test_dimensioning.py
@@ -6,7 +6,15 @@ import pytest
 
 from nichiyou_daiku.core.assembly import Assembly
 from nichiyou_daiku.dsl import parse_dsl
-from nichiyou_daiku.shell.dimensioning import Chain, _stops, chain_for, chains, spread
+from nichiyou_daiku.shell.dimensioning import (
+    Chain,
+    Segment,
+    _stops,
+    chain_for,
+    chain_from_stops,
+    chains,
+    spread,
+)
 
 SHELF = (
     Path(__file__).parents[2] / "skills" / "design" / "examples" / "two-tier-shelf.nd"
@@ -129,3 +137,18 @@ def test_a_chain_can_cover_some_pieces_only():
     assert [segment.text for segment in chain.segments] == ["38", "224", "38"]
     assert chain.overall.text == "300"
     assert chain.view == "from +x"
+
+
+def test_a_chain_through_hole_centres_stops_at_each_once():
+    # Two holes side by side across the face share one stop along it
+    chain = chain_from_stops("from -y", "x", "below", [781.0, 172.25, 0.0, 172.25])
+    assert chain.stops == (0.0, 172.25, 781.0)
+    assert chain.segments == (
+        Segment(0.0, 172.25, lumber=False),
+        Segment(172.25, 781.0, lumber=False),
+    )
+    assert chain.overall.text == "781"
+
+
+def test_a_chain_without_stops_between_its_ends_has_only_the_overall_size():
+    assert chain_from_stops("from -y", "z", "left", [0.0, 89.0]).segments == ()
diff --git a/tests/shell/test_parts.py b/tests/shell/test_parts.py
new file mode 100644
index 0000000..f6f5c0e
--- /dev/null
+++ b/tests/shell/test_parts.py
@@ -0,0 +1,244 @@
+"""Tests for the part drawings."""
+
+from functools import lru_cache
+from itertools import combinations
+from pathlib import Path
+
+import pytest
+
+pytest.importorskip("build123d")
+
+from nichiyou_daiku.core.assembly import Assembly  # noqa: E402
+from nichiyou_daiku.core.assembly.parts import (  # noqa: E402
+    LocalHole,
+    PartGroup,
+    part_groups,
+)
+from nichiyou_daiku.dsl import parse_dsl  # noqa: E402
+from nichiyou_daiku.shell.drawing import _arrow_points, _text_size  # noqa: E402
+from nichiyou_daiku.shell.parts import (  # noqa: E402
+    PAGE_WIDTH,
+    part_sheet,
+    part_title,
+)
+
+ROOT = Path(__file__).parents[2]
+EXAMPLES = sorted(
+    [
+        *(ROOT / "examples" / "nd_files").glob("*.nd"),
+        *(ROOT / "skills" / "design" / "examples").glob("*.nd"),
+    ]
+)
+SHELF = ROOT / "skills" / "design" / "examples" / "two-tier-shelf.nd"
+# The screwed shelf of patterns.md with its bottom shelf on dowels instead:
+# a post then has through holes and blind holes of two sizes on one face
+MIXED = """(side_l:2x4 =800)
+(side_r:2x4 =800)
+(shelf_bottom:2x4 =600)
+(shelf_top:2x4 =600)
+side_l -[BL<100 DL<0 D(:8x30)]- shelf_bottom
+side_r -[FL<100 TL<0 D(:8x30)]- shelf_bottom
+shelf_top -[DL<0 BL>38 S(Slim:3.8x65)]- side_l
+shelf_top -[TL<0 FL>38 S(Slim:3.8x65)]- side_r
+"""
+# Slats with long names dowelled along a rail: one part whose names are
+# wider than the page
+SLATS = "(rail:2x4 =1200)\n" + "".join(
+    f"(slat_with_a_long_name_{i:02d}:2x2 =300)\n"
+    f"rail -[RF<{i * 90:g} BT<0 D(:8x30)]- slat_with_a_long_name_{i:02d}\n"
+    for i in range(12)
+)
+
+# A post with a piece dowelled to each of its six faces
+SIX = """(c:2x4 =300)
+(up:2x4 =200)
+(dn:2x4 =200)
+(f:2x4 =200)
+(b:2x4 =200)
+(l:2x4 =200)
+(r:2x4 =200)
+c -[TF<0 DF<0 D(:8x30)]- up
+c -[DF<0 TF<0 D(:8x30)]- dn
+c -[FL<100 DF<0 D(:8x30)]- f
+c -[BL<100 DB<0 D(:8x30)]- b
+c -[LF<100 DF<0 D(:8x30)]- l
+c -[RF<100 DF<0 D(:8x30)]- r
+"""
+
+
+@lru_cache(maxsize=None)
+def _sheets(source: str):
+    # Drawing takes about a second a part, so each design is drawn once
+    assembly = Assembly.of(parse_dsl(source))
+    return assembly, [
+        part_sheet(assembly, group) for group in part_groups(assembly) if group.holes
+    ]
+
+
+@pytest.fixture(scope="module")
+def shelf():
+    return _sheets(SHELF.read_text())
+
+
+def _overlap(a, b) -> bool:
+    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
+
+
+def _crosses(rect, segment, margin: float = 1e-6) -> bool:
+    """Whether a segment passes through the inside of a rectangle."""
+    x0, y0, x1, y1 = (
+        rect[0] + margin,
+        rect[1] + margin,
+        rect[2] - margin,
+        rect[3] - margin,
+    )
+    (ax, ay), (bx, by) = segment
+    dx, dy = bx - ax, by - ay
+    start, end = 0.0, 1.0
+    for p, q in ((-dx, ax - x0), (dx, x1 - ax), (-dy, ay - y0), (dy, y1 - ay)):
+        if p == 0:
+            if q < 0:
+                return False
+        elif p < 0:
+            start = max(start, q / p)
+        else:
+            end = min(end, q / p)
+    return start <= end
+
+
+def _problems(sheet) -> list:
+    """Texts on each other or off the page, values on dimension lines,
+    crowded values."""
+    boxes = [box for _, box in sheet.texts]
+    segments = list(sheet.dimensions.lines)
+    for arrow in sheet.dimensions.arrows:
+        a, b, c = _arrow_points(*arrow)
+        segments += [(a, b), (b, c), (c, a)]
+    values = [label.box for label in sheet.dimensions.labels]
+    return (
+        [(a, b) for a, b in combinations(boxes, 2) if _overlap(a, b)]
+        + [box for box in boxes if box[0] < 0 or box[2] > PAGE_WIDTH]
+        + [(v, s) for v in values for s in segments if _crosses(v, s)]
+        + sheet.dimensions.crowded
+    )
+
+
+def test_title_names_the_pieces_lumber_length_and_holes_per_piece(shelf):
+    assembly, _ = shelf
+    groups = {group.pieces[0]: group for group in part_groups(assembly)}
+    assert part_title(assembly, groups["leg_1"]) == "leg_1   2x4   781   φ8 ↧15 ×10"
+    assert part_title(assembly, groups["shelf_1"]) == (
+        "shelf_1, shelf_2, shelf_3, shelf_4 ×4   2x4   300   φ8 ↧15 ×2"
+    )
+
+
+def test_through_holes_are_written_without_a_depth():
+    assembly = Assembly.of(parse_dsl(MIXED))
+    post = next(g for g in part_groups(assembly) if g.pieces[0] == "side_l")
+    # Blind dowel holes and the screws' through holes on one face
+    assert part_title(assembly, post) == (
+        "side_l, side_r ×2   2x4   800   φ2.5 ×2   φ8 ↧15 ×2"
+    )
+
+
+def test_a_title_wider_than_the_page_is_wrapped():
+    _, sheets = _sheets(SLATS)
+    slats = next(sheet for sheet in sheets if len(sheet.group.pieces) == 12)
+    assert _problems(slats) == []
+    written = " ".join(text for text, _ in slats.texts)
+    assert all(name in written for name in slats.group.pieces)
+
+
+def test_every_face_drilled_is_lettered_without_clashes():
+    _, sheets = _sheets(SIX)
+    post = sheets[0]
+    assert post.letters == {
+        "front": "A",
+        "back": "B",
+        "left": "C",
+        "right": "D",
+        "top": "E",
+        "down": "F",
+    }
+    assert _problems(post) == []
+
+
+def test_values_that_do_not_fit_point_to_the_pilot_holes_table():
+    # Holes 12.5mm apart along 2m leave no room for their values
+    holes = tuple(
+        LocalHole("front", (44.5, 38.0, 10 + 12.5 * i), 8.0, 15.0) for i in range(150)
+    )
+    group = PartGroup(pieces=("rail",), size=(89.0, 38.0, 2000.0), holes=holes)
+    sheet = part_sheet(Assembly.of(parse_dsl("(rail:2x4 =2000)")), group)
+    assert len(sheet.dimensions.crowded) == 1
+    assert "face A of rail" in sheet.dimensions.crowded[0]
+    assert "Pilot Holes table" in sheet.dimensions.crowded[0]
+
+
+def test_one_sheet_per_drilled_part(shelf):
+    _, sheets = shelf
+    assert [sheet.group.pieces[0] for sheet in sheets] == [
+        "leg_1",
+        "leg_2",
+        "leg_3",
+        "leg_4",
+        "apron_upper_front",
+        "apron_upper_back",
+        "apron_upper_left",
+        "apron_lower_front",
+        "top_1",
+        "shelf_1",
+    ]
+
+
+def test_leg_holes_are_dimensioned_from_the_reference_end(shelf):
+    _, sheets = shelf
+    texts = [label.text for label in sheets[0].dimensions.labels]
+    for value in ("172.2", "44.5", "497.5", "22.2", "781", "19", "70", "89"):
+        assert value in texts
+    assert sheets[0].letters == {"back": "A", "left": "B", "top": "C"}
+
+
+def test_thin_faces_are_drawn_tall_enough_for_their_values(shelf):
+    _, sheets = shelf
+    # leg_1's narrow face (38) is drawn 22 high; its wide face (89) fits
+    # at the scale along the length, which both share
+    narrow, wide = sheets[0].faces["left"], sheets[0].faces["back"]
+    assert narrow[3] - narrow[1] == pytest.approx(22.0)
+    scale = (wide[2] - wide[0]) / 781
+    assert wide[3] - wide[1] == pytest.approx(89 * scale)
+    assert narrow[2] - narrow[0] == pytest.approx(wide[2] - wide[0])
+
+
+def test_neighbours_name_the_faces_beside_each_face(shelf):
+    _, sheets = shelf
+    # Each letter is in the isometric and beside its own face. A is also at
+    # B's and C's bottom edges; B at A's top edge and beside C's left edge
+    words = [text for text, _ in sheets[0].texts]
+    assert words.count("A") == 4
+    assert words.count("B") == 4
+    assert words.count("C") == 2
+
+
+@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
+def test_part_drawings_are_clean(path):
+    _, sheets = _sheets(path.read_text())
+    for sheet in sheets:
+        assert _problems(sheet) == [], sheet.group.pieces[0]
+
+
+def test_mixed_holes_draw_cleanly():
+    _, sheets = _sheets(MIXED)
+    assert sheets
+    for sheet in sheets:
+        assert _problems(sheet) == [], sheet.group.pieces[0]
+
+
+def test_the_depth_symbol_is_drawn():
+    # A font without it would draw nothing
+    assert _text_size("↧", 0.0)[0] > 0
+
+
+def test_png_is_written(shelf):
+    _, sheets = shelf
+    assert sheets[-1].png(400).startswith(b"\x89PNG")
EOF
````

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/shell/test_dimensioning.py tests/shell/test_parts.py -q`
Expected: `2 errors` during collection: `ImportError: cannot import name 'chain_from_stops' from 'nichiyou_daiku.shell.dimensioning'` and `ModuleNotFoundError: No module named 'nichiyou_daiku.shell.parts'`

- [ ] **Step 3: Implement**

````bash
git apply <<'EOF'
diff --git a/src/nichiyou_daiku/shell/dimensioning.py b/src/nichiyou_daiku/shell/dimensioning.py
index e5a0fca..b3b15a7 100644
--- a/src/nichiyou_daiku/shell/dimensioning.py
+++ b/src/nichiyou_daiku/shell/dimensioning.py
@@ -124,6 +124,21 @@ def chain_for(
     return Chain(view, axis, side, stops, segments)
 
 
+def chain_from_stops(
+    view: str, axis: Axis, side: Side, stops: Iterable[float]
+) -> Chain:
+    """Chain dimensions through given stops, such as hole centres, between
+    the lowest and the highest; none of its stretches is a lumber size."""
+    ordered = sorted(stops)
+    merged = _stops(ordered[1:-1], ordered[0], ordered[-1])
+    segments = (
+        tuple(Segment(a, b, lumber=False) for a, b in zip(merged, merged[1:]))
+        if len(merged) > 2
+        else ()
+    )
+    return Chain(view, axis, side, merged, segments)
+
+
 def chains(assembly: Assembly) -> list[Chain]:
     """The drawing's dimension chains; none when the pieces are not all
     connected, since then the overall size means nothing.
diff --git a/src/nichiyou_daiku/shell/parts.py b/src/nichiyou_daiku/shell/parts.py
new file mode 100644
index 0000000..6b35ab0
--- /dev/null
+++ b/src/nichiyou_daiku/shell/parts.py
@@ -0,0 +1,380 @@
+"""Part drawings: one sheet per group of pieces made the same way, an
+isometric view with the drilled faces lettered and the reference end
+marked, then each drilled face seen from outside with its holes
+dimensioned from the reference end.
+
+Needs build123d, so ``nichiyou_daiku.shell`` does not import this module.
+"""
+
+import io
+import re
+import tempfile
+from collections import Counter
+from dataclasses import dataclass
+from pathlib import Path
+
+import cairosvg
+import numpy as np
+from build123d import (
+    Align,
+    Box,
+    Compound,
+    Cylinder,
+    Edge,
+    ExportSVG,
+    LineType,
+    Polygon,
+    Pos,
+    Rot,
+    Shape,
+    Unit,
+    scale,
+)
+from ezdxf.colors import RGB
+
+from nichiyou_daiku.core.assembly import Assembly
+from nichiyou_daiku.core.assembly.parts import (
+    PartGroup,
+    edge_neighbours,
+    face_letters,
+    face_point,
+    face_size,
+    view_direction,
+)
+from nichiyou_daiku.core.geometry import Face
+from nichiyou_daiku.core.placement import face_normal
+from nichiyou_daiku.shell.diagnostics import format_mm
+from nichiyou_daiku.shell.dimensioning import chain_from_stops
+from nichiyou_daiku.shell.drawing import (
+    _arrow_points,
+    _Dimensions,
+    _dimension,
+    _levels,
+    _line_height,
+    _text,
+    _text_size,
+    _View,
+)
+
+# Page mm, as wide as a step image
+PAGE_WIDTH = 280.0
+MARGIN = 6.0
+ISO_WIDTH = 70.0
+ISO_HEIGHT = 60.0
+LETTER_COLUMN = 16.0  # a face's letter and the letters of its neighbours
+MIN_FACE_HEIGHT = 22.0  # a thin face is drawn taller so its values fit
+MAX_SCALE = 0.8
+FACE_GAP = 10.0
+MARK = 3.5  # length of the reference end's triangle
+
+Rect = tuple[float, float, float, float]
+_ADVICE = "The report's Pilot Holes table lists the same holes"
+
+
+@dataclass
+class PartSheet:
+    """What one part drawing shows, in page mm, and its SVG."""
+
+    group: PartGroup
+    letters: dict[Face, str]
+    faces: dict[Face, Rect]
+    """Each drilled face's outline."""
+    texts: list[tuple[str, Rect]]
+    """Every word and number drawn, with its box."""
+    dimensions: _Dimensions
+    svg: str
+
+    def png(self, size: int) -> bytes:
+        buffer = io.BytesIO()
+        cairosvg.svg2png(
+            bytestring=self.svg.encode(),
+            write_to=buffer,
+            output_width=size,
+            background_color="white",
+        )
+        return buffer.getvalue()
+
+
+def part_title(assembly: Assembly, group: PartGroup) -> str:
+    """Pieces, count, lumber, length and holes per piece, e.g.
+    ``shelf_1, shelf_2 ×2   2x4   300   φ8 ↧15 ×2``."""
+    lumber = assembly.model.pieces[group.pieces[0]].type.value
+    kinds = Counter((hole.diameter, hole.depth) for hole in group.holes)
+    holes = [
+        f"φ{format_mm(diameter)}"
+        + ("" if depth is None else f" ↧{format_mm(depth)}")
+        + f" ×{n}"
+        # Blind holes first, through holes (no depth) last
+        for (diameter, depth), n in sorted(
+            kinds.items(),
+            key=lambda kind: (kind[0][0], kind[0][1] is None, kind[0][1] or 0),
+        )
+    ]
+    return "   ".join([group.name, lumber, format_mm(group.size[2]), *holes])
+
+
+def _title_lines(title: str) -> list[str]:
+    """The title in lines as wide as the page allows, broken after a comma
+    or between its fields."""
+    lines = [""]
+    for word in re.split(r"(?<=, )|(?<=   )", title):
+        wider = (
+            _text_size((lines[-1] + word).rstrip(), 0.0)[0] > PAGE_WIDTH - 2 * MARGIN
+        )
+        if lines[-1] and wider:
+            lines.append(word)
+        else:
+            lines[-1] += word
+    return [line.rstrip() for line in lines]
+
+
+def _solid(group: PartGroup) -> Compound:
+    """The piece in its own axes with its holes drilled."""
+    extent = np.array(group.size)
+    solid: Compound = Box(*extent, align=(Align.MIN, Align.MIN, Align.MIN))
+    for hole in group.holes:
+        normal = face_normal(hole.face)
+        axis = int(np.argmax(np.abs(normal)))
+        # A hole without a depth goes through
+        depth = hole.depth if hole.depth is not None else float(extent[axis])
+        centre = np.array(hole.point) - normal * depth / 2
+        turn = {0: Rot(0, 90, 0), 1: Rot(90, 0, 0), 2: Rot(0, 0, 0)}[axis]
+        cylinder = Cylinder(
+            hole.diameter / 2,
+            depth + 0.2,
+            align=(Align.CENTER, Align.CENTER, Align.CENTER),
+        )
+        solid = solid - Pos(*centre) * (turn * cylinder)
+    return solid
+
+
+class _Page:
+    """Shapes and texts in page mm, collected for the exporter."""
+
+    def __init__(self) -> None:
+        self.lines: list[Shape] = []
+        self.hidden: list[Shape] = []
+        self.thin: list[Shape] = []
+        self.fills: list[Shape] = []
+        self.texts: list[tuple[str, Rect]] = []
+
+    def text(self, content: str, x: float, y: float) -> None:
+        width, height = _text_size(content, 0.0)
+        self.fills.append(Pos(x, y) * _text(content, 0.0))
+        self.texts.append(
+            (content, (x - width / 2, y - height / 2, x + width / 2, y + height / 2))
+        )
+
+    def letter(self, content: str, x: float, y: float, hidden: bool = False) -> None:
+        ring = Pos(x, y) * Edge.make_circle(_line_height() * 0.9)
+        (self.hidden if hidden else self.thin).append(ring)
+        self.text(content, x, y)
+
+    def triangle(self, tip: np.ndarray, direction: np.ndarray) -> None:
+        d = direction / np.linalg.norm(direction)
+        side = np.array([-d[1], d[0]]) * MARK / 2
+        back = tip - d * MARK
+        self.fills.append(
+            Polygon(tuple(tip), tuple(back + side), tuple(back - side), align=None)
+        )
+
+
+def _isometric(
+    group: PartGroup, letters: dict[Face, str], page: _Page, top: float
+) -> None:
+    """The piece seen diagonally, its lettered faces named in a column at
+    its right with leaders, and the reference end marked."""
+    extent = np.array(group.size)
+    centre = extent / 2
+    direction = np.array(view_direction(list(letters)), dtype=float)
+    visible, hidden = _solid(group).project_to_viewport(
+        tuple(centre + direction * 2000), (0, 0, 1), look_at=tuple(centre)
+    )
+    box = Compound(children=list(visible) + list(hidden)).bounding_box()
+    factor = 0.85 * min(ISO_WIDTH / box.size.X, ISO_HEIGHT / box.size.Y)
+    origin = (
+        MARGIN + ISO_WIDTH / 2 - box.center().X * factor,
+        top - ISO_HEIGHT / 2 - box.center().Y * factor,
+    )
+    page.lines.append(Pos(*origin) * scale(Compound(children=list(visible)), factor))
+    if hidden:
+        page.hidden.append(
+            Pos(*origin) * scale(Compound(children=list(hidden)), factor)
+        )
+
+    # The same projection as project_to_viewport, for points of the piece
+    toward = direction / np.linalg.norm(direction)
+    up = np.array([0.0, 0.0, 1.0]) - toward[2] * toward
+    up /= np.linalg.norm(up)
+    right = np.cross(up, toward)
+
+    def on_page(point: np.ndarray) -> np.ndarray:
+        q = point - centre
+        return np.array([origin[0] + q @ right * factor, origin[1] + q @ up * factor])
+
+    column = MARGIN + ISO_WIDTH + 8
+    targets: list[tuple[Face, np.ndarray]] = sorted(
+        ((face, on_page(centre + face_normal(face) * extent / 2)) for face in letters),
+        key=lambda target: -target[1][1],
+    )
+    step = _line_height() * 2.6
+    first = top - ISO_HEIGHT / 2 + step * (len(targets) - 1) / 2
+    for i, (face, point) in enumerate(targets):
+        y = first - i * step
+        hidden_face = bool(face_normal(face) @ toward <= 0)
+        page.letter(letters[face], column, y, hidden_face)
+        leader = Edge.make_line((column - _line_height() * 0.9, y), tuple(point))
+        (page.hidden if hidden_face else page.thin).append(leader)
+    # The reference (down) end: a triangle pointing at it from beyond it
+    end = on_page(centre - np.array([0.0, 0.0, extent[2] / 2]))
+    beyond = on_page(centre - np.array([0.0, 0.0, extent[2] / 2 + 60 / factor]))
+    # Its tip stops short of the end so it does not cover the outline
+    toward_end = (end - beyond) / np.linalg.norm(end - beyond)
+    page.triangle(end - toward_end * 3.0, toward_end)
+
+
+def _mark_height(stops: list[float], bottom: float, top: float) -> float:
+    """Where the reference end's triangle goes on a face's left edge: the
+    middle, unless an extension line is there; then the widest gap."""
+    middle = (bottom + top) / 2
+    if all(abs(middle - stop) > MARK for stop in stops):
+        return middle
+    ordered = sorted(stops)
+    a, b = max(zip(ordered, ordered[1:]), key=lambda gap: gap[1] - gap[0])
+    return (a + b) / 2
+
+
+def _face_view(
+    group: PartGroup,
+    face: Face,
+    letters: dict[Face, str],
+    page: _Page,
+    dimensions: _Dimensions,
+    bottom: float,
+) -> Rect:
+    """Draw one drilled face with its lower edge at ``bottom``; return its
+    outline."""
+    width, height = face_size(face, group.size)
+    left = MARGIN + LETTER_COLUMN + _levels("left").depth
+    along = min((PAGE_WIDTH - MARGIN - left) / width, MAX_SCALE)
+    across = max(along, MIN_FACE_HEIGHT / height)
+    rect = (left, bottom, left + width * along, bottom + height * across)
+    corners = [
+        (rect[0], rect[1]),
+        (rect[2], rect[1]),
+        (rect[2], rect[3]),
+        (rect[0], rect[3]),
+    ]
+    page.lines += [
+        Edge.make_line(a, b) for a, b in zip(corners, corners[1:] + corners[:1])
+    ]
+
+    us, vs = [0.0, width], [0.0, height]
+    for hole in group.holes:
+        if hole.face != face:
+            continue
+        u, v = face_point(face, hole.point, group.size)
+        us.append(u)
+        vs.append(v)
+        radius = max(1.0, hole.diameter / 2 * min(along, across))
+        page.lines.append(
+            Pos(left + u * along, bottom + v * across) * Edge.make_circle(radius)
+        )
+    where = f"face {letters[face]} of {group.pieces[0]}"
+    # "from -y" puts a chain's x along the page and its z up the page
+    _dimension(
+        chain_from_stops("from -y", "x", "below", us),
+        _View("from -y", (left, bottom), along, rect, [], []),
+        dimensions,
+        where,
+        _ADVICE,
+    )
+    _dimension(
+        chain_from_stops("from -y", "z", "left", vs),
+        _View("from -y", (left, bottom), across, rect, [], []),
+        dimensions,
+        where,
+        _ADVICE,
+    )
+
+    column = MARGIN + LETTER_COLUMN / 2
+    middle = (rect[1] + rect[3]) / 2
+    page.letter(letters[face], column, middle)
+    neighbours = edge_neighbours(face)
+    for edge, y in (("top", rect[3]), ("bottom", rect[1])):
+        if neighbours[edge] in letters:
+            page.text(letters[neighbours[edge]], column, y)
+    if face in ("top", "down"):
+        # An end turns freely about the length, so its sides are named too
+        offset = _line_height() * 2
+        for edge, x in (("left", column - offset), ("right", column + offset)):
+            if neighbours[edge] in letters:
+                page.text(letters[neighbours[edge]], x, middle)
+    else:
+        y = _mark_height([bottom + v * across for v in vs], rect[1], rect[3])
+        page.triangle(np.array([left - 0.6, y]), np.array([1.0, 0.0]))
+    return rect
+
+
+def part_sheet(assembly: Assembly, group: PartGroup) -> PartSheet:
+    """The drawing of one part: the title, the isometric view and every
+    drilled face, top to bottom."""
+    letters = face_letters(group.holes, group.size)
+    drilled: list[Face] = [
+        face for face in letters if any(h.face == face for h in group.holes)
+    ]
+    page = _Page()
+    dimensions = _Dimensions()
+
+    # Faces from the bottom of the page up, the first lettered at the top
+    below = _levels("below").depth
+    y = MARGIN + below
+    faces: dict[Face, Rect] = {}
+    for face in reversed(drilled):
+        faces[face] = _face_view(group, face, letters, page, dimensions, y)
+        y = faces[face][3] + _line_height() + FACE_GAP + below
+    top = y - below + ISO_HEIGHT
+    _isometric(group, letters, page, top)
+    lines = _title_lines(part_title(assembly, group))
+    spacing = _line_height() * 1.6
+    for i, line in enumerate(reversed(lines)):
+        width, _ = _text_size(line, 0.0)
+        page.text(line, MARGIN + width / 2, top + 8 + i * spacing)
+    height = top + 14 + (len(lines) - 1) * spacing
+
+    exporter = ExportSVG(unit=Unit.MM)
+    exporter.add_layer("Piece", line_weight=0.35)
+    exporter.add_layer(
+        "Hidden",
+        line_color=RGB(120, 120, 120),
+        line_weight=0.15,
+        line_type=LineType.ISO_DASH,
+    )
+    exporter.add_layer("Thin", line_weight=0.13)
+    exporter.add_layer(
+        "Text", fill_color=RGB(0, 0, 0), line_color=RGB(0, 0, 0), line_weight=0.01
+    )
+    border = [(0.0, 0.0), (PAGE_WIDTH, 0.0), (PAGE_WIDTH, height), (0.0, height)]
+    page.thin += [Edge.make_line(a, b) for a, b in zip(border, border[1:] + border[:1])]
+    page.thin += [Edge.make_line(a, b) for a, b in dimensions.lines]
+    for shapes, layer in (
+        (page.lines, "Piece"),
+        (page.hidden, "Hidden"),
+        (page.thin, "Thin"),
+    ):
+        if shapes:
+            exporter.add_shape(shapes, layer=layer)
+    labels = [
+        Pos(*label.centre) * _text(label.text, label.rotation)
+        for label in dimensions.labels
+    ]
+    arrows = [
+        Polygon(*_arrow_points(*arrow), align=None) for arrow in dimensions.arrows
+    ]
+    exporter.add_shape(page.fills + labels + arrows, layer="Text")
+    with tempfile.TemporaryDirectory() as directory:
+        path = Path(directory) / "part.svg"
+        exporter.write(str(path))
+        svg = path.read_text()
+    texts = page.texts + [(label.text, label.box) for label in dimensions.labels]
+    return PartSheet(group, letters, faces, texts, dimensions, svg)
EOF
````

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/shell/test_dimensioning.py tests/shell/test_parts.py -q`
Expected: `37 passed` (about 40s; each design's sheets are drawn once and cached)

- [ ] **Step 5: Check**

Check that thin faces are stretched for a reason: temporarily change `across = max(along, MIN_FACE_HEIGHT / height)` to `across = along` in `_face_view`, run `uv run pytest tests/shell/test_parts.py -q -k thin`, expect `1 failed`, and restore it. Then draw the shelf's parts and look at them:

```bash
uv run python - <<'PY'
from pathlib import Path
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.assembly.parts import part_groups
from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.shell.parts import part_sheet
a = Assembly.of(parse_dsl(Path("skills/design/examples/two-tier-shelf.nd").read_text()))
out = Path("/tmp/shelf-parts"); out.mkdir(exist_ok=True)
for i, group in enumerate([g for g in part_groups(a) if g.holes], 1):
    sheet = part_sheet(a, group)
    (out / f"part-{i:02d}.png").write_bytes(sheet.png(1600))
    print(i, group.name, sheet.letters, sheet.dimensions.crowded)
PY
```

Expected: 10 parts in about 10s, none crowded. Read `part-01.png` (leg_1). The title is `leg_1   2x4   781   φ8 ↧15 ×10`. The isometric letters A (back), B (left) and C (top) in a column at its right, with ▲ below the down end. Face A has 172.2 / 44.5 / 497.5 / 44.5 / 22.2 and 781 below, 19 / 70 and 89 at its left, ▶ on its left edge. Face B is drawn 22mm high. Then read `part-07.png` (the four side aprons ×4: both ends, no letters beside them).

- [ ] **Step 6: Commit**

```bash
make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log
[ $rc -eq 0 ] && git add src/nichiyou_daiku/shell/dimensioning.py src/nichiyou_daiku/shell/parts.py tests/shell/test_dimensioning.py tests/shell/test_parts.py && git commit -m "feat: Draw each part with its holes dimensioned

An isometric view letters the drilled faces and marks the reference
end; each drilled face, seen from outside with that end on the left,
is dimensioned through its hole centres."
```

---

### Task 3: Parts in the instructions and the `steps` command

**Files:**
- Modify: `src/nichiyou_daiku/shell/instructions.py` (Parts section, `part_image_name`, `Instructions.drawings`, part images in `write_instructions`)
- Modify: `src/nichiyou_daiku/cli/commands/steps.py` (help and the success message)
- Modify: `docs/dsl-specification.md`, `docs/api-specification.md`, `skills/design/SKILL.md`, `README.md`
- Test: `tests/shell/test_instructions.py`, `tests/cli/commands/test_steps.py`

**Interfaces:**
- Consumes: Task 1's `part_groups`, `PartGroup` (`.name`, `.holes`, `.size`, `.pieces`); Task 2's `part_sheet`, `PartSheet.png(size)`, `PartSheet.dimensions.crowded`.
- Produces: `part_image_name(number: int, count: int) -> str` (`part-01.png`; `part-003.png` when there are 100 or more); `Instructions(files, drawings, declared, crowded, hint)` where `files` is `steps.md`, then the part drawings, then the step images, and `drawings` is how many part drawings there are; the CLI message `Successfully wrote steps.md, 2 part drawings and 1 step image to <directory>` (without drawings, as before: `Successfully wrote steps.md and 1 step image to <directory>`).

- [ ] **Step 1: Write the failing tests**

````bash
git apply <<'EOF'
diff --git a/tests/cli/commands/test_steps.py b/tests/cli/commands/test_steps.py
index 3396b40..6830eef 100644
--- a/tests/cli/commands/test_steps.py
+++ b/tests/cli/commands/test_steps.py
@@ -10,6 +10,8 @@ from nichiyou_daiku.cli.dsl_cli import cli  # noqa: E402
 
 CORNER = "(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n"
 CORNER_STEPS = CORNER + 'steps {\n  "Corner": a, b\n}\n'
+# The corner joined with dowels: both pieces drilled, each its own part
+DOWELLED = CORNER.replace("BD<0]", "BD<0 D(:8x30)]")
 # A third piece across the far end of b: two steps without a steps block
 THREE = CORNER + "(c:2x4 =400)\nb -[TF<0 BD<0]- c\n"
 
@@ -37,6 +39,25 @@ def test_steps_writes_the_page_and_images_next_to_the_input(runner, corner):
     assert result.stdout == ""
 
 
+def test_steps_draws_the_drilled_parts(runner, tmp_path):
+    path = tmp_path / "corner.nd"
+    path.write_text(DOWELLED)
+    result = runner.invoke(cli, ["steps", str(path)])
+    assert result.exit_code == 0, result.output
+    directory = tmp_path / "corner-steps"
+    assert sorted(p.name for p in directory.iterdir()) == [
+        "part-01.png",
+        "part-02.png",
+        "step-01.png",
+        "steps.md",
+    ]
+    assert _png_width((directory / "part-01.png").read_bytes()) == 1600
+    assert (
+        "Successfully wrote steps.md, 2 part drawings and 1 step image to"
+        in result.stderr
+    )
+
+
 def test_steps_takes_a_directory_and_an_image_width(runner, corner, tmp_path):
     out = tmp_path / "instructions"
     result = runner.invoke(cli, ["steps", str(corner), "-o", str(out), "--size", "800"])
diff --git a/tests/shell/test_instructions.py b/tests/shell/test_instructions.py
index d55a8ac..ff3f582 100644
--- a/tests/shell/test_instructions.py
+++ b/tests/shell/test_instructions.py
@@ -14,6 +14,7 @@ from nichiyou_daiku.shell.build123d_export import assembly_to_build123d  # noqa:
 from nichiyou_daiku.shell.drawing import _arrow_points  # noqa: E402
 from nichiyou_daiku.shell.instructions import (  # noqa: E402
     image_name,
+    part_image_name,
     step_image,
     steps_markdown,
     write_instructions,
@@ -23,6 +24,8 @@ SHELF = (
     Path(__file__).parents[2] / "skills" / "design" / "examples" / "two-tier-shelf.nd"
 ).read_text()
 CORNER = "(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n"
+# The corner joined with dowels: both pieces drilled, each its own part
+DOWELLED = "(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0 D(:8x30)]- b\n"
 # A third piece across the far end of b: two steps without a steps block
 THREE = CORNER + "(c:2x4 =400)\nb -[TF<0 BD<0]- c\n"
 # 39 slats 12.5mm apart up a 2m post, all in one step
@@ -180,6 +183,29 @@ def test_steps_page_lists_each_step_with_its_pieces_and_fasteners(shelf):
     assert "No steps block" not in page
 
 
+def test_steps_page_lists_the_parts_before_the_steps(shelf):
+    assembly, plan, _ = shelf
+    page = steps_markdown(assembly, plan, "two-tier-shelf")
+    parts = page.split("## Step 1", 1)[0]
+    assert "## Parts\n" in parts
+    assert "| Pieces | Lumber | Length (mm) | Count | Drawing |" in parts
+    assert "| leg_1 | 2x4 | 781 | 1 | [part-01.png](part-01.png) |" in parts
+    assert (
+        "| shelf_1, shelf_2, shelf_3, shelf_4 | 2x4 | 300 | 4 "
+        "| [part-10.png](part-10.png) |"
+    ) in parts
+    assert (
+        "### shelf_1, shelf_2, shelf_3, shelf_4 ×4\n\n![Part 10](part-10.png)" in parts
+    )
+
+
+def test_parts_without_holes_are_listed_without_a_drawing():
+    assembly = Assembly.of(parse_dsl(CORNER))
+    page = steps_markdown(assembly, plan_steps(assembly), "corner")
+    assert "| a, b | 2x4 | 400 | 2 |  |" in page
+    assert "part-" not in page
+
+
 def test_steps_page_without_steps_says_how_to_group_them():
     assembly = Assembly.of(parse_dsl(THREE))
     page = steps_markdown(assembly, plan_steps(assembly), "three")
@@ -206,6 +232,31 @@ def test_write_instructions_writes_the_page_and_one_image_per_step(tmp_path):
     assert result.crowded == []
 
 
+def test_write_instructions_draws_each_drilled_part(tmp_path):
+    assembly = Assembly.of(parse_dsl(DOWELLED))
+    part = assembly_to_build123d(assembly, fillet_radius=0)
+    result = write_instructions(assembly, part, tmp_path, "corner", size=400)
+    assert [path.name for path in result.files] == [
+        "steps.md",
+        "part-01.png",
+        "part-02.png",
+        "step-01.png",
+    ]
+    assert result.drawings == 2
+    assert (tmp_path / "part-01.png").read_bytes().startswith(b"\x89PNG")
+
+
+def test_rewriting_removes_drawings_of_parts_that_are_gone(tmp_path):
+    for source in (DOWELLED, CORNER):
+        assembly = Assembly.of(parse_dsl(source))
+        part = assembly_to_build123d(assembly, fillet_radius=0)
+        write_instructions(assembly, part, tmp_path, "design", size=400)
+    assert sorted(path.name for path in tmp_path.iterdir()) == [
+        "step-01.png",
+        "steps.md",
+    ]
+
+
 def test_unconnected_pieces_get_a_step_each(tmp_path):
     # Two loose posts: each step draws its own part
     assembly = Assembly.of(parse_dsl("(a:2x4 =400)\n(b:2x4 =400)\n"))
@@ -223,6 +274,7 @@ def test_image_names_are_wide_enough_for_every_step(shelf):
     _, plan, _ = shelf
     assert image_name(plan.steps[2], 5) == "step-03.png"
     assert image_name(plan.steps[2], 120) == "step-003.png"
+    assert part_image_name(3, 120) == "part-003.png"
 
 
 def test_crowded_values_say_to_split_the_step():
EOF
````

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/shell/test_instructions.py -q`
Expected: collection error, `ImportError: cannot import name 'part_image_name' from 'nichiyou_daiku.shell.instructions'`

Run: `uv run pytest tests/cli/commands/test_steps.py -q`
Expected: `1 failed, 8 passed` (`test_steps_draws_the_drilled_parts`: no part images)

- [ ] **Step 3: Implement**

The patch also updates the DSL and API specifications (the API one gains a doctest for `part_groups`), the design skill and the README.

````bash
git apply <<'EOF'
diff --git a/README.md b/README.md
index c880516..4e3cf58 100644
--- a/README.md
+++ b/README.md
@@ -27,7 +27,7 @@ nichiyou-daiku report corner.nd -o report.md # bill of materials, shopping list,
 nichiyou-daiku export corner.nd -f step      # 3D model (needs the viz extra)
 nichiyou-daiku drawing corner.nd             # technical drawing PDF with dimensions (needs the viz extra)
 nichiyou-daiku render corner.nd              # check image PNG, four labelled views (needs the viz extra)
-nichiyou-daiku steps corner.nd               # assembly steps: Markdown and one image per step (needs the viz extra)
+nichiyou-daiku steps corner.nd               # assembly steps: Markdown, part drawings and step images (needs the viz extra)
 ```
 
 See [`examples/nd_files/`](examples/nd_files/) for complete designs, such as a table written with variables ([`simple_table_parametric.nd`](examples/nd_files/simple_table_parametric.nd)) and one whose apron length is solved from the legs ([`simple_table_unknowns.nd`](examples/nd_files/simple_table_unknowns.nd)).
diff --git a/docs/api-specification.md b/docs/api-specification.md
index e3d347e..71c51f0 100644
--- a/docs/api-specification.md
+++ b/docs/api-specification.md
@@ -829,10 +829,28 @@ Pass the `assembly` that `part` was built from to dimension the drawing (overall
 
 `nichiyou_daiku.core.assembly.steps.plan_steps(assembly)` plans the steps without build123d: a `StepPlan` whose `declared` says whether the model has a `steps` block and whose `steps` are `PlannedStep`s with the `pieces` each adds, the `connections` it makes, its `kind` (`first`, `attach`, `sub-assembly` or `join`), the pieces `shown` in its image and the `view` (world axis and side) its dimension view looks from.
 
+`nichiyou_daiku.core.assembly.parts.part_groups(assembly)` groups the pieces made the same way (see `steps` in the [DSL Specification](./dsl-specification.md)), in declaration order. A `PartGroup` has its `pieces`, `size` (width, thickness, length), `holes` and `name`; a `LocalHole` has the `face` it is drilled into, its centre `point` in the piece's own axes (x across the width, y across the thickness, z along the length from the down end), `diameter` and `depth` (None when drilled through).
+
+```python
+>>> from nichiyou_daiku.core.assembly.parts import part_groups
+>>> posts = Assembly.of(parse_dsl("""
+... (side_l:2x4 =800)
+... (side_r:2x4 =800)
+... (shelf:2x4 =600)
+... shelf -[DL<0 BL<100 S(Slim:3.8x65)]- side_l
+... shelf -[TL<0 FL<100 S(Slim:3.8x65)]- side_r
+... """))
+>>> [group.name for group in part_groups(posts)]
+['side_l, side_r ×2', 'shelf']
+>>> part_groups(posts)[0].holes[0]
+LocalHole(face='back', point=(22.25, 0.0, 119.0), diameter=2.5, depth=None)
+```
+
 Requires `build123d` package to draw them.
 
 ```python
 from nichiyou_daiku.shell.instructions import write_instructions
+from nichiyou_daiku.shell.parts import part_sheet
 
 def write_instructions(
     assembly: Assembly,
@@ -841,10 +859,14 @@ def write_instructions(
     title: str,
     size: int = 1600,
 ) -> Instructions:
-    """Write steps.md and one PNG per step (size px wide) into directory."""
+    """Write steps.md, one PNG per drilled part and one per step (size px
+    wide) into directory."""
+
+def part_sheet(assembly: Assembly, group: PartGroup) -> PartSheet:
+    """The drawing of one part: its svg, and png(size) for a PNG."""
 ```
 
-`part` is the `assembly_to_build123d` result for `assembly`. The returned `Instructions` has the written `files` (`steps.md` first), `declared` as above, and `crowded`: a message for each step whose dimension values do not fit. See `steps` in the [DSL Specification](./dsl-specification.md).
+`part` is the `assembly_to_build123d` result for `assembly`. The returned `Instructions` has the written `files` (`steps.md` first, then the part drawings and the step images), `drawings`: how many of them are part drawings, `declared` as above, and `crowded`: a message for each part or step whose dimension values do not fit. See `steps` in the [DSL Specification](./dsl-specification.md).
 
 ## Complete Examples
 
diff --git a/docs/dsl-specification.md b/docs/dsl-specification.md
index 4cff557..33ad979 100644
--- a/docs/dsl-specification.md
+++ b/docs/dsl-specification.md
@@ -712,13 +712,15 @@ Draws one square PNG (default 1400px, at least 400px) for checking a design by e
 ### Assembly Steps (requires build123d)
 
 ```bash
-nichiyou-daiku steps shelf.nd                    # shelf-steps/steps.md and step-01.png, ...
+nichiyou-daiku steps shelf.nd                    # shelf-steps/steps.md, part-01.png, ... and step-01.png, ...
 nichiyou-daiku steps shelf.nd -o instructions --size 1200
 ```
 
-Writes `steps.md` and one PNG per step (default 1600px wide) into a directory, by default `<input>-steps`. The steps come from the file's `steps` block (see [Assembly Steps](#assembly-steps)). The page has no prose: per step, its heading (`Step 2 - Right frame (sub-assembly)`, with `(join)` for a step that joins parts), its image, the pieces it adds with their lumber and length, and its fasteners counted as in the report's shopping list.
+Writes `steps.md`, one PNG per drilled part and one per step (default 1600px wide) into a directory, by default `<input>-steps`. The steps come from the file's `steps` block (see [Assembly Steps](#assembly-steps)). The page has no prose: first the parts, then per step its heading (`Step 2 - Right frame (sub-assembly)`, with `(join)` for a step that joins parts), its image, the pieces it adds with their lumber and length, and its fasteners counted as in the report's shopping list.
 
-Each image shows the part the step leaves from +x +y +z, the pieces built before in grey and the step's pieces in black with their IDs (their hidden edges dashed), beside an orthographic view dimensioning where the step's pieces go: chain dimensions as in `drawing`, stopping at both ends of the step's pieces and of the pieces they are joined to, with the part's overall size. That view looks across the edges the step's connections are measured along, along the axis where the step's pieces hide each other least, from the side where the rest of the part hides them least. When values do not fit beside their chain, the command warns and suggests splitting the step. Without a `steps` block it says how to add one. `--fillet-radius` is that of `export`.
+The parts are listed in declaration order with their lumber, length and count, each drilled one linked to its drawing below the table (`part-01.png`, ...). Pieces made the same way are one part (`shelf_1, shelf_2, shelf_3, shelf_4 ×4`): the same lumber and length, and holes that match within 0.05mm once the board is turned onto itself (a half turn about its length, width or thickness). A mirrored piece, such as the left leg of the right one, is a different part. A drawing's title gives the pieces, the lumber, the length to cut and the holes of one piece by kind (`φ8 ↧15 ×10`: diameter, depth and count; a hole drilled through has no depth). Under it the piece is drawn from the diagonal where most of its drilled faces show, those faces lettered A, B, ... in the order front, back, left, right, top, down (dashed when hidden), with a triangle beyond the down end, the reference end. Then each drilled face is seen from outside, a long face with the reference end to the left, dimensioned through the hole centres from the reference end and from its lower edge. Its letter is at its left, and at the height of each edge the letter of the drilled face across it (beside an end face, on all four sides). A thin face is drawn taller so that its values fit; the values are true sizes. When the only drilled faces are the two ends and a half turn about the length would change their holes, the front is lettered too, to tell how the ends turn to each other.
+
+Each step image shows the part the step leaves from +x +y +z, the pieces built before in grey and the step's pieces in black with their IDs (their hidden edges dashed), beside an orthographic view dimensioning where the step's pieces go: chain dimensions as in `drawing`, stopping at both ends of the step's pieces and of the pieces they are joined to, with the part's overall size. That view looks across the edges the step's connections are measured along, along the axis where the step's pieces hide each other least, from the side where the rest of the part hides them least. When values do not fit beside their chain, the command warns and suggests splitting the step (for a part, it points to the report's Pilot Holes table, which lists the same holes). Without a `steps` block it says how to add one. `--fillet-radius` is that of `export`.
 
 ## Grammar (EBNF)
 
diff --git a/skills/design/SKILL.md b/skills/design/SKILL.md
index e956086..2fc074f 100644
--- a/skills/design/SKILL.md
+++ b/skills/design/SKILL.md
@@ -47,7 +47,7 @@ Run `nichiyou-daiku render <name>.nd -o <name>.png` and read the PNG. It shows t
 ## 7. Output files on request
 
 - Drawing: `nichiyou-daiku drawing <name>.nd -o <name>.pdf`
-- Assembly instructions: `nichiyou-daiku steps <name>.nd` (a `<name>-steps` directory with `steps.md` and one image per step); read a few of the images to check the order and the dimensions
+- Assembly instructions: `nichiyou-daiku steps <name>.nd` (a `<name>-steps` directory with `steps.md`, a drawing of each drilled part and one image per step); read a few of the images to check the order, the holes and the dimensions
 - 3D model: `nichiyou-daiku export <name>.nd -f step` (or `-f stl`)
 
 ## 8. Report
diff --git a/src/nichiyou_daiku/cli/commands/steps.py b/src/nichiyou_daiku/cli/commands/steps.py
index 502f7c4..01699b1 100644
--- a/src/nichiyou_daiku/cli/commands/steps.py
+++ b/src/nichiyou_daiku/cli/commands/steps.py
@@ -25,7 +25,7 @@ from nichiyou_daiku.cli.utils import (
     "--output",
     type=click.Path(path_type=Path),
     help=(
-        "Directory for steps.md and the step images "
+        "Directory for steps.md, the part drawings and the step images "
         "(default: <input>-steps, required for stdin)."
     ),
 )
@@ -34,7 +34,7 @@ from nichiyou_daiku.cli.utils import (
     type=click.IntRange(min=400),
     default=1600,
     show_default=True,
-    help="Width of each step image in pixels.",
+    help="Width of each image in pixels.",
 )
 @click.option(
     "--fillet-radius",
@@ -50,13 +50,16 @@ def steps(
     size: int,
     fillet_radius: float,
 ) -> None:
-    """Write assembly instructions: steps.md and one image per step.
+    """Write assembly instructions: steps.md, a drawing of each drilled
+    part and one image per step.
 
     INPUT_FILE: Path to .nd file or '-' for stdin
 
-    The steps come from the file's steps block; without one, each step adds
-    one piece. Each image shows what is built so far in grey and the step's
-    pieces in black, beside a view dimensioning where they go.
+    The parts come first: what to cut, and where to drill each face, from
+    the reference end marked with a triangle. The steps come from the
+    file's steps block; without one, each step adds one piece. Each step
+    image shows what is built so far in grey and the step's pieces in
+    black, beside a view dimensioning where they go.
 
     \b
     Examples:
@@ -91,8 +94,15 @@ def steps(
         echo.info(result.hint)
     for message in result.crowded:
         echo.info(click.style(f"Warning: {message}", fg="yellow"))
-    images = len(result.files) - 1
+    images = len(result.files) - 1 - result.drawings
+    written = ["steps.md"]
+    if result.drawings:
+        written.append(_count(result.drawings, "part drawing"))
+    written.append(_count(images, "step image"))
     echo.info(
-        f"Successfully wrote steps.md and {images} step "
-        f"image{'' if images == 1 else 's'} to {directory}"
+        f"Successfully wrote {', '.join(written[:-1])} and {written[-1]} to {directory}"
     )
+
+
+def _count(n: int, thing: str) -> str:
+    return f"{n} {thing}{'' if n == 1 else 's'}"
diff --git a/src/nichiyou_daiku/shell/instructions.py b/src/nichiyou_daiku/shell/instructions.py
index a833568..bd8ac1d 100644
--- a/src/nichiyou_daiku/shell/instructions.py
+++ b/src/nichiyou_daiku/shell/instructions.py
@@ -37,6 +37,7 @@ from OCP.TopExp import TopExp_Explorer  # pyright: ignore[reportAttributeAccessI
 from OCP.TopoDS import TopoDS_Shape  # pyright: ignore[reportAttributeAccessIssue]
 
 from nichiyou_daiku.core.assembly import Assembly
+from nichiyou_daiku.core.assembly.parts import PartGroup, part_groups
 from nichiyou_daiku.core.assembly.steps import PlannedStep, StepPlan, plan_steps
 from nichiyou_daiku.shell.diagnostics import format_mm
 from nichiyou_daiku.shell.dimensioning import Axis, chain_for
@@ -49,6 +50,7 @@ from nichiyou_daiku.shell.drawing import (
     _text_size,
     _View,
 )
+from nichiyou_daiku.shell.parts import part_sheet
 from nichiyou_daiku.shell.resources import _hardware
 from nichiyou_daiku.shell.views import VIEWS, View, axis_view, label_at, project
 
@@ -63,7 +65,7 @@ ISO_FILL = 0.9
 _ISOMETRIC = next(view for view in VIEWS if view.caption == "from +x +y +z")
 _KIND_MARKS = {"sub-assembly": " (sub-assembly)", "join": " (join)"}
 _SPLIT_ADVICE = "Split the step into steps that add fewer pieces"
-_IMAGE = re.compile(r"step-\d+\.png")
+_IMAGE = re.compile(r"(step|part)-\d+\.png")
 
 Rect = tuple[float, float, float, float]
 
@@ -330,6 +332,49 @@ def image_name(step: PlannedStep, count: int) -> str:
     return f"step-{step.number:0{max(2, len(str(count)))}d}.png"
 
 
+def part_image_name(number: int, count: int) -> str:
+    """part-01.png, ...; wide enough for every drawn part."""
+    return f"part-{number:0{max(2, len(str(count)))}d}.png"
+
+
+def _drawn(groups: list[PartGroup]) -> list[PartGroup]:
+    # A part without holes is only cut to length: the table is enough
+    return [group for group in groups if group.holes]
+
+
+def _parts(assembly: Assembly) -> list[str]:
+    """Every part's lumber, length and count, then the drawings of the
+    drilled ones."""
+    groups = part_groups(assembly)
+    drawn = _drawn(groups)
+    images = {
+        group.pieces: part_image_name(number, len(drawn))
+        for number, group in enumerate(drawn, 1)
+    }
+    lines = [
+        "## Parts",
+        "",
+        "| Pieces | Lumber | Length (mm) | Count | Drawing |",
+        "|--------|--------|-------------|-------|---------|",
+    ]
+    for group in groups:
+        image = images.get(group.pieces)
+        lumber = assembly.model.pieces[group.pieces[0]].type.value
+        lines.append(
+            f"| {', '.join(group.pieces)} | {lumber} | {format_mm(group.size[2])} "
+            f"| {len(group.pieces)} | {f'[{image}]({image})' if image else ''} |"
+        )
+    lines.append("")
+    for number, group in enumerate(drawn, 1):
+        lines += [
+            f"### {group.name}",
+            "",
+            f"![Part {number}]({images[group.pieces]})",
+            "",
+        ]
+    return lines
+
+
 def grouping_hint(plan: StepPlan) -> str | None:
     """How to group the steps, with the design's own first pieces; None when
     a steps block is declared or there is one step only, nothing to group."""
@@ -343,12 +388,13 @@ def grouping_hint(plan: StepPlan) -> str | None:
 
 
 def steps_markdown(assembly: Assembly, plan: StepPlan, title: str) -> str:
-    """The instructions page: per step, its heading, image, pieces and
-    fasteners. No prose: the images and numbers tell how."""
+    """The instructions page: the parts to make, then per step its heading,
+    image, pieces and fasteners. No prose: the images and numbers tell how."""
     lines = [f"# {title}: assembly steps", ""]
     hint = grouping_hint(plan)
     if hint:
         lines += [hint, ""]
+    lines += _parts(assembly)
     for step in plan.steps:
         lines += [
             f"## {_heading(step)}",
@@ -375,6 +421,8 @@ class Instructions:
     """The written files and what the user should hear about them."""
 
     files: list[Path]
+    drawings: int
+    """How many of ``files`` are part drawings."""
     declared: bool
     crowded: list[str]
     hint: str | None
@@ -384,12 +432,19 @@ class Instructions:
 def write_instructions(
     assembly: Assembly, part: Compound, directory: Path, title: str, size: int = 1600
 ) -> Instructions:
-    """Write ``steps.md`` and one PNG per step (``size`` px wide) into
-    ``directory``, creating it if needed. Step images left there by an
-    earlier run with more steps are removed."""
+    """Write ``steps.md``, one PNG per drilled part and one per step
+    (``size`` px wide) into ``directory``, creating it if needed. Images
+    left there by an earlier run with more parts or steps are removed."""
     plan = plan_steps(assembly)
+    drawn = _drawn(part_groups(assembly))
     directory.mkdir(parents=True, exist_ok=True)
     files, crowded = [], []
+    for number, group in enumerate(drawn, 1):
+        sheet = part_sheet(assembly, group)
+        path = directory / part_image_name(number, len(drawn))
+        path.write_bytes(sheet.png(size))
+        files.append(path)
+        crowded += sheet.dimensions.crowded
     for step in plan.steps:
         image = step_image(assembly, part, step)
         path = directory / image_name(step, len(plan.steps))
@@ -398,8 +453,10 @@ def write_instructions(
         crowded += image.dimensions.crowded
     page = directory / "steps.md"
     page.write_text(steps_markdown(assembly, plan, title))
-    # An old image would pass for a step of this design
+    # An old image would pass for a part or a step of this design
     for old in directory.iterdir():
         if _IMAGE.fullmatch(old.name) and old not in files:
             old.unlink()
-    return Instructions([page, *files], plan.declared, crowded, grouping_hint(plan))
+    return Instructions(
+        [page, *files], len(drawn), plan.declared, crowded, grouping_hint(plan)
+    )
EOF
````

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/shell/test_instructions.py tests/cli/commands/test_steps.py tests/test_docs.py -q`
Expected: `73 passed`

- [ ] **Step 5: Check**

Check that a part without holes gets no drawing: temporarily change `_drawn` to `return list(groups)`, run `uv run pytest tests/shell/test_instructions.py -q -k without_a_drawing`, expect `1 failed`, and restore it. Then write the shelf's instructions with the command:

```bash
uv run nichiyou-daiku steps skills/design/examples/two-tier-shelf.nd -o /tmp/shelf-steps
```

Expected: `Successfully wrote steps.md, 10 part drawings and 5 step images to /tmp/shelf-steps` in about 25s. In `steps.md` the Parts table comes before `## Step 1`, with `| shelf_1, shelf_2, shelf_3, shelf_4 | 2x4 | 300 | 4 | [part-10.png](part-10.png) |`, then the headings and images. Read `part-01.png`; it is the same as in Task 2.

- [ ] **Step 6: Commit**

```bash
make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log
[ $rc -eq 0 ] && git add src/nichiyou_daiku/shell/instructions.py src/nichiyou_daiku/cli/commands/steps.py docs/dsl-specification.md docs/api-specification.md skills/design/SKILL.md README.md tests/shell/test_instructions.py tests/cli/commands/test_steps.py && git commit -m "feat: Start the assembly steps with the parts to make

steps.md lists every part's lumber, length and count and shows a
drawing of each drilled one; the steps command writes part-NN.png."
```
