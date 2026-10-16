# Assembly Steps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `nichiyou-daiku steps design.nd` writes assembly instructions: a Markdown page and one image per step. Each image has an isometric view (earlier pieces grey, this step's black and named) and a view dimensioning where this step's pieces go. The order comes from an optional `steps { }` block in the `.nd` file.

**Architecture:**
- **DSL and model:** an optional `steps` block lists, per named step, the pieces it adds (`Model.steps`, checked in `Model.of`). Connections stay order-free.
- **Plan:** `core/assembly/steps.py` plans the steps without build123d. Each step gets the connections it makes, its kind (first / attach / sub-assembly / join), the part it shows, and the axis its dimension view looks from. Without a steps block, each step adds one piece.
- **Images:** `shell/instructions.py` draws each step. It runs OCCT's hidden-line removal with one shape per piece, so earlier and new pieces can be drawn apart. It reuses the drawing's chain dimensions, which now work over any subset of pieces and any axis view.
- **Command:** a `steps` CLI command writes `steps.md` and the PNGs.

**Tech Stack:** Python 3.13, Lark (DSL), pydantic, build123d/OCP (`HLRBRep_Algo`), cairosvg, click, pytest. Run commands with `uv run` from the repository root on branch `feat/assembly-steps`.

**Spec:** `docs/superpowers/specs/2026-10-16-assembly-steps-design.md` (Japanese; binding).

**How the code was checked:** every patch below was written and run in a scratch copy before this plan. In a fresh clone of this branch, applying each task's test patch and then its implementation patch passes `ruff format --check`, `ruff check`, `pyright` and the whole suite. Each task's tests fail before its implementation patch, as each step's `Expected:` says.

## Global Constraints

- **Order:** only the `steps` block carries assembly order. Connections mean the same in any order.
- **steps are optional:** without them, each step adds one piece. A hint to write a steps block is shown only when there are two or more steps, and as a hint, not a warning.
- **No prose:** the instructions are images and numbers only. A step's name is used only as its heading label (`Step 2 - Right frame (sub-assembly)`).
- **Messages:** code, comments, docstrings, docs and messages are in English. Comments are few and say why. Errors say what is wrong and how to fix it.
- **Dependencies:** `core/` does not import build123d. `shell/instructions.py` and `shell/drawing.py` need build123d and are not imported by `shell/__init__.py`. The CLI imports `shell/instructions.py` through `import_viz_module`.
- **Dimensions:** use the M4-3 machinery unchanged in look: JIS figures 2.5mm high, chain dimensions, the outside row with leaders, no text over lines.
- **Steps survive solving:** `Model.of` checks the steps, and `resolve_model` and the DSL transformer pass them on.
- **Plugin:** `bin/nichiyou-daiku` runs `steps` in the viz environment.
- **Patches:** apply each patch exactly with `git apply` from the repository root. Each one sits between the `git apply <<'EOF'` line and the closing `EOF` line.
- **Commits:** run `make check` before every commit and commit only if it passes: `make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log; [ $rc -eq 0 ] && git commit ...`.
- **Never commit:** dotfiles or `CLAUDE.md`.

## Review Focus

1. **Fonts in the CI container.** Label and figure sizes come from the font build123d finds, and the overlap tests measure real text. `make ci-local` must pass before merging.
2. **The CLI's default 5mm fillets.** The image tests draw with `fillet_radius=0`, while the CLI uses 5mm.
   - Filleted edges add many lines. Moving them one edge at a time took 334s for the shelf, so `_placed` moves each piece's edges as one compound (the shelf then takes about 8s either way).
   - `test_steps_writes_the_page_and_images_next_to_the_input` (Task 6) runs the CLI with its default fillets.
3. **Designs whose pieces are not all connected.** Each part is drawn on its own and planned as a sub-assembly, pinned by `test_unconnected_pieces_get_a_step_each` (Task 5).
4. **Connections that placement drops as contradictory.** They still group pieces into parts. Their fasteners are not counted, because counting reads `assembly.fasteners`. No test builds such a model; review the counting path.
5. **The dimension view's axis choice on unusual shapes.** It is checked on the shelf and on a chain whose connections run along all three axes (Task 3). For a step whose pieces overlap along every axis, the rules still pick one axis; review that the choice is reasonable.

---

### Task 1: Assembly steps in the model (`Step`, `Model.steps`)

**Files:**
- Modify: `src/nichiyou_daiku/core/model.py` (add `Step`, `connected_parts`, `_check_steps`; `Model.steps`; `Model.of(..., steps=())`)
- Test: `tests/core/test_model_steps.py` (new)

**Interfaces:**
- Consumes: `Model.of(pieces, connections, label)` as it is.
- Produces: `Step(name: str, pieces: tuple[str, ...])` (pydantic, frozen); `Model.steps: tuple[Step, ...] = ()`; `Model.of(pieces, connections, label=None, steps=())` raising `ValueError` with these messages: `Step '<name>' adds no pieces; name at least one`, `Step '<name>' names unknown piece '<id>'; did you mean '<close>'?`, `'<id>' is in steps '<a>' and '<b>'; keep it in one step`, `'<id>' is twice in step '<name>'; keep it in one step`, `steps leaves out <ids>; add them to a step`, `Step '<name>' leaves its pieces in <n> separate parts: split it into steps or connect the parts`; `connected_parts(pieces: Iterable[str], pairs: Iterable[tuple[str, str]]) -> list[frozenset[str]]` (pairs naming other pieces are ignored).

- [ ] **Step 1: Write the failing tests**

````bash
git apply <<'EOF'
diff --git a/tests/core/test_model_steps.py b/tests/core/test_model_steps.py
new file mode 100644
index 0000000..c9cb53b
--- /dev/null
+++ b/tests/core/test_model_steps.py
@@ -0,0 +1,95 @@
+"""Tests for a model's assembly steps and what is checked about them."""
+
+import pytest
+
+from nichiyou_daiku.core.model import Model, Step, connected_parts
+from nichiyou_daiku.dsl import parse_dsl
+
+# Two posts joined by a rail, and a block on the rail
+FRAME = parse_dsl(
+    "(post_a:2x4 =400)\n(post_b:2x4 =400)\n(rail:2x4 =224)\n(block:2x4 =100)\n"
+    "post_a -[BR<150 DB<0]- rail\n"
+    "post_b -[FR<150 TB<0]- rail\n"
+    "rail -[RF<50 BT<0]- block\n"
+)
+
+
+def _with_steps(*steps: Step) -> Model:
+    return Model.of(FRAME.pieces.values(), FRAME.connections.values(), steps=steps)
+
+
+def test_steps_are_kept_in_order():
+    steps = (
+        Step(name="Posts and rail", pieces=("post_a", "rail", "post_b")),
+        Step(name="Block", pieces=("block",)),
+    )
+    assert _with_steps(*steps).steps == steps
+
+
+def test_a_model_needs_no_steps():
+    assert Model.of(FRAME.pieces.values(), FRAME.connections.values()).steps == ()
+
+
+def test_every_piece_must_be_in_a_step():
+    with pytest.raises(ValueError, match="steps leaves out block; add them to a step"):
+        _with_steps(Step(name="Frame", pieces=("post_a", "rail", "post_b")))
+
+
+def test_unknown_piece_names_a_close_one():
+    with pytest.raises(
+        ValueError, match="Step 'Frame' names unknown piece 'rial'; did you mean 'rail'"
+    ):
+        _with_steps(Step(name="Frame", pieces=("post_a", "rial", "post_b", "block")))
+
+
+def test_a_piece_in_two_steps_is_an_error():
+    with pytest.raises(
+        ValueError, match="'rail' is in steps 'Frame' and 'Block'; keep it in one step"
+    ):
+        _with_steps(
+            Step(name="Frame", pieces=("post_a", "rail", "post_b")),
+            Step(name="Block", pieces=("block", "rail")),
+        )
+
+
+def test_a_piece_twice_in_one_step_is_an_error():
+    with pytest.raises(ValueError, match="'rail' is twice in step 'Frame'"):
+        _with_steps(
+            Step(name="Frame", pieces=("post_a", "rail", "post_b", "block", "rail"))
+        )
+
+
+def test_an_empty_step_is_an_error():
+    with pytest.raises(ValueError, match="Step 'Nothing' adds no pieces"):
+        _with_steps(
+            Step(name="Nothing", pieces=()),
+            Step(name="All", pieces=("post_a", "rail", "post_b", "block")),
+        )
+
+
+def test_a_step_leaving_its_pieces_apart_is_an_error():
+    # The two posts touch nothing but the rail, which comes later
+    with pytest.raises(
+        ValueError,
+        match="Step 'Posts' leaves its pieces in 2 separate parts: split it into "
+        "steps or connect the parts",
+    ):
+        _with_steps(
+            Step(name="Posts", pieces=("post_a", "post_b")),
+            Step(name="Rest", pieces=("rail", "block")),
+        )
+
+
+def test_a_step_may_start_a_separate_part():
+    # The block alone is a part of its own until the rail joins it
+    model = _with_steps(
+        Step(name="Post", pieces=("post_a",)),
+        Step(name="Block", pieces=("block",)),
+        Step(name="Rail", pieces=("rail", "post_b")),
+    )
+    assert [step.name for step in model.steps] == ["Post", "Block", "Rail"]
+
+
+def test_connected_parts_ignore_pairs_with_other_pieces():
+    parts = connected_parts(["a", "b", "c"], [("a", "b"), ("b", "z")])
+    assert sorted(sorted(part) for part in parts) == [["a", "b"], ["c"]]
EOF
````

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/core/test_model_steps.py -q`
Expected: collection error, `ImportError: cannot import name 'Step' from 'nichiyou_daiku.core.model'`

- [ ] **Step 3: Implement**

````bash
git apply <<'EOF'
diff --git a/src/nichiyou_daiku/core/model.py b/src/nichiyou_daiku/core/model.py
index 82d6aee..d816fa4 100644
--- a/src/nichiyou_daiku/core/model.py
+++ b/src/nichiyou_daiku/core/model.py
@@ -4,6 +4,7 @@ This module provides the main Model class that represents a complete
 woodworking project with pieces and their connections.
 """
 
+from difflib import get_close_matches
 from typing import Iterable
 
 from pydantic import BaseModel
@@ -12,6 +13,80 @@ from nichiyou_daiku.core.piece import Piece
 from nichiyou_daiku.core.connection import Connection
 
 
+class Step(BaseModel, frozen=True):
+    """An assembly step: the pieces added in it, and a name for its heading."""
+
+    name: str
+    pieces: tuple[str, ...]
+
+
+def connected_parts(
+    pieces: Iterable[str], pairs: Iterable[tuple[str, str]]
+) -> list[frozenset[str]]:
+    """The pieces grouped by the pairs that join them; pairs naming other
+    pieces are ignored.
+
+    Examples:
+        >>> sorted(sorted(part) for part in connected_parts("abc", [("a", "b")]))
+        [['a', 'b'], ['c']]
+    """
+    parent = {piece: piece for piece in pieces}
+
+    def root(piece: str) -> str:
+        while parent[piece] != piece:
+            piece = parent[piece]
+        return piece
+
+    for a, b in pairs:
+        if a in parent and b in parent:
+            parent[root(a)] = root(b)
+    parts: dict[str, set[str]] = {}
+    for piece in parent:
+        parts.setdefault(root(piece), set()).add(piece)
+    return [frozenset(part) for part in parts.values()]
+
+
+def _check_steps(
+    pieces: dict[str, Piece],
+    pairs: list[tuple[str, str]],
+    steps: tuple[Step, ...],
+) -> None:
+    """Raise what is wrong with the steps and how to fix it."""
+    step_of: dict[str, str] = {}
+    for step in steps:
+        if not step.pieces:
+            raise ValueError(f"Step '{step.name}' adds no pieces; name at least one")
+        for piece_id in step.pieces:
+            if piece_id not in pieces:
+                close = get_close_matches(piece_id, pieces, n=1)
+                hint = f"; did you mean '{close[0]}'?" if close else ""
+                raise ValueError(
+                    f"Step '{step.name}' names unknown piece '{piece_id}'{hint}"
+                )
+            if piece_id in step_of:
+                where = (
+                    f"twice in step '{step.name}'"
+                    if step_of[piece_id] == step.name
+                    else f"in steps '{step_of[piece_id]}' and '{step.name}'"
+                )
+                raise ValueError(f"'{piece_id}' is {where}; keep it in one step")
+            step_of[piece_id] = step.name
+    missing = [piece_id for piece_id in pieces if piece_id not in step_of]
+    if missing:
+        raise ValueError(f"steps leaves out {', '.join(missing)}; add them to a step")
+    placed: list[str] = []
+    for step in steps:
+        placed += step.pieces
+        parts = [
+            part for part in connected_parts(placed, pairs) if part & set(step.pieces)
+        ]
+        if len(parts) > 1:
+            raise ValueError(
+                f"Step '{step.name}' leaves its pieces in {len(parts)} separate "
+                "parts: split it into steps or connect the parts"
+            )
+
+
 class Model(BaseModel, frozen=True):
     """Complete model of a woodworking project.
 
@@ -21,6 +96,7 @@ class Model(BaseModel, frozen=True):
     Attributes:
         pieces: Dictionary mapping piece IDs to Piece objects
         connections: Dictionary mapping (base_id, target_id) to Connection objects
+        steps: The assembly steps in order; empty when none are declared
 
     Examples:
         >>> from nichiyou_daiku.core.piece import Piece, PieceType
@@ -65,6 +141,7 @@ class Model(BaseModel, frozen=True):
     pieces: dict[str, Piece]
     connections: dict[tuple[str, str], Connection]
     label: str | None = None
+    steps: tuple[Step, ...] = ()
 
     @property
     def has_unknowns(self) -> bool:
@@ -80,6 +157,7 @@ class Model(BaseModel, frozen=True):
         pieces: Iterable[Piece],
         connections: Iterable[Connection],
         label: str | None = None,
+        steps: Iterable[Step] = (),
     ) -> "Model":
         """Create a Model instance from pieces and connections.
 
@@ -88,6 +166,9 @@ class Model(BaseModel, frozen=True):
         Args:
             pieces: Iterable of Piece objects
             connections: Iterable of Connection objects
+            label: Name of the model
+            steps: Assembly steps; when given, every piece is in exactly one
+                and no step leaves its pieces in separate parts
 
         Returns:
             New Model instance
@@ -155,4 +236,9 @@ class Model(BaseModel, frozen=True):
                 )
             connections_dict[key] = conn
 
-        return cls(pieces=pieces_dict, connections=connections_dict, label=label)
+        steps = tuple(steps)
+        if steps:
+            _check_steps(pieces_dict, list(connections_dict), steps)
+        return cls(
+            pieces=pieces_dict, connections=connections_dict, label=label, steps=steps
+        )
EOF
````

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/core/test_model_steps.py src/nichiyou_daiku/core/model.py --doctest-modules -q`
Expected: `13 passed`

