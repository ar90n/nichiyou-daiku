# Calc/Display Separation (M2-2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move cut planning out of the Markdown report and the technical-drawing layout out of the CLI command, without changing any output.

**Architecture:** A new `shell/cutting.py` owns the cut plan (`plan_cuts` → one `LumberPlan` per lumber type); the report calls it once and only formats. A new `shell/drawing.py` owns the drawing (`technical_drawing` → `ExportSVG`); the CLI only reads the DSL, writes SVG/PDF and reports errors. Each view is projected twice instead of three times.

**Tech Stack:** Python 3.13, uv, pydantic, build123d (optional `viz` extra), cairosvg, click, pytest, ruff, pyright, Dagger (`make ci-local`).

**Spec:** `docs/superpowers/specs/2026-10-11-calc-display-separation-design.md`

## Global Constraints

- Behaviour must not change: report text identical (except the `*Generated on ...*` line); drawing SVG identical, or every number within 1e-6mm.
- `generate_markdown_report(resource_summary, project_name, standard_lengths, include_cut_diagram, include_anchor_details, include_pilot_holes)` keeps its signature.
- `CutPlan`, `LumberPlan` and `plan_cuts` are not exported from `nichiyou_daiku.shell.__init__`.
- `nichiyou_daiku.shell.__init__` must not import `shell/drawing.py` (build123d is optional); the CLI imports it only after `ensure_build123d_available`.
- Code comments: minimal, explain why, in English. Never commit dotfiles. `CLAUDE.md` is git-ignored and is not committed.
- Project rule: run `make ci-local` and see `✅ All CI checks passed!` before every commit.
- Run Python through the project venv: `.venv/bin/pytest`, `.venv/bin/python` (or `uv run ...`).

## Review Focus

- A lumber type missing from `standard_lengths` → its boards use 2440mm, as today (pinned in Task 1).
- Every piece of a type longer than every stock board → no boards, 0 waste, 0.0%, and the oversize warning in both report sections (pinned in Tasks 1 and 2).
- A model with no pieces → `plan_cuts` returns `{}` and the report still renders its section headers (pinned in Tasks 1 and 2).
- `include_cut_diagram=False` → the plan is still computed exactly once (pinned in Task 2).
- Lower-case page size (`"a3"`) → accepted, as the CLI's case-insensitive choice allows (pinned in Task 3).

---

## File Structure

- Create `src/nichiyou_daiku/shell/cutting.py` — stock lengths, saw kerf, `CutPlan` (one board), `LumberPlan` (one lumber type), `plan_cuts`.
- Modify `src/nichiyou_daiku/shell/report_generator.py` — drop the cut planning; format `LumberPlan`s.
- Create `src/nichiyou_daiku/shell/drawing.py` — four-view layout and `technical_drawing`.
- Modify `src/nichiyou_daiku/cli/commands/drawing.py` — I/O only.
- Modify `pyproject.toml` — measure and type-check `cli/commands/drawing.py` again.
- Create `tests/shell/test_cutting.py`, `tests/shell/test_drawing.py`; modify `tests/shell/test_report_generator.py`, `tests/cli/commands/test_drawing.py`.
- Modify `README.md` (structure listing) and the spec's status line.

Scratch files for the before/after comparison live in `/tmp/nd-m2-2/` and are never committed.

---

### Task 1: Cut planning module

**Files:**
- Create: `/tmp/nd-m2-2/capture_reports.py`, `/tmp/nd-m2-2/capture_drawings.sh`, `/tmp/nd-m2-2/compare.py` (scratch)
- Create: `src/nichiyou_daiku/shell/cutting.py`
- Modify: `src/nichiyou_daiku/shell/report_generator.py:1-160`
- Create: `tests/shell/test_cutting.py`
- Modify: `tests/shell/test_report_generator.py:1-185`

**Interfaces:**
- Consumes: `nichiyou_daiku.shell.resources.PieceResource`, `ResourceSummary`
- Produces:
  - `DEFAULT_KERF_MM: float = 3.0`
  - `DEFAULT_STANDARD_LENGTHS: dict[PieceType, list[float]]`
  - `FALLBACK_STANDARD_LENGTHS: list[float] = [2440.0]`
  - `CutPlan(board_length: float, cuts: list[tuple[str, float]], waste: float)` (dataclass)
  - `LumberPlan(available_lengths: list[float], boards: list[CutPlan], oversize: list[PieceResource])` with properties `board_counts -> dict[float, int]`, `total_waste -> float`, `waste_percentage -> float`
  - `plan_cuts(summary: ResourceSummary, standard_lengths: Mapping[PieceType, Sequence[float]] | None = None, kerf: float = DEFAULT_KERF_MM) -> dict[PieceType, LumberPlan]`
  - `_optimize_cuts(pieces, available_lengths, kerf=DEFAULT_KERF_MM) -> list[CutPlan]`, `_oversize_pieces(pieces, available_lengths) -> list[PieceResource]` (private, moved unchanged)

- [ ] **Step 1: Write the scratch capture and compare scripts**

`/tmp/nd-m2-2/capture_reports.py`:

```python
"""Write the Markdown report of every example design into OUTDIR."""

import os
import runpy
import sys
import types
from pathlib import Path

ROOT = Path("/home/argon/workspace/nichiyou-daiku")
out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=True)

stub = types.ModuleType("ocp_vscode")
stub.show = lambda *args, **kwargs: None  # type: ignore[attr-defined]
sys.modules["ocp_vscode"] = stub

from nichiyou_daiku.core.assembly import Assembly  # noqa: E402
from nichiyou_daiku.core.piece import PieceType  # noqa: E402
from nichiyou_daiku.dsl import parse_dsl  # noqa: E402
from nichiyou_daiku.shell import extract_resources, generate_markdown_report  # noqa: E402

files = sorted(
    [*ROOT.glob("examples/nd_files/*.nd"), *ROOT.glob("prompts/examples/nd-output/*.nd")]
)
models = {path.stem: parse_dsl(path.read_text()) for path in files}
# long_shelf.py writes its own (timestamped) report into the working directory,
# so run it elsewhere to keep that file out of the comparison
cwd = os.getcwd()
scratch = out.parent / "scratch"
scratch.mkdir(exist_ok=True)
os.chdir(scratch)
models["long_shelf"] = runpy.run_path(str(ROOT / "examples/long_shelf.py"))["model"]
os.chdir(cwd)

stock = {
    "default": None,
    "custom": {PieceType.PT_2x4: [1830.0]},  # 1x4 falls back to 2440mm
    "tiny": {PieceType.PT_2x4: [500.0], PieceType.PT_1x4: [500.0]},  # oversize pieces
}
for name, model in models.items():
    summary = extract_resources(Assembly.of(model))
    for label, lengths in stock.items():
        for diagram in (True, False):
            report = generate_markdown_report(
                summary,
                project_name=name,
                standard_lengths=lengths,
                include_cut_diagram=diagram,
            )
            kept = [
                line
                for line in report.splitlines()
                if not line.startswith("*Generated on")
            ]
            (out / f"{name}-{label}-{diagram}.md").write_text("\n".join(kept))
print(f"wrote {len(list(out.glob('*.md')))} reports to {out}")
```

`/tmp/nd-m2-2/capture_drawings.sh`:

```bash
#!/usr/bin/env bash
# Write the SVG drawing of every prompt example design into $1 (A3 and A4).
set -euo pipefail
out="$1"
mkdir -p "$out"
root=/home/argon/workspace/nichiyou-daiku
for nd in "$root"/prompts/examples/nd-output/*.nd; do
  name=$(basename "$nd" .nd)
  for page in A3 A4; do
    "$root/.venv/bin/nichiyou-daiku" drawing "$nd" -o "$out/$name-$page.svg" --page-size "$page" 2>/dev/null
  done
done
echo "wrote $(ls "$out"/*.svg | wc -l) drawings to $out"
```

`/tmp/nd-m2-2/compare.py`:

```python
"""Compare two capture directories: reports must match exactly, SVG numbers
may differ by at most 1e-6mm."""

import re
import sys
from pathlib import Path

NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:e-?\d+)?")
before, after = Path(sys.argv[1]), Path(sys.argv[2])
different = []
for old in sorted(before.iterdir()):
    new = after / old.name
    if not new.exists():
        different.append(f"{old.name} (missing)")
        continue
    a, b = old.read_text(), new.read_text()
    if a == b:
        continue
    if old.suffix == ".svg" and NUMBER.sub("#", a) == NUMBER.sub("#", b):
        pairs = zip(map(float, NUMBER.findall(a)), map(float, NUMBER.findall(b)))
        if max(abs(x - y) for x, y in pairs) <= 1.0000001e-6:
            continue
    different.append(old.name)
print(f"compared {len(list(before.iterdir()))} files: " + ("identical" if not different else f"DIFFERENT {different}"))
sys.exit(1 if different else 0)
```

- [ ] **Step 2: Record the current outputs (before any source change)**

Run:
```bash
chmod +x /tmp/nd-m2-2/capture_drawings.sh
cd /home/argon/workspace/nichiyou-daiku
.venv/bin/python /tmp/nd-m2-2/capture_reports.py /tmp/nd-m2-2/before
/tmp/nd-m2-2/capture_drawings.sh /tmp/nd-m2-2/before
```
Expected: `wrote 48 reports to /tmp/nd-m2-2/before` (8 designs × 3 stock settings × 2) and `wrote 6 drawings to /tmp/nd-m2-2/before`.

- [ ] **Step 3: Write the failing tests**

Create `tests/shell/test_cutting.py`:

```python
"""Tests for planning cuts from stock boards."""

import pytest

from nichiyou_daiku.core.piece import PieceType
from nichiyou_daiku.shell.cutting import (
    DEFAULT_STANDARD_LENGTHS,
    CutPlan,
    _optimize_cuts,
    plan_cuts,
)
from nichiyou_daiku.shell.resources import PieceResource, ResourceSummary


def _piece(
    id_: str, length: float, piece_type: PieceType = PieceType.PT_2x4
) -> PieceResource:
    return PieceResource(
        id=id_, type=piece_type, length=length, width=89.0, height=38.0, volume=0
    )


def _summary(*pieces: PieceResource) -> ResourceSummary:
    by_type: dict[PieceType, int] = {}
    lengths: dict[PieceType, float] = {}
    for piece in pieces:
        by_type[piece.type] = by_type.get(piece.type, 0) + 1
        lengths[piece.type] = lengths.get(piece.type, 0.0) + piece.length
    return ResourceSummary(
        pieces=list(pieces),
        total_pieces=len(pieces),
        pieces_by_type=by_type,
        total_length_by_type=lengths,
        total_volume=0.0,
    )


class TestCutPlan:
    def test_should_create_cut_plan(self):
        plan = CutPlan(
            board_length=2440.0,
            cuts=[("piece1", 1000.0), ("piece2", 800.0)],
            waste=640.0,
        )

        assert plan.board_length == 2440.0
        assert len(plan.cuts) == 2
        assert plan.cuts[0] == ("piece1", 1000.0)
        assert plan.waste == 640.0


class TestDefaultStandardLengths:
    def test_every_lumber_type_has_common_stock_lengths(self):
        assert set(DEFAULT_STANDARD_LENGTHS) == {PieceType.PT_2x4, PieceType.PT_1x4}
        assert DEFAULT_STANDARD_LENGTHS[PieceType.PT_2x4] == [2440.0, 3050.0, 3660.0]
        assert DEFAULT_STANDARD_LENGTHS[PieceType.PT_1x4] == [1830.0, 2440.0, 3050.0]


class TestOptimizeCuts:
    def test_should_optimize_simple_cuts(self):
        plans = _optimize_cuts(
            [_piece("p1", 1000.0), _piece("p2", 800.0)], [2440.0], kerf=0.0
        )

        assert len(plans) == 1
        assert plans[0].board_length == 2440.0
        assert [cut[0] for cut in plans[0].cuts] == ["p1", "p2"]
        assert plans[0].waste == 640.0

    def test_should_use_multiple_boards_when_needed(self):
        plans = _optimize_cuts(
            [_piece("p1", 2000.0), _piece("p2", 2000.0)], [2440.0], kerf=0.0
        )

        assert len(plans) == 2
        assert all(plan.board_length == 2440.0 for plan in plans)
        assert all(len(plan.cuts) == 1 for plan in plans)

    def test_should_choose_optimal_board_length(self):
        # The 1830mm board wastes less than the 2440mm one
        plans = _optimize_cuts([_piece("p1", 1500.0)], [1830.0, 2440.0], kerf=0.0)

        assert len(plans) == 1
        assert plans[0].board_length == 1830.0
        assert plans[0].waste == 330.0

    def test_should_handle_empty_pieces_list(self):
        assert _optimize_cuts([], [2440.0]) == []


class TestCutPlanKerf:
    def test_saw_kerf_is_allowed_between_cuts(self):
        # 3 x 813 = 2439mm fits 2440 only if the saw removes nothing
        pieces = [_piece("a", 813.0), _piece("b", 813.0), _piece("c", 813.0)]
        assert len(_optimize_cuts(pieces, [2440.0], kerf=3.0)) == 2

    def test_offcut_excludes_kerf(self):
        plans = _optimize_cuts(
            [_piece("a", 1000.0), _piece("b", 800.0)], [2440.0], kerf=3.0
        )
        assert plans[0].waste == 634.0

    def test_exact_fit_needs_no_final_cut(self):
        plans = _optimize_cuts(
            [_piece("a", 1218.5), _piece("b", 1218.5)], [2440.0], kerf=3.0
        )
        assert len(plans) == 1
        assert plans[0].waste == 0.0

    def test_piece_longer_than_every_board_is_not_planned(self):
        pieces = [_piece("long", 4000.0), _piece("short", 500.0)]
        plans = _optimize_cuts(pieces, [2440.0, 3050.0, 3660.0], kerf=0.0)
        assert [piece_id for plan in plans for piece_id, _ in plan.cuts] == ["short"]
        assert all(plan.waste >= 0 for plan in plans)


class TestPlanCuts:
    def test_uses_the_default_stock_lengths(self):
        plan = plan_cuts(_summary(_piece("a", 1000.0)))[PieceType.PT_2x4]
        assert plan.available_lengths == [2440.0, 3050.0, 3660.0]
        assert plan.board_counts == {2440.0: 1}

    def test_type_missing_from_standard_lengths_uses_2440mm(self):
        summary = _summary(_piece("a", 1000.0, PieceType.PT_1x4))
        plans = plan_cuts(summary, {PieceType.PT_2x4: [3050.0]})
        assert plans[PieceType.PT_1x4].available_lengths == [2440.0]

    def test_oversize_pieces_are_listed_instead_of_planned(self):
        summary = _summary(_piece("long", 4000.0), _piece("short", 500.0))
        plan = plan_cuts(summary, {PieceType.PT_2x4: [2440.0]})[PieceType.PT_2x4]
        assert [piece.id for piece in plan.oversize] == ["long"]
        assert [cut[0] for board in plan.boards for cut in board.cuts] == ["short"]

    def test_all_pieces_oversize_means_no_boards_and_no_waste(self):
        summary = _summary(_piece("long", 4000.0))
        plan = plan_cuts(summary, {PieceType.PT_2x4: [2440.0]})[PieceType.PT_2x4]
        assert plan.boards == []
        assert plan.board_counts == {}
        assert plan.total_waste == 0
        assert plan.waste_percentage == 0.0

    def test_totals_add_up_over_the_boards(self):
        summary = _summary(_piece("a", 2000.0), _piece("b", 2000.0), _piece("c", 300.0))
        plan = plan_cuts(summary, {PieceType.PT_2x4: [2440.0]})[PieceType.PT_2x4]
        assert plan.board_counts == {2440.0: 2}
        assert plan.total_waste == sum(board.waste for board in plan.boards)
        assert plan.waste_percentage == pytest.approx(plan.total_waste / 4880.0 * 100)

    def test_lumber_types_come_in_report_order(self):
        summary = _summary(_piece("a", 500.0), _piece("b", 500.0, PieceType.PT_1x4))
        assert list(plan_cuts(summary)) == [PieceType.PT_1x4, PieceType.PT_2x4]

    def test_no_pieces_means_no_plans(self):
        assert plan_cuts(_summary()) == {}
```