- [ ] **Step 5: Commit**

```bash
make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log
[ $rc -eq 0 ] && git add src/nichiyou_daiku/core/model.py tests/core/test_model_steps.py && git commit -m "feat: Let a model carry its assembly steps

Each step names the pieces it adds; Model.of checks that every piece
is in exactly one step and that no step leaves its pieces apart."
```

---
### Task 2: The `steps` block in the DSL

**Files:**
- Modify: `src/nichiyou_daiku/dsl/grammar.py` (`steps_def`, `step_def`)
- Modify: `src/nichiyou_daiku/dsl/transformer.py` (`steps_def`, `step_def`; `start` passes the steps and reports their errors at the block; a piece named `steps` is refused)
- Modify: `src/nichiyou_daiku/core/resolve.py` (keep `steps` when solving unknowns)
- Modify: `docs/dsl-specification.md` (table of contents, basic structure, new "Assembly Steps" section with a complete `nd` example, EBNF, semantic errors)
- Test: `tests/dsl/test_steps.py` (new)

**Interfaces:**
- Consumes: Task 1's `Step`, `Model.of(..., steps=...)`.
- Produces: `parse_dsl` returns models with `steps`; a wrong block raises `DSLSemanticError` at the block's line; `steps` is a reserved word.

- [ ] **Step 1: Write the failing tests**

````bash
git apply <<'EOF'
diff --git a/tests/dsl/test_steps.py b/tests/dsl/test_steps.py
new file mode 100644
index 0000000..ec425f2
--- /dev/null
+++ b/tests/dsl/test_steps.py
@@ -0,0 +1,73 @@
+"""Tests for the steps block of the DSL."""
+
+from pathlib import Path
+
+import pytest
+
+from nichiyou_daiku.core.model import Step
+from nichiyou_daiku.dsl import DSLSemanticError, DSLSyntaxError, parse_dsl
+
+ROOT = Path(__file__).parents[2]
+FRAME = (
+    "(post_a:2x4 =400)\n(post_b:2x4 =400)\n(rail:2x4 =224)\n(block:2x4 =100)\n"
+    "post_a -[BR<150 DB<0]- rail\n"
+    "post_b -[FR<150 TB<0]- rail\n"
+    "rail -[RF<50 BT<0]- block\n"
+)
+STEPS = 'steps {\n  "Frame": post_a, rail, post_b\n  "Block": block\n}\n'
+
+
+def test_steps_block_lists_the_pieces_of_each_step():
+    model = parse_dsl(FRAME + STEPS)
+    assert model.steps == (
+        Step(name="Frame", pieces=("post_a", "rail", "post_b")),
+        Step(name="Block", pieces=("block",)),
+    )
+
+
+def test_steps_block_may_come_before_the_pieces():
+    assert parse_dsl(STEPS + FRAME).steps == parse_dsl(FRAME + STEPS).steps
+
+
+def test_a_file_without_steps_has_none():
+    assert parse_dsl(FRAME).steps == ()
+
+
+def test_only_one_steps_block_is_allowed():
+    with pytest.raises(DSLSemanticError, match="Only one steps block is allowed"):
+        parse_dsl(FRAME + STEPS + STEPS)
+
+
+def test_a_wrong_steps_block_is_reported_where_it_is():
+    source = FRAME + 'steps {\n  "Frame": post_a, rail, post_b\n}\n'
+    with pytest.raises(DSLSemanticError, match="steps leaves out block") as error:
+        parse_dsl(source)
+    assert error.value.line == 8
+
+
+def test_unknown_piece_in_a_step_names_a_close_one():
+    source = FRAME + 'steps {\n  "Frame": post_a, rial, post_b, block\n}\n'
+    with pytest.raises(DSLSemanticError, match="did you mean 'rail'"):
+        parse_dsl(source)
+
+
+def test_a_step_needs_a_piece():
+    with pytest.raises(DSLSyntaxError):
+        parse_dsl(FRAME + 'steps {\n  "Frame":\n}\n')
+
+
+def test_steps_cannot_name_a_piece():
+    with pytest.raises(DSLSemanticError, match="'steps' names the steps block"):
+        parse_dsl("(steps:2x4 =400)\n")
+
+
+def test_steps_survive_solving_unknowns():
+    source = (ROOT / "examples" / "nd_files" / "simple_table_unknowns.nd").read_text()
+    pieces = [
+        line.split(":")[0].lstrip("(")
+        for line in source.splitlines()
+        if line.startswith("(")
+    ]
+    model = parse_dsl(source + 'steps {\n  "All": ' + ", ".join(pieces) + "\n}\n")
+    assert model.pieces["apron_front"].length == 622.0
+    assert model.steps == (Step(name="All", pieces=tuple(pieces)),)
EOF
````

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/dsl/test_steps.py -q`
Expected: `7 failed, 2 passed` (the block is a syntax error; the two that pass are the file without steps and the empty step, a syntax error either way)

- [ ] **Step 3: Implement**

````bash
git apply <<'EOF'
diff --git a/docs/dsl-specification.md b/docs/dsl-specification.md
index 358c43e..ba6e897 100644
--- a/docs/dsl-specification.md
+++ b/docs/dsl-specification.md
@@ -11,6 +11,7 @@ The nichiyou-daiku DSL (`.nd` files) is a domain-specific language for concisely
 - [Piece Definition](#piece-definition)
 - [Connection Definition](#connection-definition)
 - [Connection Types](#connection-types)
+- [Assembly Steps](#assembly-steps)
 - [Complete Examples](#complete-examples)
 - [CLI Tools](#cli-tools)
 - [Grammar (EBNF)](#grammar-ebnf)
@@ -23,6 +24,7 @@ An `.nd` file consists of the following elements:
 2. **Variable Definitions** - Named numbers for lengths and offsets (defined before use)
 3. **Piece Definitions** - Lumber piece declarations
 4. **Connection Definitions** - Connections between pieces (a piece must be defined before a connection refers to it)
+5. **Steps** (optional) - The order to assemble the pieces in, as one `steps { }` block
 
 ```text
 // Comment
@@ -450,6 +452,31 @@ post -[FL<100 BT<0 S(3.5, 50)]- rail_low
 post -[BT<0 FT<0 S(Coarse:3.8x57)]- cleat
 ```
 
+## Assembly Steps
+
+An optional `steps` block says in which order the pieces are put together, for the instructions written by `nichiyou-daiku steps`. Each step has a name, used only as its heading, and the pieces it adds. The connections keep their meaning and can still be written in any order; only this block is about order.
+
+```nd
+// Shelf with dowel connections, assembled in two steps
+(left_side:2x4 =800)
+(right_side:2x4 =800)
+(shelf:2x4 =600)
+
+left_side -[BL<300 DL<0 D(:8x30)]- shelf
+right_side -[FL<300 TL<0 D(:8x30)]- shelf
+
+steps {
+  "Left side and shelf": left_side, shelf
+  "Right side": right_side
+}
+```
+
+- At most one `steps` block, anywhere in the file. `steps` names the block, so it cannot name a piece or a variable.
+- Every piece is in exactly one step, and every step names at least one piece, separated by commas.
+- A connection is made in the step that adds the later of its two pieces (or in the step that adds both).
+- A step whose pieces touch nothing built before builds a **sub-assembly**; a step whose pieces bring two or more built parts together **joins** them. A step may not leave its own pieces in separate parts: split it into steps or connect the parts.
+- Without a `steps` block, `nichiyou-daiku steps` adds one piece per step: the first piece declared and the first piece touching it, then the first piece (in declaration order) touching what is built, starting a new part with the next declared piece when none touches.
+
 ## Complete Examples
 
 ### Corner Joint
@@ -686,7 +713,10 @@ Draws one square PNG (default 1400px, at least 400px) for checking a design by e
 
 ```ebnf
 start           = statement+
-statement       = piece_def | connection_def | var_def
+statement       = piece_def | connection_def | var_def | steps_def
+
+steps_def       = "steps" "{" step_def+ "}"
+step_def        = ESCAPED_STRING ":" piece_ref ("," piece_ref)*
 
 var_def         = CNAME "=" expr
 expr            = term (("+" | "-") term)*
@@ -751,6 +781,8 @@ DSLSemanticError: Duplicate piece ID: leg_1
 DSLSemanticError: Duplicate connection between 'a' and 'b': only one connection per piece pair is supported
 DSLSemanticError: Undefined variable 'W' (define it before it is used)
 DSLSemanticError: Variable 'W' is already defined
+DSLSemanticError: steps leaves out shelf_4; add them to a step
+DSLSemanticError: Step 'Posts' leaves its pieces in 2 separate parts: split it into steps or connect the parts
 ```
 
 ### Validation Errors
diff --git a/src/nichiyou_daiku/core/resolve.py b/src/nichiyou_daiku/core/resolve.py
index 91f201b..35c8efd 100644
--- a/src/nichiyou_daiku/core/resolve.py
+++ b/src/nichiyou_daiku/core/resolve.py
@@ -93,7 +93,10 @@ def resolve_model(model: Model) -> Model:
         except ValidationError as error:
             raise ResolutionError(_messages(error), connection=key) from error
     return Model.of(
-        pieces=list(pieces.values()), connections=connections, label=model.label
+        pieces=list(pieces.values()),
+        connections=connections,
+        label=model.label,
+        steps=model.steps,
     )
 
 
diff --git a/src/nichiyou_daiku/dsl/grammar.py b/src/nichiyou_daiku/dsl/grammar.py
index c577692..6d9b91b 100644
--- a/src/nichiyou_daiku/dsl/grammar.py
+++ b/src/nichiyou_daiku/dsl/grammar.py
@@ -7,7 +7,11 @@ PIECE_TYPE_NAMES = sorted(piece_type.value for piece_type in PieceType)
 GRAMMAR = r"""
 start: statement+
 
-statement: piece_def | connection_def | var_def
+statement: piece_def | connection_def | var_def | steps_def
+
+// Assembly steps: each names the pieces it adds, in the order they are built
+steps_def: "steps" "{" step_def+ "}"
+step_def: ESCAPED_STRING ":" piece_ref ("," piece_ref)*
 
 // Variables and arithmetic: a variable must be defined before it is used
 var_def: CNAME "=" sum
diff --git a/src/nichiyou_daiku/dsl/transformer.py b/src/nichiyou_daiku/dsl/transformer.py
index 94a300d..5304238 100644
--- a/src/nichiyou_daiku/dsl/transformer.py
+++ b/src/nichiyou_daiku/dsl/transformer.py
@@ -15,7 +15,7 @@ from nichiyou_daiku.core.connection import (
 )
 from nichiyou_daiku.core.geometry.face import Face
 from nichiyou_daiku.core.geometry.offset import FromMax, FromMin, Offset
-from nichiyou_daiku.core.model import Model
+from nichiyou_daiku.core.model import Model, Step
 from nichiyou_daiku.core.piece import Piece, PieceType
 from nichiyou_daiku.core.resolve import ResolutionError, resolve_model
 from nichiyou_daiku.core.screw import as_spec as as_screw_spec
@@ -50,6 +50,8 @@ class DSLTransformer(Transformer):
         # Where pieces and connections are written, for errors found once the
         # whole model is known
         self.positions: dict[str | tuple[str, str], tuple[int | None, int | None]] = {}
+        self.steps: list[Step] | None = None
+        self.steps_position: tuple[int | None, int | None] = (None, None)
 
     # =========================================================================
     # Entry points
@@ -57,10 +59,16 @@ class DSLTransformer(Transformer):
 
     def start(self, items: list[Any]) -> Model:
         """Transform the start rule into a Model with its unknowns resolved."""
-        model = Model.of(
-            pieces=list(self.pieces.values()),
-            connections=self.connections.values(),
-        )
+        try:
+            model = Model.of(
+                pieces=list(self.pieces.values()),
+                connections=self.connections.values(),
+                steps=self.steps or (),
+            )
+        except ValueError as error:
+            # Pieces and connections were checked as they were read, so what
+            # is left is the steps block
+            raise DSLSemanticError(str(error), *self.steps_position) from error
         try:
             return resolve_model(model)
         except ResolutionError as error:
@@ -130,6 +138,25 @@ class DSLTransformer(Transformer):
         self._register_piece(piece)
         self.positions[piece.id] = _position(meta)
 
+    # =========================================================================
+    # Assembly steps
+    # =========================================================================
+
+    @v_args(meta=True)
+    def steps_def(self, meta: Meta, items: list[Step]) -> None:
+        """Keep the steps; they are checked once every piece is known."""
+        if self.steps is not None:
+            raise DSLSemanticError(
+                "Only one steps block is allowed; merge them into one"
+            )
+        self.steps = items
+        self.steps_position = _position(meta)
+
+    def step_def(self, items: list[Any]) -> Step:
+        """Transform one step: its name and the pieces it adds."""
+        name, *piece_ids = items
+        return Step(name=self._unescape_string(name), pieces=tuple(piece_ids))
+
     def _length_from_props(self, props: dict[str, Any]) -> float:
         """Extract the piece length from JSON properties."""
         if "length" not in props:
@@ -144,6 +171,10 @@ class DSLTransformer(Transformer):
 
     def _register_piece(self, piece: Piece) -> None:
         """Register a piece, checking for duplicates."""
+        if piece.id == "steps":
+            raise DSLSemanticError(
+                "'steps' names the steps block and cannot name a piece; rename the piece"
+            )
         if piece.id in self.pieces:
             raise DSLSemanticError(f"Duplicate piece ID: {piece.id}")
         self.pieces[piece.id] = piece
EOF
````

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/dsl/test_steps.py -q`
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log
[ $rc -eq 0 ] && git add src/nichiyou_daiku/dsl/grammar.py src/nichiyou_daiku/dsl/transformer.py src/nichiyou_daiku/core/resolve.py docs/dsl-specification.md tests/dsl/test_steps.py && git commit -m "feat: Declare assembly steps in a steps block

The block names the pieces each step adds, anywhere in the file; its
mistakes are reported where it is, and the steps survive solving the
unknowns."
```

---
### Task 3: Planning the steps (`core/assembly/steps.py`)

**Files:**
- Create: `src/nichiyou_daiku/core/assembly/steps.py`
- Modify: `skills/design/examples/two-tier-shelf.nd` (its `steps` block; the tests read it)
- Test: `tests/core/test_assembly_steps.py` (new)

**Interfaces:**
- Consumes: Task 1's `connected_parts`, `Model.steps`; `placement.edge_axis(rotation, bound)`; `Pose.bounds`, `Pose.rotation_matrix()`.
- Produces: `plan_steps(assembly: Assembly) -> StepPlan`; `StepPlan(declared: bool, steps: tuple[PlannedStep, ...])`; `PlannedStep(number: int, name: str | None, pieces: tuple[str, ...], connections: tuple[tuple[str, str], ...], kind: Literal['first', 'attach', 'sub-assembly', 'join'], shown: tuple[str, ...], view: tuple[int, int])` (`view` = world axis 0/1/2 and side +1/-1); private `_view(assembly, pieces, connections, shown) -> tuple[int, int]` (tested directly).

- [ ] **Step 1: Write the failing tests**

````bash
git apply <<'EOF'
diff --git a/tests/core/test_assembly_steps.py b/tests/core/test_assembly_steps.py
new file mode 100644
index 0000000..060a82e
--- /dev/null
+++ b/tests/core/test_assembly_steps.py
@@ -0,0 +1,145 @@
+"""Tests for planning the assembly steps."""
+
+from pathlib import Path
+
+import pytest
+
+from nichiyou_daiku.core.assembly import Assembly
+from nichiyou_daiku.core.assembly.steps import _view, plan_steps
+from nichiyou_daiku.dsl import parse_dsl
+
+SHELF = (
+    Path(__file__).parents[2] / "skills" / "design" / "examples" / "two-tier-shelf.nd"
+).read_text()
+# The example builds the side frames, joins them, then the shelf and the top
+SHELF_WITHOUT_STEPS = SHELF[: SHELF.index("steps {")]
+# Edges along z (posts to rail), y (rail to block) and x (block to cap)
+CHAIN = (
+    "(post_a:2x4 =400)\n(post_b:2x4 =400)\n(rail:2x4 =224)\n(block:2x4 =100)\n"
+    "(cap:2x4 =60)\n"
+    "post_a -[BR<150 DB<0]- rail\n"
+    "post_b -[FR<150 TB<0]- rail\n"
+    "rail -[RF<50 BT<0]- block\n"
+    "block -[RF<10 BT<0]- cap\n"
+)
+
+
+@pytest.fixture(scope="module")
+def shelf() -> Assembly:
+    return Assembly.of(parse_dsl(SHELF))
+
+
+@pytest.fixture(scope="module")
+def plan(shelf):
+    return plan_steps(shelf)
+
+
+def test_declared_steps_keep_their_names_and_pieces(plan):
+    assert plan.declared
+    assert [step.name for step in plan.steps] == [
+        "Left frame",
+        "Right frame",
+        "Join",
+        "Shelf",
+        "Top",
+    ]
+    assert plan.steps[3].pieces == ("shelf_1", "shelf_2", "shelf_3", "shelf_4")
+    assert [step.number for step in plan.steps] == [1, 2, 3, 4, 5]
+
+
+def test_step_kinds(plan):
+    # The right frame is built apart, then the aprons join the two frames
+    assert [step.kind for step in plan.steps] == [
+        "first",
+        "sub-assembly",
+        "join",
+        "attach",
+        "attach",
+    ]
+
+
+def test_each_connection_is_made_once_when_its_later_piece_goes_on(plan, shelf):
+    made = [key for step in plan.steps for key in step.connections]
+    assert sorted(made) == sorted(shelf.model.connections)
+    # Pieces of the same step are joined in that step
+    assert ("leg_1", "apron_upper_left") in plan.steps[0].connections
+    # The front and back aprons join the legs of both frames
+    assert len(plan.steps[2].connections) == 8
+
+
+def test_a_step_shows_the_part_it_leaves(plan):
+    assert plan.steps[1].shown == (
+        "leg_2",
+        "leg_4",
+        "apron_upper_right",
+        "apron_lower_right",
+    )
+    assert len(plan.steps[2].shown) == 12
+    assert len(plan.steps[4].shown) == 22
+
+
+def test_frames_are_seen_from_the_side_and_boards_from_above(plan):
+    # (axis, side): 0 = x, 2 = z
+    assert [step.view for step in plan.steps] == [
+        (0, 1),
+        (0, 1),
+        (0, 1),
+        (2, 1),
+        (2, 1),
+    ]
+
+
+def test_without_steps_each_step_adds_one_piece():
+    plan = plan_steps(Assembly.of(parse_dsl(SHELF_WITHOUT_STEPS)))
+    assert not plan.declared
+    assert plan.steps[0].name is None
+    # The first piece and the first piece touching it, then whatever touches
+    # what is built, in declaration order
+    assert [step.pieces for step in plan.steps[:4]] == [
+        ("leg_1", "apron_upper_front"),
+        ("leg_2",),
+        ("apron_upper_left",),
+        ("leg_3",),
+    ]
+    assert len(plan.steps) == 21
+
+
+def test_without_steps_unconnected_pieces_start_new_parts():
+    plan = plan_steps(Assembly.of(parse_dsl("(a:2x4 =400)\n(b:2x4 =400)\n")))
+    assert [step.pieces for step in plan.steps] == [("a",), ("b",)]
+    assert [step.kind for step in plan.steps] == ["first", "sub-assembly"]
+
+
+def test_a_single_piece_is_one_step():
+    plan = plan_steps(Assembly.of(parse_dsl("(post:2x4 =400)")))
+    assert [step.pieces for step in plan.steps] == [("post",)]
+
+
+def test_view_avoids_every_measured_axis(shelf):
+    # The apron is placed along z (up the legs), the shelf board along x
+    view = _view(
+        shelf,
+        ("apron_lower_front", "shelf_1"),
+        (("leg_1", "apron_lower_front"), ("apron_lower_front", "shelf_1")),
+        tuple(shelf.model.pieces),
+    )
+    assert view[0] == 1
+
+
+def test_view_looks_from_where_the_rest_hides_the_new_piece_least(shelf):
+    pieces = tuple(shelf.model.pieces)
+    # The back apron hides the front one from -y, and the other way round
+    assert _view(
+        shelf, ("apron_lower_front",), (("leg_1", "apron_lower_front"),), pieces
+    ) == (1, 1)
+    assert _view(
+        shelf, ("apron_lower_back",), (("leg_3", "apron_lower_back"),), pieces
+    ) == (1, -1)
+
+
+def test_view_ignores_the_measured_axes_when_they_are_all_three():
+    assembly = Assembly.of(parse_dsl(CHAIN))
+    pieces, shown = ("rail", "block", "cap"), tuple(assembly.model.pieces)
+    assert _view(assembly, pieces, tuple(assembly.model.connections), shown) == _view(
+        assembly, pieces, (), shown
+    )
EOF
````

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/core/test_assembly_steps.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'nichiyou_daiku.core.assembly.steps'`

- [ ] **Step 3: Implement**

````bash
git apply <<'EOF'
diff --git a/skills/design/examples/two-tier-shelf.nd b/skills/design/examples/two-tier-shelf.nd
index a588788..93fe141 100644
--- a/skills/design/examples/two-tier-shelf.nd
+++ b/skills/design/examples/two-tier-shelf.nd
@@ -124,3 +124,14 @@ apron_lower_front -[RF<0 BT<0 D(:8x30)]- shelf_1
 apron_lower_front -[RF<111 BT<0 D(:8x30)]- shelf_2
 apron_lower_front -[RF<222 BT<0 D(:8x30)]- shelf_3
 apron_lower_front -[RF<333 BT<0 D(:8x30)]- shelf_4
+
+// ============================================
+// Assembly: the side frames, the aprons joining them, the shelf, the top
+// ============================================
+steps {
+  "Left frame":  leg_1, leg_3, apron_upper_left, apron_lower_left
+  "Right frame": leg_2, leg_4, apron_upper_right, apron_lower_right
+  "Join":        apron_upper_front, apron_upper_back, apron_lower_front, apron_lower_back
+  "Shelf":       shelf_1, shelf_2, shelf_3, shelf_4
+  "Top":         top_1, top_2, top_3, top_4, top_5, top_6
+}
diff --git a/src/nichiyou_daiku/core/assembly/steps.py b/src/nichiyou_daiku/core/assembly/steps.py
new file mode 100644
index 0000000..638a454
--- /dev/null
+++ b/src/nichiyou_daiku/core/assembly/steps.py
@@ -0,0 +1,198 @@
+"""Assembly steps: the pieces each step adds, the connections it makes, what
+kind of step it is, and the direction its dimension view looks from.
+
+Free of build123d. A model's ``steps`` give the order; without them each
+step adds one piece.
+"""
+
+from typing import Literal
+
+from pydantic import BaseModel
+
+from nichiyou_daiku.core.geometry import Point3D
+from nichiyou_daiku.core.model import Model, connected_parts
+from nichiyou_daiku.core.placement import edge_axis
+
+from .builder import Assembly
+
+StepKind = Literal["first", "attach", "sub-assembly", "join"]
+"""first: the first step. sub-assembly: builds a part apart from everything
+built so far. join: brings two or more parts together. attach: adds to one."""
+
+# Tie-break for the dimension view: from above, then the front, then the side
+_AXIS_PREFERENCE = (2, 1, 0)
+
+
+class PlannedStep(BaseModel, frozen=True):
+    """One step of the assembly.
+
+    Attributes:
+        number: 1-based position
+        name: The name in the steps block; None when there is no steps block
+        pieces: The pieces this step adds
+        connections: The connections it makes, as model connection keys
+        kind: What the step does to the parts built so far
+        shown: The pieces of the part it leaves, in model order
+        view: World axis (0, 1, 2) and side (+1, -1) the dimension view
+            looks from
+    """
+
+    number: int
+    name: str | None
+    pieces: tuple[str, ...]
+    connections: tuple[tuple[str, str], ...]
+    kind: StepKind
+    shown: tuple[str, ...]
+    view: tuple[int, int]
+
+
+class StepPlan(BaseModel, frozen=True):
+    """The steps, and whether the model declared them."""
+
+    declared: bool
+    steps: tuple[PlannedStep, ...]
+
+
+def _one_piece_steps(model: Model) -> list[tuple[str, ...]]:
+    """Without a steps block: start with the first piece and the first piece
+    touching it, then add the first piece (in declaration order) touching
+    what is built; when none does, start a new part the same way."""
+    order = list(model.pieces)
+    touching: dict[str, set[str]] = {piece_id: set() for piece_id in order}
+    for a, b in model.connections:
+        touching[a].add(b)
+        touching[b].add(a)
+    placed: set[str] = set()
+    steps: list[tuple[str, ...]] = []
+    while len(placed) < len(order):
+        next_to_built = [p for p in order if p not in placed and touching[p] & placed]
+        if next_to_built:
+            new: tuple[str, ...] = (next_to_built[0],)
+        else:
+            start = next(p for p in order if p not in placed)
+            partner = next(
+                (p for p in order if p not in placed and p in touching[start]), None
+            )
+            new = (start,) if partner is None else (start, partner)
+        placed.update(new)
+        steps.append(new)
+    return steps
+
+
+def _rect(box: tuple[Point3D, Point3D], axis: int) -> tuple[float, float, float, float]:
+    """The box seen along ``axis``: its extent on the two other axes."""
+    low = [box[0].x, box[0].y, box[0].z]
+    high = [box[1].x, box[1].y, box[1].z]
+    u, v = (i for i in range(3) if i != axis)
+    return low[u], low[v], high[u], high[v]
+
+
+def _overlap(a: tuple[float, ...], b: tuple[float, ...]) -> float:
+    width = min(a[2], b[2]) - max(a[0], b[0])
+    height = min(a[3], b[3]) - max(a[1], b[1])
+    return width * height if width > 0 and height > 0 else 0.0
+
+
+def _area(rect: tuple[float, ...]) -> float:
+    return (rect[2] - rect[0]) * (rect[3] - rect[1])
+
+
+def _centre(box: tuple[Point3D, Point3D], axis: int) -> float:
+    return (getattr(box[0], "xyz"[axis]) + getattr(box[1], "xyz"[axis])) / 2
+
+
+def _view(
+    assembly: Assembly,
+    pieces: tuple[str, ...],
+    connections: tuple[tuple[str, str], ...],
+    shown: tuple[str, ...],
+) -> tuple[int, int]:
+    """The axis and side the step's dimension view looks from: across the
+    edges its connections are measured along, where the new pieces hide
+    each other least, from the side where the rest hides them least."""
+    poses, model = assembly.placement.poses, assembly.model
+    boxes = {p: poses[p].bounds(model.pieces[p]) for p in shown}
+    measured = {
+        edge_axis(poses[key[0]].rotation_matrix(), model.connections[key].base)
+        for key in connections
+    }
+    axes = [axis for axis in _AXIS_PREFERENCE if axis not in measured] or list(
+        _AXIS_PREFERENCE
+    )
+
+    def crowding(axis: int) -> tuple[float, float]:
+        rects = [_rect(boxes[p], axis) for p in pieces]
+        overlap = sum(
+            _overlap(a, b) for i, a in enumerate(rects) for b in rects[i + 1 :]
+        )
+        return overlap, -sum(_area(r) for r in rects)
+
+    axis = min(axes, key=crowding)  # min keeps the preferred axis on ties
+    others = [p for p in shown if p not in pieces]
+
+    def hidden(sign: int) -> float:
+        return sum(
+            _overlap(_rect(boxes[p], axis), _rect(boxes[o], axis))
+            for p in pieces
+            for o in others
+            if sign * _centre(boxes[o], axis) > sign * _centre(boxes[p], axis)
+        )
+
+    return axis, min((1, -1), key=hidden)
+
+
+def plan_steps(assembly: Assembly) -> StepPlan:
+    """The assembly steps of the model's steps block, or one piece per step
+    when it has none.
+
+    Examples:
+        >>> from nichiyou_daiku.dsl import parse_dsl
+        >>> model = parse_dsl(
+        ...     "(a:2x4 =400)\\n(b:2x4 =400)\\na -[TF<0 BD<0]- b\\n"
+        ... )
+        >>> plan = plan_steps(Assembly.of(model))
+        >>> plan.declared, [step.pieces for step in plan.steps]
+        (False, [('a', 'b')])
+    """
+    model = assembly.model
+    declared = bool(model.steps)
+    groups = (
+        [(step.name, step.pieces) for step in model.steps]
+        if declared
+        else [(None, pieces) for pieces in _one_piece_steps(model)]
+    )
+    step_of = {p: i for i, (_, pieces) in enumerate(groups) for p in pieces}
+    pairs = list(model.connections)
+    order = list(model.pieces)
+
+    planned = []
+    placed: list[str] = []
+    for i, (name, pieces) in enumerate(groups):
+        before = connected_parts(placed, pairs)
+        placed += pieces
+        part = next(
+            part for part in connected_parts(placed, pairs) if part & set(pieces)
+        )
+        joined = [old for old in before if old & part]
+        if i == 0:
+            kind: StepKind = "first"
+        elif not joined:
+            kind = "sub-assembly"
+        elif len(joined) > 1:
+            kind = "join"
+        else:
+            kind = "attach"
+        made = tuple(key for key in pairs if max(step_of[key[0]], step_of[key[1]]) == i)
+        shown = tuple(p for p in order if p in part)
+        planned.append(
+            PlannedStep(
+                number=i + 1,
+                name=name,
+                pieces=pieces,
+                connections=made,
+                kind=kind,
+                shown=shown,
+                view=_view(assembly, pieces, made, shown),
+            )
+        )
+    return StepPlan(declared=declared, steps=tuple(planned))
EOF
````

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/core/test_assembly_steps.py src/nichiyou_daiku/core/assembly/steps.py --doctest-modules -q`
Expected: `12 passed`

- [ ] **Step 5: Check**

Check that the sub-assembly rule can fail: temporarily change `elif not joined:` to `elif False:` in `plan_steps`, run `uv run pytest tests/core/test_assembly_steps.py -q -k kinds`, expect `1 failed`, then restore it and rerun: `1 passed`.

- [ ] **Step 6: Commit**

```bash
make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log
[ $rc -eq 0 ] && git add src/nichiyou_daiku/core/assembly/steps.py skills/design/examples/two-tier-shelf.nd tests/core/test_assembly_steps.py && git commit -m "feat: Plan the assembly steps