- [ ] **Step 4: Run the new tests to verify they fail**

Run: `.venv/bin/pytest tests/shell/test_cutting.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'nichiyou_daiku.shell.cutting'`.

- [ ] **Step 5: Create `src/nichiyou_daiku/shell/cutting.py`**

Move `CutPlan`, `DEFAULT_KERF_MM`, `_oversize_pieces` and `_optimize_cuts` out of `report_generator.py` with their bodies and docstrings unchanged, and add the rest:

```python
"""Plan how to cut lumber pieces from stock boards.

Kept apart from the report so the plan is computed once and can serve any
output, not only the Markdown report.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Dict, List, Tuple

from nichiyou_daiku.core.piece import PieceType

from .resources import PieceResource, ResourceSummary

DEFAULT_KERF_MM = 3.0
"""Material removed by each saw cut."""

DEFAULT_STANDARD_LENGTHS: Dict[PieceType, List[float]] = {
    PieceType.PT_2x4: [2440.0, 3050.0, 3660.0],  # 8ft, 10ft, 12ft
    PieceType.PT_1x4: [1830.0, 2440.0, 3050.0],  # 6ft, 8ft, 10ft
}

FALLBACK_STANDARD_LENGTHS: List[float] = [2440.0]
"""Stock lengths for a lumber type that ``standard_lengths`` does not list."""


@dataclass
class CutPlan:
    # (moved verbatim from report_generator.py, docstring included)
    board_length: float
    cuts: List[Tuple[str, float]]
    waste: float


@dataclass
class LumberPlan:
    """How to cut every piece of one lumber type.

    Attributes:
        available_lengths: Stock board lengths in mm
        boards: One cut plan per board to buy
        oversize: Pieces longer than every stock board; they are not in ``boards``
    """

    available_lengths: List[float]
    boards: List[CutPlan]
    oversize: List[PieceResource]

    @property
    def board_counts(self) -> Dict[float, int]:
        """Number of boards to buy per stock length."""
        counts: Dict[float, int] = {}
        for board in self.boards:
            counts[board.board_length] = counts.get(board.board_length, 0) + 1
        return counts

    @property
    def total_waste(self) -> float:
        return sum(board.waste for board in self.boards)

    @property
    def waste_percentage(self) -> float:
        """Waste as a share of the purchased length (0 when nothing is bought)."""
        purchased = sum(board.board_length for board in self.boards)
        return self.total_waste / purchased * 100 if purchased > 0 else 0.0


# _oversize_pieces and _optimize_cuts: moved verbatim from report_generator.py


def plan_cuts(
    summary: ResourceSummary,
    standard_lengths: Mapping[PieceType, Sequence[float]] | None = None,
    kerf: float = DEFAULT_KERF_MM,
) -> Dict[PieceType, LumberPlan]:
    """Plan the cuts for every lumber type in ``summary``, in report order.

    Args:
        summary: Pieces to cut
        standard_lengths: Stock board lengths per lumber type; defaults to
            ``DEFAULT_STANDARD_LENGTHS``. Types it does not list use
            ``FALLBACK_STANDARD_LENGTHS``.
        kerf: Material removed by each saw cut in mm

    Examples:
        >>> piece = PieceResource(id="p1", type=PieceType.PT_2x4, length=1000.0,
        ...                       width=89.0, height=38.0, volume=0)
        >>> summary = ResourceSummary(
        ...     pieces=[piece], total_pieces=1,
        ...     pieces_by_type={PieceType.PT_2x4: 1},
        ...     total_length_by_type={PieceType.PT_2x4: 1000.0},
        ...     total_volume=0,
        ... )
        >>> plan_cuts(summary)[PieceType.PT_2x4].board_counts
        {2440.0: 1}
    """
    if standard_lengths is None:
        standard_lengths = DEFAULT_STANDARD_LENGTHS
    plans: Dict[PieceType, LumberPlan] = {}
    for piece_type in sorted(summary.pieces_by_type, key=lambda t: t.value):
        pieces = [p for p in summary.pieces if p.type == piece_type]
        available = list(standard_lengths.get(piece_type, FALLBACK_STANDARD_LENGTHS))
        plans[piece_type] = LumberPlan(
            available_lengths=available,
            boards=_optimize_cuts(pieces, available, kerf),
            oversize=_oversize_pieces(pieces, available),
        )
    return plans
```

The two "moved verbatim" comments above are instructions, not code: paste the real `CutPlan` docstring and the real `_oversize_pieces` / `_optimize_cuts` functions (with their doctests) in those places.

- [ ] **Step 6: Point `report_generator.py` at the moved code**

In `src/nichiyou_daiku/shell/report_generator.py`:
1. Delete `class CutPlan`, `_get_default_standard_lengths`, `DEFAULT_KERF_MM`, `_oversize_pieces` and `_optimize_cuts`.
2. Add `from .cutting import DEFAULT_STANDARD_LENGTHS, _optimize_cuts, _oversize_pieces`.
3. In `generate_markdown_report`, replace `standard_lengths = _get_default_standard_lengths()` with `standard_lengths = DEFAULT_STANDARD_LENGTHS`.
4. Remove the imports `ruff check` now reports as unused (`dataclass`, `Tuple`).