Which connections each step makes, whether it builds a sub-assembly or
joins parts, what it shows and where its dimension view looks from;
without a steps block each step adds one piece."
```

---
### Task 4: Chain dimensions for any part and any axis view

**Files:**
- Modify: `src/nichiyou_daiku/shell/views.py` (`axis_view(axis, sign) -> View`)
- Modify: `src/nichiyou_daiku/shell/dimensioning.py` (`_chain` becomes the public `chain_for`)
- Modify: `src/nichiyou_daiku/shell/drawing.py` (`_VIEW` knows the six axis views; `_dimension(chain, view, out, where, advice)` says where crowded values are and what to do; the outside row is sorted in page order, since a view can run its axis leftward or down)
- Test: `tests/shell/test_views.py`, `tests/shell/test_dimensioning.py`, `tests/shell/test_drawing.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `axis_view(axis: int, sign: int) -> View` (caption `from +x` ... `from -z`; z up, +y up when looking along z); `chain_for(view: str, axis: Axis, side: Side, bounds: dict[str, tuple[Point3D, Point3D]], pieces: dict[str, Piece], chosen: Sequence[str]) -> Chain` (the extent is the pieces in `bounds`); `_dimension(chain: Chain, view: _View, out: _Dimensions, where: str, advice: str) -> None` (`technical_drawing` passes `the <name> view` and `_crowded_advice(page_size)`, so its messages are unchanged).

- [ ] **Step 1: Write the failing tests**

````bash
git apply <<'EOF'
diff --git a/tests/shell/test_dimensioning.py b/tests/shell/test_dimensioning.py
index e1dfd51..067004c 100644
--- a/tests/shell/test_dimensioning.py
+++ b/tests/shell/test_dimensioning.py
@@ -6,7 +6,7 @@ import pytest
 
 from nichiyou_daiku.core.assembly import Assembly
 from nichiyou_daiku.dsl import parse_dsl