In `tests/shell/test_report_generator.py`:
1. Remove `CutPlan`, `_get_default_standard_lengths` and `_optimize_cuts` from the import list.
2. Delete `TestCutPlan`, `TestGetDefaultStandardLengths`, `TestOptimizeCuts`, `TestCutPlanKerf` and `TestOversizePieces.test_piece_longer_than_every_board_is_not_planned` (they now live in `test_cutting.py`). Keep the `_piece` helper and `TestOversizePieces.test_report_warns_about_piece_longer_than_every_board`.

- [ ] **Step 7: Run the tests**

Run: `.venv/bin/pytest tests/shell -q && .venv/bin/pytest --doctest-modules src/nichiyou_daiku/shell/cutting.py -q`
Expected: all pass (the new `TestPlanCuts` included).

- [ ] **Step 8: Check the reports did not change**

Run:
```bash
.venv/bin/python /tmp/nd-m2-2/capture_reports.py /tmp/nd-m2-2/after-1
.venv/bin/python - <<'EOF'
import filecmp, sys
d = filecmp.dircmp("/tmp/nd-m2-2/before", "/tmp/nd-m2-2/after-1")
md = [f for f in d.common_files if f.endswith(".md")]
match, mismatch, errors = filecmp.cmpfiles(d.left, d.right, md, shallow=False)
print(len(match), "identical", mismatch, errors); sys.exit(1 if mismatch or errors else 0)
EOF
```
Expected: `48 identical [] []`.

- [ ] **Step 9: Lint, CI, commit**

Run: `make lint && make ci-local`
Expected: `0 errors` from pyright, ruff clean, `✅ All CI checks passed!`

```bash
git add src/nichiyou_daiku/shell/cutting.py src/nichiyou_daiku/shell/report_generator.py tests/shell/test_cutting.py tests/shell/test_report_generator.py
git commit -m "refactor(report): Move cut planning into shell/cutting.py"
```

---

### Task 2: The report plans the cuts once

**Files:**
- Modify: `src/nichiyou_daiku/shell/report_generator.py` (`_oversize_warning`, `_generate_purchase_recommendations`, `_generate_cut_list`, `generate_markdown_report`)
- Modify: `tests/shell/test_report_generator.py`

**Interfaces:**
- Consumes: `plan_cuts`, `LumberPlan` from Task 1
- Produces: `_generate_purchase_recommendations(plans: Mapping[PieceType, LumberPlan]) -> str`, `_generate_cut_list(plans: Mapping[PieceType, LumberPlan]) -> str`, `_oversize_warning(plan: LumberPlan) -> List[str]`

- [ ] **Step 1: Update the tests to the new section signatures**

In `tests/shell/test_report_generator.py`:
1. Add `import pytest` and `from nichiyou_daiku.shell.cutting import plan_cuts`.
2. Replace each section call:
   - `_generate_purchase_recommendations(summary, lengths)` → `_generate_purchase_recommendations(plan_cuts(summary, lengths))`
   - `_generate_cut_list(summary, lengths)` → `_generate_cut_list(plan_cuts(summary, lengths))`
   - `_generate_purchase_recommendations(summary, standard_lengths)` → `_generate_purchase_recommendations(plan_cuts(summary, standard_lengths))`
   - `_generate_cut_list(summary, standard_lengths)` → `_generate_cut_list(plan_cuts(summary, standard_lengths))`
3. Append:

```python
class TestCutPlanIsComputedOnce:
    @pytest.mark.parametrize("include_cut_diagram", [True, False])
    def test_report_plans_the_cuts_once(self, include_cut_diagram):
        summary = ResourceSummary(
            pieces=[_piece("a", 1000.0)],
            total_pieces=1,
            pieces_by_type={PieceType.PT_2x4: 1},
            total_length_by_type={PieceType.PT_2x4: 1000.0},
            total_volume=0.0,
        )
        with patch(
            "nichiyou_daiku.shell.report_generator.plan_cuts", wraps=plan_cuts
        ) as spy:
            generate_markdown_report(summary, include_cut_diagram=include_cut_diagram)
        assert spy.call_count == 1

    def test_report_of_no_pieces_still_has_its_sections(self):
        summary = ResourceSummary(
            pieces=[],
            total_pieces=0,
            pieces_by_type={},
            total_length_by_type={},
            total_volume=0.0,
        )
        report = generate_markdown_report(summary)
        assert "## Purchase Recommendations" in report
        assert "## Optimized Cut List" in report
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/pytest tests/shell/test_report_generator.py -q`
Expected: FAIL — `TypeError` (`_generate_purchase_recommendations() missing 1 required positional argument`) and `AttributeError: ... does not have the attribute 'plan_cuts'`; `test_report_of_no_pieces_still_has_its_sections` passes already (it pins current behaviour).

- [ ] **Step 3: Format the plan instead of computing it**

In `src/nichiyou_daiku/shell/report_generator.py`, replace the import from `.cutting` with `from .cutting import LumberPlan, plan_cuts`, add `from collections.abc import Mapping`, and replace the three functions:

```python
def _oversize_warning(plan: LumberPlan) -> List[str]:
    longest = max(plan.available_lengths)
    return [
        f"- ⚠ {p.id} ({format_mm(p.length)}mm) is longer than the longest available "
        f"board ({longest:.0f}mm) and cannot be cut from stock"
        for p in plan.oversize
    ]


def _generate_purchase_recommendations(plans: Mapping[PieceType, LumberPlan]) -> str:
    """Generate purchase recommendations from the cut plan.

    Args:
        plans: Cut plan per lumber type, in report order

    Returns:
        Markdown formatted purchase recommendations
    """
    lines = ["## Purchase Recommendations", ""]

    for piece_type, plan in plans.items():
        lengths_str = ", ".join(
            f"{length:.0f}mm" for length in sorted(plan.available_lengths)
        )
        lines.extend(
            [
                f"### {piece_type.value} Lumber (Available: {lengths_str})",
                "Optimal purchase:",
            ]
        )
        for board_length, count in sorted(plan.board_counts.items()):
            lines.append(f"- {count} × {board_length:.0f}mm boards")
        lines.append(
            f"Total waste: {format_mm(plan.total_waste)}mm "
            f"({plan.waste_percentage:.1f}%)"
        )
        lines.extend(_oversize_warning(plan))
        lines.append("")

    return "\n".join(lines)


def _generate_cut_list(plans: Mapping[PieceType, LumberPlan]) -> str:
    """Generate the cut list from the cut plan.

    Args:
        plans: Cut plan per lumber type, in report order

    Returns:
        Markdown formatted cut list
    """
    lines = ["## Optimized Cut List", ""]

    for piece_type, plan in plans.items():
        lines.extend([f"### {piece_type.value} Boards", ""])
        warnings = _oversize_warning(plan)
        if warnings:
            lines.extend([*warnings, ""])

        for i, board in enumerate(plan.boards, 1):
            lines.append(f"**Board {i}** ({board.board_length:.0f}mm):")
            for piece_id, length in board.cuts:
                lines.append(f"- Cut {format_mm(length)}mm → {piece_id}")
            if board.waste > 0:
                lines.append(f"- Waste: {format_mm(board.waste)}mm")
            lines.append("")

    return "\n".join(lines)
```

In `generate_markdown_report`, delete the `if standard_lengths is None: ...` block, compute `plans = plan_cuts(resource_summary, standard_lengths)` before building the sections, and change the two calls to `_generate_purchase_recommendations(plans)` and `_generate_cut_list(plans)`. Remove imports `ruff check` reports as unused.

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/pytest tests/shell -q && .venv/bin/pytest --doctest-modules src/nichiyou_daiku/shell -q`
Expected: all pass.

- [ ] **Step 5: Check the reports did not change**

Run:
```bash
.venv/bin/python /tmp/nd-m2-2/capture_reports.py /tmp/nd-m2-2/after-2
.venv/bin/python - <<'EOF'
import filecmp, sys
d = filecmp.dircmp("/tmp/nd-m2-2/before", "/tmp/nd-m2-2/after-2")
md = [f for f in d.common_files if f.endswith(".md")]
match, mismatch, errors = filecmp.cmpfiles(d.left, d.right, md, shallow=False)
print(len(match), "identical", mismatch, errors); sys.exit(1 if mismatch or errors else 0)
EOF
```
Expected: `48 identical [] []`.

- [ ] **Step 6: Lint, CI, commit**

Run: `make lint && make ci-local`
Expected: clean, `✅ All CI checks passed!`

```bash
git add src/nichiyou_daiku/shell/report_generator.py tests/shell/test_report_generator.py
git commit -m "refactor(report): Plan the cuts once and only format them"
```

---

### Task 3: Drawing layout module

**Files:**
- Create: `src/nichiyou_daiku/shell/drawing.py`
- Create: `tests/shell/test_drawing.py`

**Interfaces:**
- Consumes: `build123d` (`Compound`, `ExportSVG`, `LineType`, `PageSize`, `Pos`, `ShapeList`, `TechnicalDrawing`, `Unit`, `scale`); `nichiyou_daiku.shell.build123d_export.assembly_to_build123d` only in tests
- Produces:
  - `PAGE_SIZES: tuple[str, ...] = ("A4", "A3", "A2", "A1")`
  - `VIEW_FILL: float = 0.7`
  - `technical_drawing(part: Compound, *, title: str, drawing_number: str, designed_by: str, page_size: str = "A3", design_date: date | None = None) -> ExportSVG`
  - `_layout_views(part: Compound, width: float, height: float) -> list[_View]` with `_View.visible: ShapeList`, `_View.hidden: ShapeList` (private; used by tests)

- [ ] **Step 1: Write the failing tests**

Create `tests/shell/test_drawing.py`:

```python
"""Tests for the technical drawing layout."""

from datetime import date
from itertools import combinations

import pytest

pytest.importorskip("build123d")

from build123d import Compound  # noqa: E402

from nichiyou_daiku.core.assembly import Assembly  # noqa: E402
from nichiyou_daiku.dsl import parse_dsl  # noqa: E402
from nichiyou_daiku.shell.build123d_export import assembly_to_build123d  # noqa: E402
from nichiyou_daiku.shell.drawing import (  # noqa: E402
    VIEW_FILL,
    _layout_views,
    technical_drawing,
)

CORNER = "(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n"
A3_WIDTH, A3_HEIGHT = 420.0, 297.0