-from nichiyou_daiku.shell.dimensioning import Chain, _stops, chains, spread
+from nichiyou_daiku.shell.dimensioning import Chain, _stops, chain_for, chains, spread
 
 SHELF = (
     Path(__file__).parents[2] / "skills" / "design" / "examples" / "two-tier-shelf.nd"
@@ -114,3 +114,18 @@ def test_spread_keeps_order_and_never_overlaps():
 
 def test_spread_of_nothing_fits():
     assert spread([], [], 0.0, 1.0, 1.0) == ([], True)
+
+
+def test_a_chain_can_cover_some_pieces_only():
+    assembly = Assembly.of(parse_dsl(SHELF.read_text()))
+    frame = ["leg_1", "leg_3", "apron_upper_left", "apron_lower_left"]
+    bounds = {
+        p: assembly.placement.poses[p].bounds(assembly.model.pieces[p]) for p in frame
+    }
+    chain = chain_for(
+        "from +x", "y", "below", bounds, dict(assembly.model.pieces), frame
+    )
+    # The frame alone: 38 + 224 + 38 deep, the legs' faces as stops
+    assert [segment.text for segment in chain.segments] == ["38", "224", "38"]
+    assert chain.overall.text == "300"
+    assert chain.view == "from +x"
diff --git a/tests/shell/test_drawing.py b/tests/shell/test_drawing.py
index 48f84fb..bad2202 100644
--- a/tests/shell/test_drawing.py
+++ b/tests/shell/test_drawing.py
@@ -14,7 +14,11 @@ import nichiyou_daiku.shell.drawing as drawing_module  # noqa: E402
 from nichiyou_daiku.core.assembly import Assembly  # noqa: E402
 from nichiyou_daiku.dsl import parse_dsl  # noqa: E402
 from nichiyou_daiku.shell.build123d_export import assembly_to_build123d  # noqa: E402
-from nichiyou_daiku.shell.dimensioning import CrowdedDimensionsWarning  # noqa: E402
+from nichiyou_daiku.shell.dimensioning import (  # noqa: E402
+    Chain,
+    CrowdedDimensionsWarning,
+    Segment,
+)
 from nichiyou_daiku.shell.drawing import (  # noqa: E402
     FIRST,
     PAD,
@@ -22,7 +26,10 @@ from nichiyou_daiku.shell.drawing import (  # noqa: E402
     _arrow_points,
     _compose,
     _crowded_advice,
+    _Dimensions,
+    _dimension,
     _frame,
+    _View,
     technical_drawing,
 )
 
@@ -380,3 +387,26 @@ def test_crowded_values_warn_and_say_what_to_do():
     message = str(caught[0].message)
     assert "--page-size A2" in message
     assert "--no-dimensions" in message
+
+
+def test_values_keep_their_order_when_the_axis_runs_leftward():
+    # From +y, x grows to the left of the page, so the chain's stretches come
+    # in right to left; the values too small for their stretch must still go
+    # in the outside row in page order
+    stops = (0.0, 10.0, 25.0, 45.0, 300.0)
+    chain = Chain(
+        view="from +y",
+        axis="x",
+        side="below",
+        stops=stops,
+        segments=tuple(Segment(a, b, lumber=False) for a, b in zip(stops, stops[1:])),
+    )
+    view = _View("from +y", (0.0, 0.0), 0.2, (-60.0, 0.0, 0.0, 20.0), [], [])
+    out = _Dimensions()
+    _dimension(chain, view, out, "here", "Make room")
+    row = sorted(
+        (label for label in out.labels if label.text in {"10", "15", "20"}),
+        key=lambda label: label.centre[0],
+    )
+    assert [label.text for label in row] == ["20", "15", "10"]
+    assert out.crowded == []
diff --git a/tests/shell/test_views.py b/tests/shell/test_views.py
index de46803..db27039 100644
--- a/tests/shell/test_views.py
+++ b/tests/shell/test_views.py
@@ -6,7 +6,7 @@ import pytest
 
 from nichiyou_daiku.core.assembly import Assembly
 from nichiyou_daiku.dsl import parse_dsl
-from nichiyou_daiku.shell.views import VIEWS, project, visible_labels
+from nichiyou_daiku.shell.views import VIEWS, axis_view, project, visible_labels
 
 ROOT = Path(__file__).parents[2]
 SHELF = (ROOT / "skills" / "design" / "examples" / "two-tier-shelf.nd").read_text()
@@ -71,3 +71,23 @@ def test_labels_sit_on_their_piece():
             ]
             assert min(x for x, _ in corners) <= label.x <= max(x for x, _ in corners)
             assert min(y for _, y in corners) <= label.y <= max(y for _, y in corners)
+
+
+def test_axis_views_match_the_views_they_share_a_caption_with():
+    shared = {view.caption: view for view in VIEWS}
+    for axis in range(3):
+        for sign in (1, -1):
+            view = axis_view(axis, sign)
+            if view.caption in shared:
+                assert (view.origin, view.up) == (
+                    shared[view.caption].origin,
+                    shared[view.caption].up,
+                )
+
+
+def test_axis_views_look_from_their_side_with_z_up():
+    assert axis_view(0, -1).caption == "from -x"
+    assert axis_view(0, -1).origin == (-100.0, 0.0, 0.0)
+    assert axis_view(1, 1).up == (0, 0, 1)
+    # Looking along z, +y is up
+    assert axis_view(2, -1).up == (0, 1, 0)
EOF
````

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/shell/test_views.py tests/shell/test_dimensioning.py tests/shell/test_drawing.py -q`
Expected: collection errors: `ImportError: cannot import name 'axis_view'` and `cannot import name 'chain_for'`

- [ ] **Step 3: Implement**

````bash
git apply <<'EOF'
diff --git a/src/nichiyou_daiku/shell/dimensioning.py b/src/nichiyou_daiku/shell/dimensioning.py
index 23bae19..e5a0fca 100644
--- a/src/nichiyou_daiku/shell/dimensioning.py
+++ b/src/nichiyou_daiku/shell/dimensioning.py
@@ -93,7 +93,7 @@ def _is_lumber(
     return False
 
 
-def _chain(
+def chain_for(
     view: str,
     axis: Axis,
     side: Side,
@@ -101,6 +101,12 @@ def _chain(
     pieces: dict[str, Piece],
     chosen: Sequence[str],
 ) -> Chain:
+    """Chain dimensions along ``axis`` over the pieces in ``bounds`` (their
+    world boxes), stopping at both ends of the ``chosen`` ones.
+
+    ``pieces`` gives the lumber of the chosen pieces, so stretches that are
+    their width or thickness are marked as lumber.
+    """
     low = min(getattr(box[0], axis) for box in bounds.values())
     high = max(getattr(box[1], axis) for box in bounds.values())
     extents = [
@@ -145,11 +151,11 @@ def chains(assembly: Assembly) -> list[Chain]:
         if box[1].z >= top - _TOP_TOLERANCE_MM
     ]
     return [
-        _chain("from -y", "z", "left", bounds, pieces, list(pieces)),
-        _chain("from -y", "x", "below", bounds, pieces, upright),
-        _chain("from +x", "y", "below", bounds, pieces, upright),
-        _chain("from +z", "x", "below", bounds, pieces, top_layer),
-        _chain("from +z", "y", "left", bounds, pieces, top_layer),
+        chain_for("from -y", "z", "left", bounds, pieces, list(pieces)),
+        chain_for("from -y", "x", "below", bounds, pieces, upright),
+        chain_for("from +x", "y", "below", bounds, pieces, upright),
+        chain_for("from +z", "x", "below", bounds, pieces, top_layer),
+        chain_for("from +z", "y", "left", bounds, pieces, top_layer),
     ]
 
 
diff --git a/src/nichiyou_daiku/shell/drawing.py b/src/nichiyou_daiku/shell/drawing.py
index d172aa2..d33b163 100644
--- a/src/nichiyou_daiku/shell/drawing.py
+++ b/src/nichiyou_daiku/shell/drawing.py
@@ -39,7 +39,7 @@ from nichiyou_daiku.shell.dimensioning import (
     chains,
     spread,
 )
-from nichiyou_daiku.shell.views import VIEWS, project
+from nichiyou_daiku.shell.views import VIEWS, axis_view, project
 
 PAGE_SIZES = ("A4", "A3", "A2", "A1")
 
@@ -61,7 +61,10 @@ Point = tuple[float, float]
 Rect = tuple[float, float, float, float]
 """min x, min y, max x, max y on the page."""
 
-_VIEW = {view.caption: view for view in VIEWS}
+_VIEW = {
+    view.caption: view
+    for view in [*(axis_view(a, s) for a in range(3) for s in (1, -1)), *VIEWS]
+}
 _ISOMETRIC = "from +x +y +z"
 
 
@@ -263,9 +266,13 @@ def _crowded_advice(page_size: str) -> str:
     )
 
 
-def _dimension(chain: Chain, view: _View, out: _Dimensions, page_size: str) -> None:
+def _dimension(
+    chain: Chain, view: _View, out: _Dimensions, where: str, advice: str
+) -> None:
     """Draw one chain beside its view: extension lines, the chain with its
-    values (inside their stretch, else in a row with leaders), the overall."""
+    values (inside their stretch, else in a row with leaders), the overall.
+    Values that do not fit are reported as being in ``where``, with
+    ``advice`` on making room."""
     horizontal = chain.side == "below"
     levels = _levels(chain.side)
     edge = view.box[1] if horizontal else view.box[0]
@@ -325,6 +332,8 @@ def _dimension(chain: Chain, view: _View, out: _Dimensions, page_size: str) -> N
             elif not segment.lumber:
                 outside.append((segment.text, (a + b) / 2, length, across))
         if outside:
+            # A view can run the axis leftward or down; spread wants them in page order
+            outside.sort(key=lambda value: value[1])
             centres, fits = spread(
                 [middle for _, middle, _, _ in outside],
                 [length for _, _, length, _ in outside],
@@ -334,9 +343,8 @@ def _dimension(chain: Chain, view: _View, out: _Dimensions, page_size: str) -> N
             )
             if not fits:
                 out.crowded.append(
-                    f"{len(outside)} dimension values along {chain.axis} in the "
-                    f"{VIEW_NAMES[chain.view]} view do not fit beside their chain "
-                    f"and overlap. {_crowded_advice(page_size)}"
+                    f"{len(outside)} dimension values along {chain.axis} in "
+                    f"{where} do not fit beside their chain and overlap. {advice}"
                 )
             for (text, middle, _, across), centre in zip(outside, centres):
                 out.lines.append((at(middle, levels.line), at(middle, levels.bend)))
@@ -367,7 +375,13 @@ def _compose(part: Compound, assembly: Assembly | None, page_size: str) -> _Shee
     denominator, views = _layout(part, frame, title_block, bands=bool(found))
     dimensions = _Dimensions()
     for chain in found:
-        _dimension(chain, views[chain.view], dimensions, page_size)
+        _dimension(
+            chain,
+            views[chain.view],
+            dimensions,
+            f"the {VIEW_NAMES[chain.view]} view",
+            _crowded_advice(page_size),
+        )
     return _Sheet(frame, title_block, denominator, views, dimensions)
 
 
diff --git a/src/nichiyou_daiku/shell/views.py b/src/nichiyou_daiku/shell/views.py
index a702805..8cc7764 100644
--- a/src/nichiyou_daiku/shell/views.py
+++ b/src/nichiyou_daiku/shell/views.py
@@ -35,6 +35,17 @@ VIEWS = (
 )
 
 
+def axis_view(axis: int, sign: int) -> View:
+    """The view from the ``sign`` side of world ``axis`` (0, 1, 2 for x, y,
+    z): z is up, or +y when looking along z. The three that ``VIEWS`` also
+    has project the same way."""
+    origin = [0.0, 0.0, 0.0]
+    origin[axis] = 100.0 * sign
+    up = (0, 1, 0) if axis == 2 else (0, 0, 1)
+    caption = f"from {'+' if sign > 0 else '-'}{'xyz'[axis]}"
+    return View(caption, (origin[0], origin[1], origin[2]), up, 0, 0)
+
+
 class Label(NamedTuple):
     """A piece ID at a point of the viewport."""
 
EOF
````

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/shell/test_views.py tests/shell/test_dimensioning.py tests/shell/test_drawing.py -q`
Expected: `110 passed`

- [ ] **Step 5: Check**

Check that the page-order sort is what keeps the leftward values in order: temporarily delete the line `outside.sort(key=lambda value: value[1])` in `_dimension`, run `uv run pytest tests/shell/test_drawing.py -q -k leftward`, expect `1 failed` (`['10', '15', '20'] == ['20', '15', '10']`), then restore it and rerun: `1 passed`.

- [ ] **Step 6: Commit**

```bash
make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log
[ $rc -eq 0 ] && git add src/nichiyou_daiku/shell/views.py src/nichiyou_daiku/shell/dimensioning.py src/nichiyou_daiku/shell/drawing.py tests/shell/test_views.py tests/shell/test_dimensioning.py tests/shell/test_drawing.py && git commit -m "refactor: Draw chain dimensions over any part and any axis view

Chains can cover some pieces only and run along any axis view; values
in a leftward axis keep their page order, and the crowding message
says where and what to do."
```

---
### Task 5: Step images and the steps page (`shell/instructions.py`)

**Files:**
- Create: `src/nichiyou_daiku/shell/instructions.py`
- Modify: `src/nichiyou_daiku/shell/views.py` (`visible_labels(assembly, view, pieces=None)`: only those pieces are labelled and hide each other)
- Modify: `src/nichiyou_daiku/shell/resources.py` (`_hardware(assembly, connections=None)`: count only those connections' fasteners)
- Test: `tests/shell/test_instructions.py` (new)

**Interfaces:**
- Consumes: Task 3's `plan_steps`, `PlannedStep`, `StepPlan`; Task 4's `axis_view`, `chain_for`, `_dimension(..., where, advice)`; `drawing._levels`, `_text`, `_text_size`, `_arrow_points`, `_View`, `_Dimensions`.
- Produces: `step_image(assembly, part, step) -> StepImage` (`step`, `lines: dict[id, _PieceLines]` (iso lines per piece), `labels: dict[id, Rect]`, `view: View`, `dimensions: _Dimensions`, `svg: str`, `png(size) -> bytes`); `image_name(step, count) -> str` (`step-01.png`, three digits from 100 steps); `steps_markdown(assembly, plan, title) -> str`; `write_instructions(assembly, part, directory: Path, title: str, size: int = 1600) -> Instructions` (`files: list[Path]` with `steps.md` first, `declared: bool`, `crowded: list[str]`). SVG layers: `Before` (grey), `New` (black), `NewHidden` (dashed), `Dimensions`, `LabelGround` (white), `Text`.

- [ ] **Step 1: Write the failing tests**

````bash
git apply <<'EOF'
diff --git a/tests/shell/test_instructions.py b/tests/shell/test_instructions.py
new file mode 100644
index 0000000..76a2644
--- /dev/null
+++ b/tests/shell/test_instructions.py
@@ -0,0 +1,213 @@
+"""Tests for the assembly instructions: step images and the steps page."""
+
+from itertools import combinations
+from pathlib import Path
+
+import pytest
+
+pytest.importorskip("build123d")
+
+from nichiyou_daiku.core.assembly import Assembly  # noqa: E402
+from nichiyou_daiku.core.assembly.steps import plan_steps  # noqa: E402
+from nichiyou_daiku.dsl import parse_dsl  # noqa: E402
+from nichiyou_daiku.shell.build123d_export import assembly_to_build123d  # noqa: E402
+from nichiyou_daiku.shell.drawing import _arrow_points  # noqa: E402
+from nichiyou_daiku.shell.instructions import (  # noqa: E402
+    image_name,
+    step_image,
+    steps_markdown,
+    write_instructions,
+)
+
+SHELF = (
+    Path(__file__).parents[2] / "skills" / "design" / "examples" / "two-tier-shelf.nd"
+).read_text()
+CORNER = "(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n"
+# A third piece across the far end of b: two steps without a steps block
+THREE = CORNER + "(c:2x4 =400)\nb -[TF<0 BD<0]- c\n"
+# 39 slats 12.5mm apart up a 2m post, all in one step
+CROWDED = (
+    "(rail:2x4 =2000)\n"
+    + "".join(
+        f"(s{i}:2x2 =300)\nrail -[RF<{i * 50.5:g} BT<0]- s{i}\n" for i in range(39)
+    )
+    + 'steps {\n  "All": rail, '
+    + ", ".join(f"s{i}" for i in range(39))
+    + "\n}\n"
+)
+
+
+@pytest.fixture(scope="module")
+def shelf():
+    assembly = Assembly.of(parse_dsl(SHELF))
+    part = assembly_to_build123d(assembly, fillet_radius=0)
+    plan = plan_steps(assembly)
+    return assembly, plan, [step_image(assembly, part, step) for step in plan.steps]
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
+def _layer(svg: str, name: str) -> str:
+    return svg.split(f'id="{name}"', 1)[1].split("</g>", 1)[0]
+
+
+def _drawn(svg: str, layer: str) -> int:
+    body = _layer(svg, layer)
+    return body.count("<line") + body.count("<path")
+
+
+def test_this_steps_pieces_are_black_and_earlier_ones_grey(shelf):
+    _, plan, images = shelf
+    assert set(images[3].lines) == set(plan.steps[3].shown)
+    # The first step has nothing earlier: its grey layer holds the border only
+    border = 4
+    assert _drawn(images[0].svg, "Before") == border
+    assert _drawn(images[0].svg, "New") > 0
+    assert _drawn(images[3].svg, "Before") > border
+    assert _drawn(images[3].svg, "New") > 0
+
+
+def test_hidden_lines_are_drawn_for_this_steps_pieces_only(shelf):
+    _, plan, images = shelf
+    join = images[2]
+    assert any(join.lines[p].hidden for p in plan.steps[2].pieces)
+    assert 'id="NewHidden"' in join.svg
+
+
+def test_labels_name_this_steps_pieces_without_overlapping(shelf):
+    _, plan, images = shelf
+    top = images[4]
+    assert set(top.labels) == set(plan.steps[4].pieces)
+    for image in images:
+        assert set(image.labels) <= set(image.step.pieces)
+        boxes = list(image.labels.values())
+        assert [(a, b) for a, b in combinations(boxes, 2) if _overlap(a, b)] == []
+
+
+def test_pieces_not_drawn_hide_no_labels(shelf):
+    # The right frame is drawn alone; the left frame does not hide its aprons
+    _, _, images = shelf
+    assert {"apron_upper_right", "apron_lower_right"} <= set(images[1].labels)
+
+
+def test_dimension_view_shows_where_the_shelf_boards_go(shelf):
+    _, _, images = shelf
+    texts = [label.text for label in images[3].dimensions.labels]
+    assert texts.count("22") == 3
+    assert "600" in texts
+
+
+def test_frame_heights_are_dimensioned_from_the_side(shelf):
+    _, _, images = shelf
+    assert images[0].view.caption == "from +x"
+    texts = [label.text for label in images[0].dimensions.labels]
+    assert {"150", "453", "781", "224", "300"} <= set(texts)
+
+
+def test_dimension_values_touch_no_line_and_no_other_value(shelf):
+    _, _, images = shelf
+    for image in images:
+        out = image.dimensions
+        segments = list(out.lines)
+        for arrow in out.arrows:
+            a, b, c = _arrow_points(*arrow)
+            segments += [(a, b), (b, c), (c, a)]
+        boxes = [label.box for label in out.labels]
+        assert [
+            (box, s) for box in boxes for s in segments if _crosses(box, s)
+        ] == [], image.step.name
+        assert [(a, b) for a, b in combinations(boxes, 2) if _overlap(a, b)] == []
+        assert out.crowded == []
+
+
+def test_steps_page_lists_each_step_with_its_pieces_and_fasteners(shelf):
+    assembly, plan, _ = shelf
+    page = steps_markdown(assembly, plan, "two-tier-shelf")
+    assert page.startswith("# two-tier-shelf: assembly steps\n")
+    assert "## Step 1 - Left frame\n" in page
+    assert "## Step 2 - Right frame (sub-assembly)\n" in page
+    assert "## Step 3 - Join (join)\n" in page
+    assert "![Step 4](step-04.png)" in page
+    assert "| shelf_2 | 2x4 | 300 |" in page
+    first = page.split("## Step 2", 1)[0]
+    # Four connections, two dowels each
+    assert "| Dowel 8x30 | 8 |" in first
+    assert "No steps block" not in page
+
+
+def test_steps_page_without_steps_says_how_to_group_them():
+    assembly = Assembly.of(parse_dsl(THREE))
+    page = steps_markdown(assembly, plan_steps(assembly), "three")
+    assert "No steps block: each step adds one piece" in page
+    assert '`steps { "Frame": a, b, ... }`' in page
+    assert "## Step 1\n" in page
+    assert "## Step 2\n" in page
+
+
+def test_a_single_step_needs_no_word_about_grouping():
+    assembly = Assembly.of(parse_dsl(CORNER))
+    assert "No steps block" not in steps_markdown(
+        assembly, plan_steps(assembly), "corner"
+    )
+
+
+def test_write_instructions_writes_the_page_and_one_image_per_step(tmp_path):
+    assembly = Assembly.of(parse_dsl(CORNER))
+    part = assembly_to_build123d(assembly, fillet_radius=0)
+    result = write_instructions(assembly, part, tmp_path / "out", "corner", size=400)
+    assert [path.name for path in result.files] == ["steps.md", "step-01.png"]
+    assert (tmp_path / "out" / "step-01.png").read_bytes().startswith(b"\x89PNG")
+    assert not result.declared
+    assert result.crowded == []
+
+
+def test_unconnected_pieces_get_a_step_each(tmp_path):
+    # Two loose posts: each step draws its own part
+    assembly = Assembly.of(parse_dsl("(a:2x4 =400)\n(b:2x4 =400)\n"))
+    part = assembly_to_build123d(assembly, fillet_radius=0)
+    result = write_instructions(assembly, part, tmp_path, "loose", size=400)
+    assert [path.name for path in result.files] == [
+        "steps.md",
+        "step-01.png",
+        "step-02.png",
+    ]
+    assert "## Step 2 (sub-assembly)" in (tmp_path / "steps.md").read_text()
+
+
+def test_image_names_are_wide_enough_for_every_step(shelf):
+    _, plan, _ = shelf
+    assert image_name(plan.steps[2], 5) == "step-03.png"
+    assert image_name(plan.steps[2], 120) == "step-003.png"
+
+
+def test_crowded_values_say_to_split_the_step():
+    assembly = Assembly.of(parse_dsl(CROWDED))
+    part = assembly_to_build123d(assembly, fillet_radius=0)
+    image = step_image(assembly, part, plan_steps(assembly).steps[0])
+    assert image.dimensions.crowded
+    assert "step 1" in image.dimensions.crowded[0]
+    assert "Split the step" in image.dimensions.crowded[0]
EOF
````

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/shell/test_instructions.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'nichiyou_daiku.shell.instructions'`

- [ ] **Step 3: Implement**

````bash
git apply <<'EOF'
diff --git a/src/nichiyou_daiku/shell/instructions.py b/src/nichiyou_daiku/shell/instructions.py
new file mode 100644
index 0000000..5828103
--- /dev/null
+++ b/src/nichiyou_daiku/shell/instructions.py
@@ -0,0 +1,388 @@
+"""Assembly instructions: a Markdown page and one image per step, each an
+isometric view (earlier pieces grey, this step's black) beside a view
+dimensioning where this step's pieces go.
+
+Needs build123d, so ``nichiyou_daiku.shell`` does not import this module.
+"""
+
+import io
+import tempfile
+from dataclasses import dataclass, field
+from pathlib import Path
+
+import cairosvg
+from build123d import (
+    Compound,
+    Edge,
+    ExportSVG,
+    LineType,
+    Polygon,
+    Pos,
+    Shape,
+    Unit,
+    scale,
+)
+from build123d.topology import downcast
+from ezdxf.colors import RGB
+
+# OCP's classes live in a compiled module that pyright cannot read
+from OCP.BRepLib import BRepLib  # pyright: ignore[reportAttributeAccessIssue]
+from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt  # pyright: ignore[reportAttributeAccessIssue]
+from OCP.HLRAlgo import HLRAlgo_Projector  # pyright: ignore[reportAttributeAccessIssue]
+from OCP.HLRBRep import HLRBRep_Algo  # pyright: ignore[reportAttributeAccessIssue]
+from OCP.HLRBRep import HLRBRep_HLRToShape  # pyright: ignore[reportAttributeAccessIssue]
+from OCP.TopAbs import TopAbs_ShapeEnum  # pyright: ignore[reportAttributeAccessIssue]
+from OCP.TopExp import TopExp_Explorer  # pyright: ignore[reportAttributeAccessIssue]
+from OCP.TopoDS import TopoDS_Shape  # pyright: ignore[reportAttributeAccessIssue]
+
+from nichiyou_daiku.core.assembly import Assembly
+from nichiyou_daiku.core.assembly.steps import PlannedStep, StepPlan, plan_steps
+from nichiyou_daiku.shell.diagnostics import format_mm
+from nichiyou_daiku.shell.dimensioning import Axis, chain_for
+from nichiyou_daiku.shell.drawing import (
+    _arrow_points,
+    _Dimensions,
+    _dimension,
+    _levels,
+    _text,
+    _text_size,
+    _View,
+)
+from nichiyou_daiku.shell.resources import _hardware
+from nichiyou_daiku.shell.views import VIEWS, View, axis_view, project, visible_labels
+
+# Page mm of a step image: an isometric half and a dimensioned half. Small
+# enough that 2.5mm figures stay readable at the default 1600px.
+PAGE_WIDTH = 280.0
+PAGE_HEIGHT = 140.0
+MARGIN = 6.0
+HEADING = 10.0  # band at the top for the step's heading
+ISO_FILL = 0.9
+
+_ISOMETRIC = next(view for view in VIEWS if view.caption == "from +x +y +z")
+_KIND_MARKS = {"sub-assembly": " (sub-assembly)", "join": " (join)"}
+_SPLIT_ADVICE = "Split the step into steps that add fewer pieces"
+
+Rect = tuple[float, float, float, float]
+
+
+@dataclass
+class _PieceLines:
+    visible: list[Shape] = field(default_factory=list)
+    hidden: list[Shape] = field(default_factory=list)
+
+
+@dataclass
+class StepImage:
+    """What one step's image shows, in page mm, and its SVG."""
+
+    step: PlannedStep
+    lines: dict[str, _PieceLines]
+    """Isometric lines of each piece shown."""
+    labels: dict[str, Rect]
+    """Boxes of the labels naming this step's pieces."""
+    view: View
+    """The view dimensioning this step."""
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
+def _edges(shape: TopoDS_Shape) -> list[Shape]:
+    if shape.IsNull():
+        return []
+    edges: list[Shape] = []
+    explorer = TopExp_Explorer(shape, TopAbs_ShapeEnum.TopAbs_EDGE)
+    while explorer.More():
+        edge = downcast(explorer.Current())
+        # The projected edges have no 3D curves until they are built
+        BRepLib.BuildCurves3d_s(edge, 1e-5)
+        edges.append(Edge(edge))
+        explorer.Next()
+    return edges
+
+
+def _piece_lines(
+    shapes: dict[str, Compound], pieces: tuple[str, ...], view: View
+) -> dict[str, _PieceLines]:
+    """Each piece's visible and hidden lines from ``view``, with every piece
+    in ``pieces`` hiding the others. build123d's projection treats a part as
+    one shape, so this runs OCCT's hidden-line removal with one shape per
+    piece and reads the lines back per piece."""
+    algorithm = HLRBRep_Algo()
+    for piece_id in pieces:
+        algorithm.Add(shapes[piece_id].wrapped)
+    toward_viewer = gp_Dir(*view.origin)
+    axes = gp_Ax2(gp_Pnt(*view.origin), toward_viewer)
+    axes.SetYDirection(gp_Dir(*view.up))
+    algorithm.Projector(HLRAlgo_Projector(axes))
+    algorithm.Update()
+    algorithm.Hide()
+    to_shape = HLRBRep_HLRToShape(algorithm)
+    lines = {}
+    for piece_id in pieces:
+        shape = shapes[piece_id].wrapped
+        lines[piece_id] = _PieceLines(
+            visible=_edges(to_shape.VCompound(shape))
+            + _edges(to_shape.OutLineVCompound(shape))
+            + _edges(to_shape.Rg1LineVCompound(shape)),
+            hidden=_edges(to_shape.HCompound(shape))
+            + _edges(to_shape.OutLineHCompound(shape))
+            + _edges(to_shape.Rg1LineHCompound(shape)),
+        )
+    return lines
+
+
+def _bounds(lines: dict[str, _PieceLines]) -> Rect:
+    box = Compound(
+        children=[e for piece in lines.values() for e in piece.visible + piece.hidden]
+    ).bounding_box()
+    return box.min.X, box.min.Y, box.max.X, box.max.Y
+
+
+def _fit(bounds: Rect, area: Rect, fill: float) -> tuple[float, tuple[float, float]]:
+    """Scale and offset that centre ``bounds`` in ``area``, ``fill`` of it."""
+    width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
+    factor = fill * min((area[2] - area[0]) / width, (area[3] - area[1]) / height)
+    centre = ((area[0] + area[2]) / 2, (area[1] + area[3]) / 2)
+    return factor, (
+        centre[0] - (bounds[0] + bounds[2]) / 2 * factor,
+        centre[1] - (bounds[1] + bounds[3]) / 2 * factor,
+    )
+
+
+def _placed(
+    lines: dict[str, _PieceLines], factor: float, offset: tuple[float, float]
+) -> dict[str, _PieceLines]:
+    def place(edges: list[Shape]) -> list[Shape]:
+        # One compound per piece: moving edges one by one copies each of them
+        if not edges:
+            return []
+        return [Pos(*offset) * scale(Compound(children=edges), factor)]
+
+    return {
+        piece_id: _PieceLines(place(piece.visible), place(piece.hidden))
+        for piece_id, piece in lines.items()
+    }
+
+
+def _heading(step: PlannedStep) -> str:
+    name = f" - {step.name}" if step.name else ""
+    return f"Step {step.number}{name}{_KIND_MARKS.get(step.kind, '')}"
+
+
+def _dimension_view(
+    assembly: Assembly, step: PlannedStep, lines: dict[str, _PieceLines], area: Rect
+) -> tuple[View, _View, _Dimensions]:
+    """The step's view placed in ``area`` with its chains drawn: the shown
+    pieces as the extent, stops at this step's pieces and their partners."""
+    view = axis_view(*step.view)
+    left, below = _levels("left").depth, _levels("below").depth
+    inner = (area[0] + left, area[1] + below, area[2], area[3])
+    bounds = _bounds(lines)
+    factor = min(
+        (inner[2] - inner[0]) / (bounds[2] - bounds[0]),
+        (inner[3] - inner[1]) / (bounds[3] - bounds[1]),
+    )
+    offset = (inner[0] - bounds[0] * factor, inner[3] - bounds[3] * factor)
+    box = (
+        inner[0],
+        inner[3] - (bounds[3] - bounds[1]) * factor,
+        inner[0] + (bounds[2] - bounds[0]) * factor,
+        inner[3],
+    )
+    placed = _View(view.caption, offset, factor, box, [], [])
+
+    model, poses = assembly.model, assembly.placement.poses
+    partners = {
+        piece_id
+        for key in step.connections
+        for piece_id in key
+        if piece_id not in step.pieces
+    }
+    chosen = [*step.pieces, *sorted(partners)]
+    world = {p: poses[p].bounds(model.pieces[p]) for p in step.shown}
+    dimensions = _Dimensions()
+    names: tuple[Axis, Axis, Axis] = ("x", "y", "z")
+    for axis in (a for a in range(3) if a != step.view[0]):
+        unit = [0.0, 0.0, 0.0]
+        unit[axis] = 1.0
+        x, y = project(view, unit)
+        side = "below" if abs(x) > abs(y) else "left"
+        chain = chain_for(
+            view.caption, names[axis], side, world, dict(model.pieces), chosen
+        )
+        _dimension(chain, placed, dimensions, f"step {step.number}", _SPLIT_ADVICE)
+    return view, placed, dimensions
+
+
+def step_image(assembly: Assembly, part: Compound, step: PlannedStep) -> StepImage:
+    """The step's image: the isometric view on the left, the dimension view
+    on the right, the heading at the top."""
+    shapes = {child.label: child for child in part.children}
+    iso_area = (MARGIN, MARGIN, PAGE_WIDTH / 2 - MARGIN, PAGE_HEIGHT - HEADING)
+    iso_lines = _piece_lines(shapes, step.shown, _ISOMETRIC)
+    factor, offset = _fit(_bounds(iso_lines), iso_area, ISO_FILL)
+    iso = _placed(iso_lines, factor, offset)
+    labels: dict[str, Rect] = {}
+    for label in visible_labels(assembly, _ISOMETRIC, step.shown):
+        if label.piece_id not in step.pieces:
+            continue
+        x, y = offset[0] + label.x * factor, offset[1] + label.y * factor
+        width, height = _text_size(label.piece_id, 0.0)
+        box = (x - width / 2, y - height / 2, x + width / 2, y + height / 2)
+        # A label that would cover another is left out; the table names it
+        if all(
+            box[2] <= b[0] or b[2] <= box[0] or box[3] <= b[1] or b[3] <= box[1]
+            for b in labels.values()
+        ):
+            labels[label.piece_id] = box
+
+    dim_area = (
+        PAGE_WIDTH / 2 + MARGIN,
+        MARGIN,
+        PAGE_WIDTH - MARGIN,
+        PAGE_HEIGHT - HEADING,
+    )
+    view = axis_view(*step.view)
+    dim_lines = _piece_lines(shapes, step.shown, view)
+    view, placed, dimensions = _dimension_view(assembly, step, dim_lines, dim_area)
+    dims = _placed(dim_lines, placed.scale, placed.offset)
+
+    exporter = ExportSVG(unit=Unit.MM)
+    exporter.add_layer("Before", line_color=RGB(160, 160, 160), line_weight=0.18)
+    exporter.add_layer("New", line_weight=0.5)
+    exporter.add_layer("NewHidden", line_weight=0.25, line_type=LineType.ISO_DASH)
+    exporter.add_layer("Dimensions", line_weight=0.13)
+    # A white ground under each piece name keeps it readable over the lines
+    exporter.add_layer(
+        "LabelGround",
+        fill_color=RGB(255, 255, 255),
+        line_color=RGB(255, 255, 255),
+        line_weight=0.01,
+    )
+    exporter.add_layer(
+        "Text", fill_color=RGB(0, 0, 0), line_color=RGB(0, 0, 0), line_weight=0.01
+    )
+    # A light border keeps every step's image the same size
+    corners = [(0, 0), (PAGE_WIDTH, 0), (PAGE_WIDTH, PAGE_HEIGHT), (0, PAGE_HEIGHT)]
+    exporter.add_shape(
+        [Edge.make_line(a, b) for a, b in zip(corners, corners[1:] + corners[:1])],
+        layer="Before",
+    )
+    for drawn in (iso, dims):
+        for piece_id, piece in drawn.items():
+            new = piece_id in step.pieces
+            if piece.visible:
+                exporter.add_shape(piece.visible, layer="New" if new else "Before")
+            if new and piece.hidden:
+                exporter.add_shape(piece.hidden, layer="NewHidden")
+    if dimensions.lines:
+        exporter.add_shape(
+            [Edge.make_line(a, b) for a, b in dimensions.lines], layer="Dimensions"
+        )
+    if labels:
+        exporter.add_shape(
+            [
+                Polygon(
+                    (b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]), align=None
+                )
+                for b in labels.values()
+            ],
+            layer="LabelGround",
+        )
+    heading_size = _text_size(_heading(step), 0.0)
+    texts = [
+        Pos(MARGIN + heading_size[0] / 2, PAGE_HEIGHT - HEADING / 2)
+        * _text(_heading(step), 0.0),
+        *(
+            Pos((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) * _text(piece_id, 0.0)
+            for piece_id, b in labels.items()
+        ),
+        *(
+            Pos(*label.centre) * _text(label.text, label.rotation)
+            for label in dimensions.labels
+        ),
+        *(Polygon(*_arrow_points(*arrow), align=None) for arrow in dimensions.arrows),
+    ]
+    exporter.add_shape(texts, layer="Text")
+    with tempfile.TemporaryDirectory() as directory:
+        path = Path(directory) / "step.svg"
+        exporter.write(str(path))
+        svg = path.read_text()
+    return StepImage(step, iso, labels, view, dimensions, svg)
+
+
+def image_name(step: PlannedStep, count: int) -> str:
+    """step-01.png, ...; wide enough for every step number."""
+    return f"step-{step.number:0{max(2, len(str(count)))}d}.png"
+
+
+def steps_markdown(assembly: Assembly, plan: StepPlan, title: str) -> str:
+    """The instructions page: per step, its heading, image, pieces and
+    fasteners. No prose: the images and numbers tell how."""
+    lines = [f"# {title}: assembly steps", ""]
+    # One step needs no grouping
+    if not plan.declared and len(plan.steps) > 1:
+        first = ", ".join(plan.steps[0].pieces)
+        lines += [
+            "No steps block: each step adds one piece. Group pieces with a steps "
+            f'block, e.g. `steps {{ "Frame": {first}, ... }}`.',
+            "",
+        ]
+    for step in plan.steps:
+        lines += [
+            f"## {_heading(step)}",
+            "",
+            f"![Step {step.number}]({image_name(step, len(plan.steps))})",
+            "",
+            "| Piece | Lumber | Length (mm) |",
+            "|-------|--------|-------------|",
+        ]
+        for piece_id in step.pieces:
+            piece = assembly.model.pieces[piece_id]
+            length = format_mm(piece.length) if piece.length is not None else "?"
+            lines.append(f"| {piece_id} | {piece.type.value} | {length} |")
+        hardware = _hardware(assembly, step.connections)
+        if hardware:
+            lines += ["", "| Fastener | Count |", "|----------|-------|"]
+            lines += [f"| {item.name} | {item.count} |" for item in hardware]
+        lines.append("")
+    return "\n".join(lines)
+
+
+@dataclass
+class Instructions:
+    """The written files and what the user should hear about them."""
+
+    files: list[Path]
+    declared: bool
+    crowded: list[str]
+
+
+def write_instructions(
+    assembly: Assembly, part: Compound, directory: Path, title: str, size: int = 1600
+) -> Instructions:
+    """Write ``steps.md`` and one PNG per step (``size`` px wide) into
+    ``directory``, creating it if needed."""
+    plan = plan_steps(assembly)
+    directory.mkdir(parents=True, exist_ok=True)
+    files, crowded = [], []
+    for step in plan.steps:
+        image = step_image(assembly, part, step)
+        path = directory / image_name(step, len(plan.steps))
+        path.write_bytes(image.png(size))
+        files.append(path)
+        crowded += image.dimensions.crowded
+    page = directory / "steps.md"
+    page.write_text(steps_markdown(assembly, plan, title))
+    return Instructions([page, *files], plan.declared, crowded)
diff --git a/src/nichiyou_daiku/shell/resources.py b/src/nichiyou_daiku/shell/resources.py
index 9db3dd4..8793011 100644
--- a/src/nichiyou_daiku/shell/resources.py
+++ b/src/nichiyou_daiku/shell/resources.py
@@ -4,7 +4,7 @@ This module provides functionality to extract and summarize the resources
 (lumber pieces) required for a woodworking project from an Assembly.
 """
 
-from typing import Dict
+from typing import Collection, Dict
 
 from pydantic import BaseModel
 
@@ -315,11 +315,19 @@ def _size(value: float) -> float:
     return round(value, 1)
 
 
-def _hardware(assembly: Assembly) -> list[HardwareItem]:
+def _hardware(
+    assembly: Assembly, connections: Collection[tuple[str, str]] | None = None
+) -> list[HardwareItem]:
     """Count the fasteners laid out, by kind and size: dowels first, then
-    slim, coarse and untyped screws, each by diameter and length."""
+    slim, coarse and untyped screws, each by diameter and length. With
+    ``connections``, only theirs."""
     counts: dict[tuple[int, int, float, float, str], int] = {}
     for fastener in assembly.fasteners:
+        if (
+            connections is not None
+            and (fastener.base_id, fastener.target_id) not in connections
+        ):
+            continue
         connection = assembly.model.connections[(fastener.base_id, fastener.target_id)]
         match connection.type:
             case DowelConnection(radius=radius, depth=length):
diff --git a/src/nichiyou_daiku/shell/views.py b/src/nichiyou_daiku/shell/views.py
index 8cc7764..27b33a5 100644
--- a/src/nichiyou_daiku/shell/views.py
+++ b/src/nichiyou_daiku/shell/views.py
@@ -5,7 +5,7 @@ projection is the one build123d's ``project_to_viewport`` uses when looking at
 the origin, so a label placed here lands on the projected lines.
 """
 
-from typing import NamedTuple, Sequence
+from typing import Collection, NamedTuple, Sequence
 
 import numpy as np
 
@@ -88,11 +88,19 @@ def _blocks(
     return far - near > _TOLERANCE_MM
 
 
-def visible_labels(assembly: Assembly, view: View) -> list[Label]:
+def visible_labels(
+    assembly: Assembly, view: View, pieces: Collection[str] | None = None
+) -> list[Label]:
     """Labels at the centers the viewer can see: no other piece lies between
-    a piece's center and the viewer. In model order."""
+    a piece's center and the viewer. In model order.
+
+    With ``pieces``, only those are labelled and only they hide each other
+    (the others are not there yet).
+    """
     boxes = {}
     for piece_id, piece in assembly.model.pieces.items():
+        if pieces is not None and piece_id not in pieces:
+            continue
         low, high = assembly.placement.poses[piece_id].bounds(piece)
         boxes[piece_id] = (
             np.array([low.x, low.y, low.z]),
EOF
````

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/shell/test_instructions.py -q`
Expected: `14 passed` (about 13s)

- [ ] **Step 5: Check**

Check two tests can fail: (1) temporarily change `layer="New" if new else "Before"` to `layer="New"` in `step_image`, run `uv run pytest tests/shell/test_instructions.py -q -k black_and_earlier`, expect `1 failed`, restore; (2) temporarily change `visible_labels(assembly, _ISOMETRIC, step.shown)` to `visible_labels(assembly, _ISOMETRIC)`, run `-k hide_no_labels`, expect `1 failed`, restore. Then write the shelf's instructions and look at them:

```bash
uv run python - <<'PY'
from pathlib import Path
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.shell.build123d_export import assembly_to_build123d
from nichiyou_daiku.shell.instructions import write_instructions
a = Assembly.of(parse_dsl(Path("skills/design/examples/two-tier-shelf.nd").read_text()))
print(write_instructions(a, assembly_to_build123d(a), Path("/tmp/shelf-steps"), "two-tier-shelf"))
PY
```

Expected: about 8 seconds; 5 PNGs and `steps.md`, `crowded=[]`. Read `step-01.png` (left frame, the dimension view from +x with 150 / 89 / 453 / 89 and 38 / 224 / 38) and `step-04.png` (shelf boards black, the view from above with 89 / 22 / 89 ... / 600).

- [ ] **Step 6: Commit**

```bash
make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log
[ $rc -eq 0 ] && git add src/nichiyou_daiku/shell/instructions.py src/nichiyou_daiku/shell/views.py src/nichiyou_daiku/shell/resources.py tests/shell/test_instructions.py && git commit -m "feat: Draw each assembly step and write the steps page

Each image shows the part built so far, earlier pieces grey and the
step's pieces black with their names, beside a view dimensioning where
they go; the page lists each step's pieces and fasteners."
```

---
### Task 6: The `steps` command

**Files:**
- Create: `src/nichiyou_daiku/cli/commands/steps.py`
- Modify: `src/nichiyou_daiku/cli/dsl_cli.py` (register `steps`)
- Modify: `bin/nichiyou-daiku` (run `steps` in the viz environment)
- Modify: `docs/dsl-specification.md` (CLI section "Assembly Steps (requires build123d)"; `tests/test_docs.py` requires every command to be documented)
- Test: `tests/cli/commands/test_steps.py` (new), `tests/test_plugin.py` (the launcher case)

**Interfaces:**
- Consumes: Task 5's `write_instructions`, `Instructions`.
- Produces: `nichiyou-daiku steps FILE [-o DIR] [--size N] [--fillet-radius R]`, writing into `<input stem>-steps` by default; hint (not a warning) without a steps block when there are two or more steps; crowded values as yellow `Warning:` lines; exit 1 when `-o` is a file.

- [ ] **Step 1: Write the failing tests**

````bash
git apply <<'EOF'
diff --git a/tests/cli/commands/test_steps.py b/tests/cli/commands/test_steps.py
new file mode 100644
index 0000000..828db53
--- /dev/null
+++ b/tests/cli/commands/test_steps.py
@@ -0,0 +1,85 @@
+"""Tests for the steps command."""
+
+import struct
+
+import pytest
+
+pytest.importorskip("build123d")
+
+from nichiyou_daiku.cli.dsl_cli import cli  # noqa: E402
+
+CORNER = "(a:2x4 =400)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n"
+CORNER_STEPS = CORNER + 'steps {\n  "Corner": a, b\n}\n'
+# A third piece across the far end of b: two steps without a steps block
+THREE = CORNER + "(c:2x4 =400)\nb -[TF<0 BD<0]- c\n"
+
+
+def _png_width(data: bytes) -> int:
+    assert data[:8] == b"\x89PNG\r\n\x1a\n"
+    return struct.unpack(">I", data[16:20])[0]
+
+
+@pytest.fixture
+def corner(tmp_path):
+    path = tmp_path / "corner.nd"
+    path.write_text(CORNER_STEPS)
+    return path
+
+
+def test_steps_writes_the_page_and_images_next_to_the_input(runner, corner):
+    result = runner.invoke(cli, ["steps", str(corner)])
+    assert result.exit_code == 0, result.output
+    directory = corner.with_name("corner-steps")
+    assert sorted(p.name for p in directory.iterdir()) == ["step-01.png", "steps.md"]
+    assert (directory / "steps.md").read_text().startswith("# corner: assembly steps\n")
+    assert _png_width((directory / "step-01.png").read_bytes()) == 1600
+    assert "Successfully wrote steps.md and 1 step image to" in result.stderr
+    assert result.stdout == ""
+
+
+def test_steps_takes_a_directory_and_an_image_width(runner, corner, tmp_path):
+    out = tmp_path / "instructions"
+    result = runner.invoke(cli, ["steps", str(corner), "-o", str(out), "--size", "800"])
+    assert result.exit_code == 0, result.output
+    assert _png_width((out / "step-01.png").read_bytes()) == 800
+
+
+def test_steps_without_a_steps_block_says_how_to_group(runner, tmp_path):
+    path = tmp_path / "three.nd"
+    path.write_text(THREE)
+    result = runner.invoke(cli, ["steps", str(path)])
+    assert result.exit_code == 0, result.output
+    assert "No steps block: each step adds one piece" in result.stderr
+    # A hint, not a warning
+    assert "Warning" not in result.stderr
+
+
+def test_a_single_step_gets_no_hint(runner, tmp_path):
+    path = tmp_path / "corner.nd"
+    path.write_text(CORNER)
+    result = runner.invoke(cli, ["steps", str(path)])
+    assert result.exit_code == 0, result.output
+    assert "No steps block" not in result.stderr
+
+
+def test_steps_refuses_a_file_as_the_directory(runner, corner, tmp_path):
+    taken = tmp_path / "taken.txt"
+    taken.write_text("keep me")
+    result = runner.invoke(cli, ["steps", str(corner), "-o", str(taken)])
+    assert result.exit_code == 1
+    assert "is a file" in result.stderr
+    assert taken.read_text() == "keep me"
+
+
+def test_steps_from_stdin_needs_a_directory(runner):
+    result = runner.invoke(cli, ["steps", "-"], input=CORNER)
+    assert result.exit_code == 1
+    assert "-o" in result.stderr
+
+
+def test_steps_reports_a_wrong_steps_block(runner, tmp_path):
+    path = tmp_path / "corner.nd"
+    path.write_text(CORNER + 'steps {\n  "Corner": a\n}\n')
+    result = runner.invoke(cli, ["steps", str(path)])
+    assert result.exit_code == 1
+    assert "steps leaves out b" in result.stderr
diff --git a/tests/test_plugin.py b/tests/test_plugin.py
index 8676ef6..8047391 100644
--- a/tests/test_plugin.py
+++ b/tests/test_plugin.py
@@ -141,6 +141,7 @@ def test_wrapper_runs_its_own_source_through_uv(tmp_path):
         ("drawing", "d.nd"),
         ("view", "d.nd"),
         ("render", "d.nd"),
+        ("steps", "d.nd"),
         ("-v", "export", "d.nd"),
     ],
 )
EOF
````

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/cli/commands/test_steps.py tests/test_plugin.py -q`
Expected: `8 failed, 26 passed` (`No such command 'steps'`, and the launcher runs `steps` without the viz extra)

- [ ] **Step 3: Implement**

````bash
git apply <<'EOF'
diff --git a/bin/nichiyou-daiku b/bin/nichiyou-daiku
index fac50f3..474ae58 100755
--- a/bin/nichiyou-daiku
+++ b/bin/nichiyou-daiku
@@ -53,7 +53,7 @@ fi
 group=core
 for arg in "$@"; do
   case $arg in
-    export | drawing | view | render) group=viz ;;
+    export | drawing | view | render | steps) group=viz ;;
   esac
 done
 
diff --git a/docs/dsl-specification.md b/docs/dsl-specification.md
index ba6e897..4cff557 100644
--- a/docs/dsl-specification.md
+++ b/docs/dsl-specification.md
@@ -709,6 +709,17 @@ nichiyou-daiku render furniture.nd -o check.png --size 1000
 
 Draws one square PNG (default 1400px, at least 400px) for checking a design by eye: the model seen from +z, -y, +x and +x +y +z on a 2×2 grid at one scale, visible lines only, in the axes of `size_reference` (see `validate --json`). Each piece's ID is written at its center in every view where no other piece hides that center and it does not overlap another label; pieces labelled in no view are listed in the note at the bottom, below the file name and the overall size. Shapes are those of `export` and `drawing`, including holes and `--fillet-radius`.
 
+### Assembly Steps (requires build123d)
+
+```bash
+nichiyou-daiku steps shelf.nd                    # shelf-steps/steps.md and step-01.png, ...
+nichiyou-daiku steps shelf.nd -o instructions --size 1200
+```
+
+Writes `steps.md` and one PNG per step (default 1600px wide) into a directory, by default `<input>-steps`. The steps come from the file's `steps` block (see [Assembly Steps](#assembly-steps)). The page has no prose: per step, its heading (`Step 2 - Right frame (sub-assembly)`, with `(join)` for a step that joins parts), its image, the pieces it adds with their lumber and length, and its fasteners counted as in the report's shopping list.
+
+Each image shows the part the step leaves from +x +y +z, the pieces built before in grey and the step's pieces in black with their IDs (their hidden edges dashed), beside an orthographic view dimensioning where the step's pieces go: chain dimensions as in `drawing`, stopping at both ends of the step's pieces and of the pieces they are joined to, with the part's overall size. That view looks across the edges the step's connections are measured along, along the axis where the step's pieces hide each other least, from the side where the rest of the part hides them least. When values do not fit beside their chain, the command warns and suggests splitting the step. Without a `steps` block it says how to add one. `--fillet-radius` is that of `export`.
+
 ## Grammar (EBNF)
 
 ```ebnf