@pytest.fixture(scope="module")
def part() -> Compound:
    return assembly_to_build123d(Assembly.of(parse_dsl(CORNER)), fillet_radius=0)


def _bounds(view):
    return Compound(children=list(view.visible) + list(view.hidden)).bounding_box()


def _draw(part, path, **options):
    technical_drawing(
        part, title="Corner", drawing_number="ND-1", designed_by="me", **options
    ).write(str(path))
    return path.read_text()


def test_views_fit_inside_the_drawing_area_without_overlapping(part):
    boxes = [_bounds(view) for view in _layout_views(part, A3_WIDTH, A3_HEIGHT)]
    assert len(boxes) == 4
    # The drawing area leaves 20mm side margins and a 40mm title block,
    # and its centre sits 10mm above the page centre
    half_width = (A3_WIDTH - 40) / 2
    half_height = (A3_HEIGHT - 80) / 2
    for box in boxes:
        assert -half_width <= box.min.X and box.max.X <= half_width
        assert -half_height + 10 <= box.min.Y and box.max.Y <= half_height + 10
    for a, b in combinations(boxes, 2):
        assert (
            a.max.X <= b.min.X
            or b.max.X <= a.min.X
            or a.max.Y <= b.min.Y
            or b.max.Y <= a.min.Y
        )


def test_largest_view_fills_the_set_share_of_a_grid_cell(part):
    views = _layout_views(part, A3_WIDTH, A3_HEIGHT)
    cell = min((A3_WIDTH - 40) / 2 - 10, (A3_HEIGHT - 80) / 2 - 10)
    largest = max(max(box.size.X, box.size.Y) for box in map(_bounds, views))
    assert largest == pytest.approx(cell * VIEW_FILL)


def test_drawing_has_visible_and_hidden_lines(part, tmp_path):
    svg = _draw(part, tmp_path / "drawing.svg", design_date=date(2026, 1, 1))
    assert 'id="Visible"' in svg
    hidden_layer = svg.split('id="Hidden"', 1)[1].split("</g>", 1)[0]
    assert "<path" in hidden_layer


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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/pytest tests/shell/test_drawing.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'nichiyou_daiku.shell.drawing'`.

- [ ] **Step 3: Create `src/nichiyou_daiku/shell/drawing.py`**

```python
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
    exporter.add_layer("Hidden", line_color=(99, 99, 99), line_type=LineType.ISO_DOT)
    exporter.add_shape([e for view in views for e in view.visible], layer="Visible")
    exporter.add_shape([e for view in views for e in view.hidden], layer="Hidden")
    exporter.add_shape(border, layer="Visible")
    return exporter
```

- [ ] **Step 4: Run the tests and the type checker**

Run: `.venv/bin/pytest tests/shell/test_drawing.py -q && .venv/bin/pyright src/nichiyou_daiku/shell/drawing.py`
Expected: 5 passed; `0 errors`. If pyright reports build123d typing errors, fix them with precise annotations (not `# type: ignore`) and ledger the ruling.

- [ ] **Step 5: Lint, CI, commit**

Run: `make lint && make ci-local`
Expected: clean, `✅ All CI checks passed!`

```bash
git add src/nichiyou_daiku/shell/drawing.py tests/shell/test_drawing.py
git commit -m "feat(shell): Lay out technical drawings outside the CLI"
```

---

### Task 4: The drawing command only does I/O

**Files:**
- Modify: `src/nichiyou_daiku/cli/commands/drawing.py` (whole body)
- Modify: `pyproject.toml` (`[tool.coverage.run] omit`, `[tool.pyright] exclude`)
- Modify: `tests/cli/commands/test_drawing.py`

**Interfaces:**
- Consumes: `technical_drawing(part, *, title, drawing_number, designed_by, page_size)` from Task 3
- Produces: unchanged CLI (`nichiyou-daiku drawing INPUT [-o] [--title] [--drawing-number] [--designed-by] [--fillet-radius] [--page-size]`); drawing failures print `Error creating drawing: <reason>` and exit 1

- [ ] **Step 1: Write the failing test**

Append to `tests/cli/commands/test_drawing.py`:

```python
def test_drawing_failure_is_reported(runner, tmp_path, beam_file, monkeypatch):
    import nichiyou_daiku.shell.drawing as drawing_module

    def broken(*args, **kwargs):
        raise RuntimeError("no projection")

    monkeypatch.setattr(drawing_module, "technical_drawing", broken)
    result = runner.invoke(
        cli, ["drawing", str(beam_file), "-o", str(tmp_path / "out.svg")]
    )
    assert result.exit_code == 1
    assert "Error creating drawing: no projection" in result.output
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/pytest tests/cli/commands/test_drawing.py::test_drawing_failure_is_reported -q`
Expected: FAIL — `assert 0 == 1` (the command still draws on its own).

- [ ] **Step 3: Replace the command body**

In `src/nichiyou_daiku/cli/commands/drawing.py`: delete `project_to_2d` and the `from datetime import date` import; keep the `@click.command()` / `@click.option(...)` decorators, the signature and the docstring exactly as they are; replace everything from `echo = CliEcho(ctx)` to the end of the function with:

```python
    echo = CliEcho(ctx)

    ensure_build123d_available(echo)
    try:
        import cairosvg

        from nichiyou_daiku.shell.drawing import technical_drawing
    except ImportError as e:
        echo.error(
            f"Error importing dependencies: {e}\n"
            "Please install with: uv add nichiyou-daiku[viz]"
        )
        sys.exit(1)

    # Determine output path and title
    require_output_for_stdin(input_file, output)
    output_path = output or Path(input_file).with_suffix(".pdf")
    ensure_not_overwriting_input(input_file, output_path)
    write_svg_only = output_path.suffix.lower() == ".svg"
    source_stem = output_path.stem if input_file == "-" else Path(input_file).stem

    dsl_content = read_dsl_file(input_file)
    model = parse_dsl_to_model(dsl_content, echo)
    assembly = create_assembly_from_model(model, echo)
    compound = convert_assembly_to_build123d(
        assembly, echo, fillet_radius=fillet_radius
    )

    try:
        exporter = technical_drawing(
            compound,
            title=title or source_stem,
            drawing_number=drawing_number,
            designed_by=designed_by,
            page_size=page_size,
        )
    except Exception as e:
        echo.exception(f"Error creating drawing: {e}")
        sys.exit(1)

    if write_svg_only:
        try:
            exporter.write(str(output_path))
        except Exception as e:
            echo.exception(f"Error exporting SVG: {e}")
            sys.exit(1)
    else:
        # Render via a private temp SVG so files next to the output are untouched
        with tempfile.TemporaryDirectory() as tmp_dir:
            svg_path = Path(tmp_dir) / "drawing.svg"
            try:
                exporter.write(str(svg_path))
                cairosvg.svg2pdf(url=str(svg_path), write_to=str(output_path))
            except Exception as e:
                echo.exception(f"Error converting to PDF: {e}")
                sys.exit(1)

    echo.info(f"Successfully created technical drawing: {output_path}")
```

In `pyproject.toml`, delete the line `"src/nichiyou_daiku/cli/commands/drawing.py",` from both `[tool.coverage.run] omit` and `[tool.pyright] exclude`.

- [ ] **Step 4: Run the drawing tests and the type checker**

Run: `.venv/bin/pytest tests/cli/commands/test_drawing.py tests/shell/test_drawing.py -q && .venv/bin/pyright src/nichiyou_daiku`
Expected: all pass; `0 errors`. Fix any pyright error in `cli/commands/drawing.py` with precise annotations and ledger the ruling.

- [ ] **Step 5: Check the drawings did not change**

Run:
```bash
/tmp/nd-m2-2/capture_drawings.sh /tmp/nd-m2-2/after-4
mkdir -p /tmp/nd-m2-2/before-svg && cp /tmp/nd-m2-2/before/*.svg /tmp/nd-m2-2/before-svg/
.venv/bin/python /tmp/nd-m2-2/compare.py /tmp/nd-m2-2/before-svg /tmp/nd-m2-2/after-4
```
Expected: `compared 6 files: identical`. (Captures from different days differ in the title-block date; re-capture `before` from the commit before Task 3 if the day changed.)

- [ ] **Step 6: Lint, CI, commit**

Run: `make lint && make ci-local`
Expected: clean, coverage still ≥ 90% with the command measured, `✅ All CI checks passed!`

```bash
git add src/nichiyou_daiku/cli/commands/drawing.py pyproject.toml tests/cli/commands/test_drawing.py
git commit -m "refactor(cli): Leave only I/O in the drawing command"
```

---

### Task 5: Docs and final check

**Files:**
- Modify: `README.md` (project structure listing under `shell/`)
- Modify: `docs/superpowers/specs/2026-10-11-calc-display-separation-design.md` (status line)
- Modify (local, not committed): `CLAUDE.md` (project structure under `shell/`)

**Interfaces:**
- Consumes: everything above
- Produces: nothing new

- [ ] **Step 1: Update the structure listings**

In `README.md`, change the `shell/` block of the project tree to:

```
│       └── shell/          # External integrations
│           ├── build123d_export.py
│           ├── drawing.py
│           ├── resources.py
│           ├── cutting.py
│           └── report_generator.py
```

In the local `CLAUDE.md`, add under `shell/`:

```
│           ├── cutting.py           # 木取り（定尺・刃厚・LumberPlan）
│           ├── drawing.py           # 図面（4ビューの配置、build123d必須）
```

In the spec, change `- ステータス: 設計済み（未実装）` to `- ステータス: 実装済み（ブランチ refactor/calc-display-separation）`.

- [ ] **Step 2: Compare everything once more**

Run:
```bash
.venv/bin/python /tmp/nd-m2-2/capture_reports.py /tmp/nd-m2-2/after-5
/tmp/nd-m2-2/capture_drawings.sh /tmp/nd-m2-2/after-5
.venv/bin/python /tmp/nd-m2-2/compare.py /tmp/nd-m2-2/before /tmp/nd-m2-2/after-5
```
Expected: `compared 54 files: identical`.

- [ ] **Step 3: Confirm the spec's completion conditions**

Run: `grep -nE "_optimize_cuts|class CutPlan" src/nichiyou_daiku/shell/report_generator.py; grep -nE "project_to_viewport|bounding_box" src/nichiyou_daiku/cli/commands/drawing.py; echo done`
Expected: only `done` is printed.

- [ ] **Step 4: CI and commit**

Run: `make ci-local`
Expected: `✅ All CI checks passed!`

```bash
git add README.md docs/superpowers/specs/2026-10-11-calc-display-separation-design.md
git commit -m "docs: List the cutting and drawing modules; mark M2-2 implemented"
```