diff --git a/src/nichiyou_daiku/cli/commands/steps.py b/src/nichiyou_daiku/cli/commands/steps.py
new file mode 100644
index 0000000..c57a0ea
--- /dev/null
+++ b/src/nichiyou_daiku/cli/commands/steps.py
@@ -0,0 +1,101 @@
+"""Steps command: assembly instructions, a Markdown page and one image per step."""
+
+import sys
+from pathlib import Path
+from typing import Optional
+
+import click
+
+from nichiyou_daiku.cli.utils import (
+    CliEcho,
+    convert_assembly_to_build123d,
+    create_assembly_from_model,
+    ensure_build123d_available,
+    import_viz_module,
+    parse_dsl_to_model,
+    read_dsl_file,
+    require_output_for_stdin,
+)
+
+
+@click.command()
+@click.argument("input_file", type=str)
+@click.option(
+    "-o",
+    "--output",
+    type=click.Path(path_type=Path),
+    help=(
+        "Directory for steps.md and the step images "
+        "(default: <input>-steps, required for stdin)."
+    ),
+)
+@click.option(
+    "--size",
+    type=click.IntRange(min=400),
+    default=1600,
+    show_default=True,
+    help="Width of each step image in pixels.",
+)
+@click.option(
+    "--fillet-radius",
+    type=float,
+    default=5.0,
+    help="Fillet radius in mm (default: 5.0, use 0 to disable)",
+)
+@click.pass_context
+def steps(
+    ctx: click.Context,
+    input_file: str,
+    output: Optional[Path],
+    size: int,
+    fillet_radius: float,
+) -> None:
+    """Write assembly instructions: steps.md and one image per step.
+
+    INPUT_FILE: Path to .nd file or '-' for stdin
+
+    The steps come from the file's steps block; without one, each step adds
+    one piece. Each image shows what is built so far in grey and the step's
+    pieces in black, beside a view dimensioning where they go.
+
+    \b
+    Examples:
+        nichiyou-daiku steps shelf.nd
+        nichiyou-daiku steps shelf.nd -o instructions --size 1200
+    """
+    echo = CliEcho(ctx)
+
+    ensure_build123d_available(echo)
+    write_instructions = import_viz_module(
+        "nichiyou_daiku.shell.instructions", echo
+    ).write_instructions
+
+    require_output_for_stdin(input_file, output)
+    directory = output or Path(input_file).with_name(f"{Path(input_file).stem}-steps")
+    if directory.exists() and not directory.is_dir():
+        echo.error(f"{directory} is a file; give -o a directory for the steps")
+        sys.exit(1)
+    title = directory.name if input_file == "-" else Path(input_file).stem
+
+    model = parse_dsl_to_model(read_dsl_file(input_file), echo)
+    assembly = create_assembly_from_model(model, echo)
+    part = convert_assembly_to_build123d(assembly, echo, fillet_radius=fillet_radius)
+
+    try:
+        result = write_instructions(assembly, part, directory, title, size=size)
+    except Exception as e:
+        echo.exception(f"Error writing the steps: {e}")
+        sys.exit(1)
+
+    images = len(result.files) - 1
+    if not result.declared and images > 1:
+        echo.info(
+            "No steps block: each step adds one piece. Group the pieces with a "
+            'steps block, e.g. steps { "Frame": leg_1, apron_1 }'
+        )
+    for message in result.crowded:
+        echo.info(click.style(f"Warning: {message}", fg="yellow"))
+    echo.info(
+        f"Successfully wrote steps.md and {images} step "
+        f"image{'' if images == 1 else 's'} to {directory}"
+    )
diff --git a/src/nichiyou_daiku/cli/dsl_cli.py b/src/nichiyou_daiku/cli/dsl_cli.py
index 731d192..fb05571 100644
--- a/src/nichiyou_daiku/cli/dsl_cli.py
+++ b/src/nichiyou_daiku/cli/dsl_cli.py
@@ -8,6 +8,7 @@ from nichiyou_daiku.cli.commands.view import view
 from nichiyou_daiku.cli.commands.export import export
 from nichiyou_daiku.cli.commands.drawing import drawing
 from nichiyou_daiku.cli.commands.render import render
+from nichiyou_daiku.cli.commands.steps import steps
 
 
 @click.group()
@@ -37,6 +38,7 @@ cli.add_command(view)
 cli.add_command(export)
 cli.add_command(drawing)
 cli.add_command(render)
+cli.add_command(steps)
 
 
 if __name__ == "__main__":
EOF
````

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/cli/commands/test_steps.py tests/test_plugin.py -q`
Expected: `34 passed`

- [ ] **Step 5: Check**

Try it: `uv run nichiyou-daiku steps skills/design/examples/two-tier-shelf.nd -o /tmp/shelf-steps-cli`. Expected: `Successfully wrote steps.md and 5 step images to /tmp/shelf-steps-cli` and no hint; with `examples/nd_files/simple_table_compact.nd` the hint `No steps block: each step adds one piece...` and 15 images.

- [ ] **Step 6: Commit**

```bash
make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log
[ $rc -eq 0 ] && git add src/nichiyou_daiku/cli/commands/steps.py src/nichiyou_daiku/cli/dsl_cli.py bin/nichiyou-daiku docs/dsl-specification.md tests/cli/commands/test_steps.py tests/test_plugin.py && git commit -m "feat: Add the steps command for assembly instructions

Writes steps.md and one image per step, by default next to the input;
the plugin runs it with build123d."
```

---
### Task 7: Documentation, the design skill and the examples

**Files:**
- Modify: `docs/api-specification.md` (`Model.steps`, `Step`, `Model.of(..., steps=())`, new "Assembly Instructions (Optional)" section)
- Modify: `README.md` (the `steps` command in the quick start)
- Modify: `skills/design/SKILL.md` (write a `steps` block for furniture of more than a few pieces; the `steps` output; reinstall and cairo notes name `steps`)
- Modify: `skills/design/patterns.md` (connection order is only for reading; the build order goes in `steps`)
- Modify: `skills/design/examples/side-table.nd`, `examples/nd_files/simple_table.nd` (their `steps` blocks)
- Test: `tests/test_plugin.py` (the skill names `steps` with the commands that need build123d)
- Local only, not committed: `CLAUDE.md`

**Interfaces:**
- Consumes: everything above.
- Produces: docs checked by `tests/test_docs.py` (the API spec's imports are executed; build123d is installed in `make check` and CI) and `tests/test_plugin.py`.

- [ ] **Step 1: Write the failing tests**

````bash
git apply <<'EOF'
diff --git a/tests/test_plugin.py b/tests/test_plugin.py
index 8047391..c5ddb17 100644
--- a/tests/test_plugin.py
+++ b/tests/test_plugin.py
@@ -318,5 +318,5 @@ def test_skill_covers_render_with_an_old_or_partial_install():
     # Step 6 is the first command that needs the viz extra and cairo
     skill = (ROOT / "skills" / "design" / "SKILL.md").read_text()
     assert "No such command 'render'" in skill
-    assert "`drawing`, `export` or `render` says build123d is missing" in skill
+    assert "`drawing`, `export`, `render` or `steps` says build123d is missing" in skill
     assert "the cairo library is missing" in skill
EOF
````

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/test_plugin.py -q`
Expected: `1 failed, 26 passed` (`test_skill_covers_render_with_an_old_or_partial_install`)

- [ ] **Step 3: Implement**

````bash
git apply <<'EOF'
diff --git a/README.md b/README.md
index f4a075f..c880516 100644
--- a/README.md
+++ b/README.md
@@ -27,6 +27,7 @@ nichiyou-daiku report corner.nd -o report.md # bill of materials, shopping list,
 nichiyou-daiku export corner.nd -f step      # 3D model (needs the viz extra)
 nichiyou-daiku drawing corner.nd             # technical drawing PDF with dimensions (needs the viz extra)
 nichiyou-daiku render corner.nd              # check image PNG, four labelled views (needs the viz extra)
+nichiyou-daiku steps corner.nd               # assembly steps: Markdown and one image per step (needs the viz extra)
 ```
 
 See [`examples/nd_files/`](examples/nd_files/) for complete designs, such as a table written with variables ([`simple_table_parametric.nd`](examples/nd_files/simple_table_parametric.nd)) and one whose apron length is solved from the legs ([`simple_table_unknowns.nd`](examples/nd_files/simple_table_unknowns.nd)).
diff --git a/docs/api-specification.md b/docs/api-specification.md
index 0715250..e3d347e 100644
--- a/docs/api-specification.md
+++ b/docs/api-specification.md
@@ -335,15 +335,20 @@ class Model(BaseModel, frozen=True):
     pieces: dict[str, Piece]                      # Piece ID -> Piece
     connections: dict[tuple[str, str], Connection] # (base_id, target_id) -> Connection
     label: str | None = None                       # Optional project label
+    steps: tuple[Step, ...] = ()                   # Assembly order; empty when not declared
+
+class Step(BaseModel, frozen=True):
+    name: str                                      # Heading of the step
+    pieces: tuple[str, ...]                        # IDs of the pieces it adds
 ```
 
 **Factory Methods:**
 
 | Method | Description |
 |--------|-------------|
-| `Model.of(pieces, connections, label=None)` | Create from iterables |
+| `Model.of(pieces, connections, label=None, steps=())` | Create from iterables |
 
-`Model.of` raises `ValueError` for duplicate piece IDs, connections that reference pieces not in `pieces`, and a second connection for the same (base, target) pair.
+`Model.of` raises `ValueError` for duplicate piece IDs, connections that reference pieces not in `pieces`, and a second connection for the same (base, target) pair. With `steps`, it also raises it when a piece is in no step or in two, a step names an unknown piece or none, or a step leaves its own pieces in separate parts; see [Assembly Steps](./dsl-specification.md#assembly-steps).
 
 **Example:**
 
@@ -820,6 +825,27 @@ def technical_drawing(
 
 Pass the `assembly` that `part` was built from to dimension the drawing (overall size and where the pieces go; see `drawing` in the [DSL Specification](./dsl-specification.md)). Values that cannot be placed without overlapping raise `nichiyou_daiku.shell.dimensioning.CrowdedDimensionsWarning`. `exporter.write("drawing.svg")` writes the page as SVG.
 
+### Assembly Instructions (Optional)
+
+`nichiyou_daiku.core.assembly.steps.plan_steps(assembly)` plans the steps without build123d: a `StepPlan` whose `declared` says whether the model has a `steps` block and whose `steps` are `PlannedStep`s with the `pieces` each adds, the `connections` it makes, its `kind` (`first`, `attach`, `sub-assembly` or `join`), the pieces `shown` in its image and the `view` (world axis and side) its dimension view looks from.
+
+Requires `build123d` package to draw them.
+
+```python
+from nichiyou_daiku.shell.instructions import write_instructions
+
+def write_instructions(
+    assembly: Assembly,
+    part: "Compound",
+    directory: Path,
+    title: str,
+    size: int = 1600,
+) -> Instructions:
+    """Write steps.md and one PNG per step (size px wide) into directory."""
+```
+
+`part` is the `assembly_to_build123d` result for `assembly`. The returned `Instructions` has the written `files` (`steps.md` first), `declared` as above, and `crowded`: a message for each step whose dimension values do not fit. See `steps` in the [DSL Specification](./dsl-specification.md).
+
 ## Complete Examples
 
 ### Simple Frame
diff --git a/examples/nd_files/simple_table.nd b/examples/nd_files/simple_table.nd
index 19f109c..b1adc41 100644
--- a/examples/nd_files/simple_table.nd
+++ b/examples/nd_files/simple_table.nd
@@ -64,4 +64,13 @@ apron_front -[{"contact_face": "right", "edge_shared_face": "front", "offset": F
 apron_front -[{"contact_face": "right", "edge_shared_face": "front", "offset": FromMin(520.426)}
                {"contact_face": "back", "edge_shared_face": "top", "offset": FromMin(0)}]- table_top_7
 table_top_8 -[{"contact_face": "back", "edge_shared_face": "down", "offset": FromMin(0)}
-              {"contact_face": "top", "edge_shared_face": "front", "offset": FromMin(0)}]- leg_2
\ No newline at end of file
+              {"contact_face": "top", "edge_shared_face": "front", "offset": FromMin(0)}]- leg_2
+
+// Assembly: the side frames, the aprons joining them, the top
+steps {
+  "Left frame":  leg_1, leg_3, apron_left
+  "Right frame": leg_2, leg_4, apron_right
+  "Join":        apron_front, apron_back
+  "Top":         table_top_1, table_top_2, table_top_3, table_top_4,
+                 table_top_5, table_top_6, table_top_7, table_top_8
+}
diff --git a/skills/design/SKILL.md b/skills/design/SKILL.md
index 3295fd4..e956086 100644
--- a/skills/design/SKILL.md
+++ b/skills/design/SKILL.md
@@ -19,7 +19,7 @@ Check the request against [requirements.md](requirements.md). Ask only for what
 
 ## 3. Write
 
-Create `<name>.nd`. Name the overall sizes as variables and derive lengths and offsets from them; leave a length unknown (`=?`) where the pieces at both ends fix it. Put the overall size in a comment at the top and group the pieces by section.
+Create `<name>.nd`. Name the overall sizes as variables and derive lengths and offsets from them; leave a length unknown (`=?`) where the pieces at both ends fix it. Put the overall size in a comment at the top and group the pieces by section. For furniture of more than a few pieces, end with a `steps` block in the order a person would build it: frames first (each frame a step), then the pieces that join them, shelves, and the top last.
 
 ## 4. Check and fix
 
@@ -47,6 +47,7 @@ Run `nichiyou-daiku render <name>.nd -o <name>.png` and read the PNG. It shows t
 ## 7. Output files on request
 
 - Drawing: `nichiyou-daiku drawing <name>.nd -o <name>.pdf`
+- Assembly instructions: `nichiyou-daiku steps <name>.nd` (a `<name>-steps` directory with `steps.md` and one image per step); read a few of the images to check the order and the dimensions
 - 3D model: `nichiyou-daiku export <name>.nd -f step` (or `-f stl`)
 
 ## 8. Report
@@ -59,9 +60,9 @@ Tell the user the file path, the overall size, what to buy from the shopping lis
 
 An installed CLI can be behind this plugin. Ask the user to reinstall it when:
 
-- `render` says `No such command 'render'` (it predates the check image): `uv tool install --force "nichiyou-daiku[viz] @ git+https://github.com/ar90n/nichiyou-daiku"`
-- `drawing`, `export` or `render` says build123d is missing (it lacks the viz extra): `uv tool install --force "nichiyou-daiku[viz] @ git+https://github.com/ar90n/nichiyou-daiku"`
+- `render` says `No such command 'render'` or `steps` says `No such command 'steps'` (it predates them): `uv tool install --force "nichiyou-daiku[viz] @ git+https://github.com/ar90n/nichiyou-daiku"`
+- `drawing`, `export`, `render` or `steps` says build123d is missing (it lacks the viz extra): `uv tool install --force "nichiyou-daiku[viz] @ git+https://github.com/ar90n/nichiyou-daiku"`
 - `validate` says `No such option: --json` (it predates the JSON output): `uv tool install --force "git+https://github.com/ar90n/nichiyou-daiku"`, or the `[viz]` form above
 - `validate` rejects syntax that the DSL specification documents (it is older than the plugin): `uv tool install --force "git+https://github.com/ar90n/nichiyou-daiku"`, or the `[viz]` form above
 
-If `render`, `drawing` or `export` says the cairo library is missing, ask the user to install it (macOS: `brew install cairo`, Debian/Ubuntu: `sudo apt install libcairo2`).
+If `render`, `drawing`, `export` or `steps` says the cairo library is missing, ask the user to install it (macOS: `brew install cairo`, Debian/Ubuntu: `sudo apt install libcairo2`).
diff --git a/skills/design/examples/side-table.nd b/skills/design/examples/side-table.nd
index 7ae9efc..8f99537 100644
--- a/skills/design/examples/side-table.nd
+++ b/skills/design/examples/side-table.nd
@@ -70,3 +70,11 @@ apron_front -[RF<13.75 BT<0 D(:8x30)]- top_2
 apron_front -[RF<116.5 BT<0 D(:8x30)]- top_3
 apron_front -[RF<219.25 BT<0 D(:8x30)]- top_4
 top_5 -[BD<0 TF<0 D(:8x30)]- leg_fr
+
+// Assembly: the side frames, the aprons joining them, the top
+steps {
+  "Left frame":  leg_fl, leg_bl, apron_left
+  "Right frame": leg_fr, leg_br, apron_right
+  "Join":        apron_front, apron_back
+  "Top":         top_1, top_2, top_3, top_4, top_5
+}
diff --git a/skills/design/patterns.md b/skills/design/patterns.md
index dcff73f..70c49e3 100644
--- a/skills/design/patterns.md
+++ b/skills/design/patterns.md
@@ -170,6 +170,8 @@ Name the overall sizes as variables (`WIDTH = 800`) and derive lengths and offse
 3. Top surface connections
 4. Shelf connections
 
+This order only keeps the file readable: connections mean the same in any order. The order a person builds the furniture in goes in a `steps` block at the end (see "Assembly Steps" in the DSL specification).
+
 ### 3. Comments
 
 Always include:
EOF
````

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_plugin.py tests/test_docs.py -q`
Expected: `76 passed`

- [ ] **Step 5: Check**

Update `CLAUDE.md` (local, not committed): in 構成と責務, add to the `core/` list `assembly/steps.py`（組み立て手順の計画。build123d に依存しない）, and to the `shell/` line `instructions.py`（組み立て手順の画像と steps.md。build123d 必須）. Then look at the side table's steps: `uv run nichiyou-daiku steps skills/design/examples/side-table.nd -o /tmp/side-steps` (4 steps: left frame, right frame as a sub-assembly, join, top with 89 and 13.8).

- [ ] **Step 6: Commit**

```bash
make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log
[ $rc -eq 0 ] && git add docs/api-specification.md README.md skills/design/SKILL.md skills/design/patterns.md skills/design/examples/side-table.nd examples/nd_files/simple_table.nd tests/test_plugin.py && git commit -m "docs: Describe assembly steps and add them to the examples"
```
