# Docs Single Source (M3-2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep one English source for the DSL and Python API docs, give the LLM prompts only LLM-specific guidance, and let tests catch drift in the examples, tables and links that remain duplicated.

**Architecture:** `docs/dsl-specification.md` and `docs/api-specification.md` become the only specs; the Japanese twins and three `prompts/reference/` files are deleted, `prompts/system.md` keeps its patterns and rules and points at the DSL spec, and README shrinks to an overview with links. A new `tests/test_docs.py` validates every ```nd example, runs the API spec's `>>>` examples, checks lumber/preset tables against the code and checks relative links.

**Tech Stack:** Python 3.13, pytest, doctest, Lark DSL (`parse_dsl`), Markdown.

**Spec:** `docs/superpowers/specs/2026-10-12-docs-single-source-design.md`

## Global Constraints

- Docs are English only; `docs/superpowers/` (decision records) stays as it is and is excluded from the tests.
- Canonical sources: DSL = `docs/dsl-specification.md`, Python API = `docs/api-specification.md`.
- No prompt generation script.
- ```nd blocks must parse and have no placement conflicts, overlapping pieces or fastener issues; unconnected pieces are allowed; fragments use ```text.
- Run `make check` before every commit and `make ci-local` before merging into main.

## Review Focus

- An `.nd` example file that drifts from the DSL (`examples/nd_files/*.nd`, `prompts/examples/nd-output/*.nd`) should fail a test just like a ```nd block in Markdown (pinned in Task 2).
- The Python output example (`prompts/examples/python-output/simple-table.py`) should keep building a valid table (pinned in Task 2).
- A link to a deleted file anywhere in README, docs or prompts should fail (pinned in Task 2).
- A preset or lumber type added in code but not in the DSL spec tables should fail (pinned in Task 2).
- The trimmed prompt must not produce worse designs than the old one (checked in Task 4).

---

### Task 1: Consolidate the docs and prompts

**Files:**
- Delete: `docs/dsl-specification_ja.md`, `docs/api-specification_ja.md`, `prompts/reference/dsl-complete.md`, `prompts/reference/python-api.md`, `prompts/reference/presets.md`
- Modify: `docs/dsl-specification.md` (screw section), `prompts/system.md`, `prompts/README.md`

**Interfaces:**
- Consumes: nothing
- Produces: the file layout Task 2's link test checks

- [ ] **Step 1: Move the screw selection guide into the DSL spec**

In `docs/dsl-specification.md`, directly after the bullet list under the Screw Connection's `#### Rules` heading (before `#### Examples`), insert (allowed ranges corrected for the strict rule, length < target thickness + base depth):

```markdown
#### Choosing a Length

When the base is also contacted on a wide (front/back) face:

| Target → Base | Allowed length | Recommended screw |
|---------------|----------------|-------------------|
| 2x4 → 2x4 (38mm + 38mm) | 39-75mm | `Slim:3.8x65`, `Coarse:3.8x57` |
| 1x4 → 2x4 (19mm + 38mm) | 20-56mm | `Slim:3.3x45`, `Coarse:3.8x40` |
| 1x4 → 1x4 (19mm + 19mm) | 20-37mm | `Slim:3.3x30`, `Coarse:3.8x30` |

A base contacted on its narrow face (as deep as its width) or its end (as deep as its length) allows longer screws.
```

- [ ] **Step 2: Delete the duplicates**

```bash
git rm docs/dsl-specification_ja.md docs/api-specification_ja.md prompts/reference/dsl-complete.md prompts/reference/python-api.md prompts/reference/presets.md
```

- [ ] **Step 3: Trim `prompts/system.md`**

Replace everything from the line `## Core Concepts` up to (not including) the line `## Verified Patterns (Follow These Exactly)` with:

```markdown
## DSL Specification

The full DSL specification (`docs/dsl-specification.md`) comes with this prompt. Every rule in it applies: the piece frame and faces, edges and offsets, placement rules, variables, unknown lengths and sliding connections, connection types and presets. The patterns below assume it.

---

```

In the Output Format section, replace

```text
Write it with the API in `prompts/reference/python-api.md`;
```

with

```text
Write it with the API in `docs/api-specification.md` (provided when Python output is wanted);
```

- [ ] **Step 4: Rewrite `prompts/README.md`**

Replace the whole file with:

````markdown
# nichiyou-daiku LLM Prompts

Prompts for generating nichiyou-daiku furniture designs with an LLM. The prompt carries only LLM-specific guidance; the specifications live in `docs/` and are sent alongside it.

## Files

```
prompts/
├── README.md            # This file
├── system.md            # System prompt: output format, verified patterns, length rules, checklist
├── user-template.md     # Specification template to fill in
└── examples/
    ├── user-specs/      # Example specifications
    ├── nd-output/       # Expected .nd outputs (validated by the test suite)
    └── python-output/   # Expected Python output (built by the test suite)
```

## Usage

| Output | Send as the system prompt | About |
|--------|---------------------------|-------|
| `.nd` (recommended) | `prompts/system.md` + `docs/dsl-specification.md` | 7,800 tokens |
| Python | the above + `docs/api-specification.md` | 14,600 tokens |

Estimates are characters / 4. Add a file from `examples/nd-output/` when a worked example helps.

```python
from pathlib import Path

import anthropic

system = "\n\n".join(
    Path(path).read_text()
    for path in ("prompts/system.md", "docs/dsl-specification.md")
)
response = anthropic.Anthropic().messages.create(
    model="claude-sonnet-5",
    max_tokens=8192,
    system=system,
    messages=[{"role": "user", "content": Path("my-spec.md").read_text()}],
)
print(response.content[0].text)
```

## Workflow

1. Copy `user-template.md` and fill in the furniture (see `examples/user-specs/`).
2. Send it with the system prompt above.
3. Check the result:

```bash
nichiyou-daiku validate generated.nd
nichiyou-daiku report generated.nd -o report.md
```
````

- [ ] **Step 5: Check nothing still points at the deleted files**

Run: `grep -rn "_ja.md\|dsl-complete\|python-api.md\|presets.md" README.md docs prompts src tests examples | grep -v "docs/superpowers"`
Expected: no output.

- [ ] **Step 6: Check and commit**

Run: `make check`
Expected: lint clean; all tests pass.

```bash
git add -A docs prompts
git commit -m "docs: Keep one English source for the DSL and API specs"
```

---

### Task 2: Docs tests

**Files:**
- Create: `tests/test_docs.py`
- Modify: `docs/dsl-specification.md` (fragment fences)

**Interfaces:**
- Consumes: the layout from Task 1
- Produces: `tests/test_docs.py` (used by Task 3 to check the new README)

- [ ] **Step 1: Write the tests**

Create `tests/test_docs.py`:

```python
"""Keep the docs honest: examples, tables and links must match the code."""

import doctest
import re
import runpy
from pathlib import Path

import pytest

from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.dowel import Dowel
from nichiyou_daiku.core.piece import PieceType, get_shape
from nichiyou_daiku.core.placement import find_overlaps
from nichiyou_daiku.core.screw import CoarseThreadScrew, SlimScrew
from nichiyou_daiku.dsl import parse_dsl

ROOT = Path(__file__).parents[1]
MARKDOWN = sorted(
    [
        *(p for p in (ROOT / "docs").glob("*.md")),
        ROOT / "README.md",
        *(ROOT / "prompts").rglob("*.md"),
    ]
)
ND_FILES = sorted(
    [
        *(ROOT / "examples" / "nd_files").glob("*.nd"),
        *(ROOT / "prompts" / "examples" / "nd-output").glob("*.nd"),
    ]
)
FENCE = re.compile(r"^```(\w[\w-]*)?\n(.*?)^```", re.S | re.M)
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
DSL_SPEC = (ROOT / "docs" / "dsl-specification.md").read_text()


def _blocks(language: str) -> list[tuple[str, str]]:
    found = []
    for path in MARKDOWN:
        text = path.read_text()
        for match in FENCE.finditer(text):
            if match.group(1) == language:
                line = text[: match.start()].count("\n") + 1
                found.append((f"{path.relative_to(ROOT)}:{line}", match.group(2)))
    return found


def _problems(source: str) -> list[str]:
    model = parse_dsl(source)
    assembly = Assembly.of(model)
    return [
        *(f"conflict {c.base_id} -> {c.target_id}" for c in assembly.placement.conflicts),
        *(f"overlap {o.lhs}/{o.rhs}" for o in find_overlaps(model, assembly.placement)),
        *(f"fastener {i.base_id} -> {i.target_id}" for i in assembly.fastener_issues),
    ]


@pytest.mark.parametrize(("where", "source"), _blocks("nd"))
def test_nd_examples_in_the_docs_are_sound(where, source):
    assert _problems(source) == []


@pytest.mark.parametrize("path", ND_FILES, ids=lambda p: p.name)
def test_example_files_are_sound(path):
    assert _problems(path.read_text()) == []


def test_python_output_example_builds_a_sound_table():
    namespace = runpy.run_path(
        str(ROOT / "prompts" / "examples" / "python-output" / "simple-table.py")
    )
    assembly = namespace["main"]()
    assert assembly.placement.conflicts == ()
    assert find_overlaps(assembly.model, assembly.placement) == ()


def test_api_spec_examples_run():
    text = (ROOT / "docs" / "api-specification.md").read_text()
    blocks = [
        (text[: m.start()].count("\n") + 2, m.group(2))
        for m in FENCE.finditer(text)
        if m.group(1) == "python"
    ]
    # Signature blocks show the imports the doctest blocks rely on
    namespace: dict = {}
    imports = re.compile(r"^(?:>>> )?((?:from \S+ )?import (?:\([^)]*\)|[^\n]+))", re.M)
    for _, body in blocks:
        for statement in imports.findall(body):
            exec(re.sub(r"\n(?:\.\.\. )?", "\n", statement), namespace)
    parser = doctest.DocTestParser()
    runner = doctest.DocTestRunner(
        optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE
    )
    for line, body in blocks:
        if ">>>" not in body:
            continue
        test = parser.get_doctest(
            body, namespace, f"api-specification.md:{line}", None, line
        )
        runner.run(test, clear_globs=False)
        # DocTest copies its globals; carry definitions on to later blocks
        namespace.update(test.globs)
    assert runner.summarize(verbose=False).failed == 0


def test_lumber_table_matches_the_code():
    section = DSL_SPEC.split("### Lumber Types", 1)[1].split("###", 1)[0]
    rows = re.findall(r"^\| `(\d+x\d+)` \| (\d+) \| (\d+) \|", section, re.M)
    documented = {name: (float(w), float(t)) for name, w, t in rows}
    actual = {
        t.value: (get_shape(t).width, get_shape(t).height) for t in PieceType
    }
    assert documented == actual


def test_preset_tables_match_the_code():
    # Lumber rows look like dowel rows, so read only the dowel section
    dowel_section = DSL_SPEC.split("### Dowel Connection", 1)[1].split("### Screw", 1)[0]
    dowels = set(re.findall(r"^\| `(\d+x\d+)` \| [\d.]+ \| [\d.]+ \|", dowel_section, re.M))
    screws = set(re.findall(r"^\| `((?:Slim|Coarse):[\d.]+x[\d.]+)` \|", DSL_SPEC, re.M))
    assert dowels == {preset.value for preset in Dowel}
    assert screws == {f"Slim:{p.value}" for p in SlimScrew} | {
        f"Coarse:{p.value}" for p in CoarseThreadScrew
    }


@pytest.mark.parametrize("path", MARKDOWN, ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_links_point_at_existing_files(path):
    missing = []
    for target in LINK.findall(path.read_text()):
        if re.match(r"^(https?:|mailto:|#)", target):
            continue
        file_part = target.split("#", 1)[0]
        if not (path.parent / file_part).exists():
            missing.append(target)
    assert missing == []
```

- [ ] **Step 2: Run them and read the failures**

Run: `.venv/bin/pytest tests/test_docs.py -q`
Expected: FAIL in `test_nd_examples_in_the_docs_are_sound` for the snippet under `## Unknown Lengths and Sliding Connections` in `docs/dsl-specification.md` (it refers to pieces it does not define). Every other test passes. If another test fails, fix the doc (or the test if the doc is right) and ledger the ruling.

- [ ] **Step 3: Mark the fragment as text**

In `docs/dsl-specification.md`, change the opening fence of that snippet from ```` ```nd ```` to ```` ```text ````.

- [ ] **Step 4: Run them again**

Run: `.venv/bin/pytest tests/test_docs.py -q`
Expected: all pass.

- [ ] **Step 5: Check the tests can fail**

Temporarily change one row of the lumber table in `docs/dsl-specification.md` (e.g. `| \`2x6\` | 140 | 38 |` → `| \`2x6\` | 141 | 38 |`) and one link in `prompts/README.md` to a missing file; run `.venv/bin/pytest tests/test_docs.py -q`.
Expected: the table test and the link test fail. Revert both edits.

- [ ] **Step 6: Check and commit**

Run: `make check`
Expected: lint clean; all tests pass.

```bash
git add tests/test_docs.py docs/dsl-specification.md
git commit -m "test: Check doc examples, tables and links against the code"
```

---

### Task 3: Trim the README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: `tests/test_docs.py` from Task 2

- [ ] **Step 1: Replace the README**

Keep the first 12 lines (title, badges, the two intro paragraphs) unchanged and replace everything after them with:

````markdown
## Quick Example

A corner joint of two 2x4s, written in the DSL:

```nd
(corner_piece_a:2x4 =400)
(corner_piece_b:2x4 =400)

corner_piece_a -[TF<0 BD<0]- corner_piece_b
```

```bash
nichiyou-daiku validate corner.nd           # syntax, placement, overlaps, fasteners
nichiyou-daiku report corner.nd -o report.md # bill of materials, shopping list, cut list
nichiyou-daiku export corner.nd -f step      # 3D model (needs the viz extra)
nichiyou-daiku drawing corner.nd             # technical drawing PDF (needs the viz extra)
```

See [`examples/nd_files/`](examples/nd_files/) for complete designs, such as a table written with variables ([`simple_table_parametric.nd`](examples/nd_files/simple_table_parametric.nd)) and one whose apron length is solved from the legs ([`simple_table_unknowns.nd`](examples/nd_files/simple_table_unknowns.nd)).

## Features

- 📝 A small DSL for furniture: pieces, connections, variables and arithmetic
- 🧩 Unknown lengths (`=?`) and sliding connections (`?` offsets) solved from the other connections
- 📐 Exact placement from all connections at once; contradictions and overlaps are reported
- 🔩 Dowels and screws laid out in the contact area, with preset sizes
- 📑 Markdown reports: bill of materials, shopping list, cut list with saw kerf
- 🎯 STL/STEP export and technical drawings with build123d (optional)
- 🪵 Standard lumber: 1x4, 1x6, 1x8, 2x2, 2x4, 2x6
- 🐍 Typed Python API

## Installation

```bash
pip install nichiyou-daiku          # core and CLI
pip install "nichiyou-daiku[viz]"   # plus 3D export and drawings (build123d)
```

> **Note** build123d currently has limited support for ARM64/aarch64. The core works everywhere.

## Documentation

- [DSL specification](docs/dsl-specification.md): pieces, faces and offsets, connections, variables, unknowns, fasteners, CLI, grammar, errors
- [Python API](docs/api-specification.md): pieces, connections, models, assembly, placement, reports, 3D export
- [LLM prompts](prompts/README.md): generate designs with an LLM

## Development

```bash
git clone https://github.com/ar90n/nichiyou-daiku.git
cd nichiyou-daiku
uv sync --dev --all-extras

make check     # lint and tests; run before every commit (~30s)
make ci-local  # the full CI pipeline in Dagger; run before merging into main or pushing
make format
```

Design decisions are recorded in [`docs/superpowers/specs/`](docs/superpowers/specs/).

## Contributing

1. Fork the repository and create a feature branch
2. Write tests first (TDD), then implement
3. Run `make check`
4. Open a pull request titled `<type>: <description>`, where type is one of `feat`, `fix`, `docs`, `refactor`, `style`, `chore` or `test`; release notes are grouped by it

## License

Apache 2.0 License - see LICENSE file for details
````

- [ ] **Step 2: Run the docs tests**

Run: `.venv/bin/pytest tests/test_docs.py -q`
Expected: all pass (the README's ```nd block validates and its links resolve).

- [ ] **Step 3: Check and commit**

Run: `make check`
Expected: lint clean; all tests pass.

```bash
git add README.md
git commit -m "docs: Trim the README to an overview with links"
```

---

### Task 4: Check the prompt and finish

**Files:**
- Modify: `docs/superpowers/specs/2026-10-12-docs-single-source-design.md` (status)
- Modify (local, not committed): `CLAUDE.md`

- [ ] **Step 1: Compare old and new prompts**

Prepare in `/tmp/nd-m3-2/`:
- `old-system.txt` = `git show main:prompts/system.md` + `git show main:prompts/reference/presets.md` + `git show main:prompts/reference/dsl-complete.md`, joined by blank lines
- `new-system.txt` = `prompts/system.md` + `docs/dsl-specification.md`, joined by blank lines

For each of `prompts/examples/user-specs/side-table.md` and `two-tier-shelf.md`, and each of old/new, run two sonnet subagents (8 runs) with the prompt: "Act as the model below. System prompt: <contents of old/new-system.txt>. User message: <spec>. Reply with only the .nd file." Save each reply to `/tmp/nd-m3-2/<spec>-<old|new>-<n>.nd` and run `nichiyou-daiku validate` on it; record whether it is valid and whether `report`'s overall size matches the spec (W × D × H in any axis order).
Expected: new valid-and-sized count ≥ old count. If lower, add the missing guidance to `prompts/system.md`, rerun the new runs, and ledger the change.

- [ ] **Step 2: Mark the spec implemented and update CLAUDE.md**

In the spec, change `- ステータス: 設計済み（未実装）` to `- ステータス: 実装済み（ブランチ docs/single-source）` and add a line `- プロンプトの比較: <old と new の結果>`.
In the local `CLAUDE.md`, replace the "ドキュメントの置き場所" section's last bullet with: `- 機能を足したら、DSL 仕様・API 仕様（docs/、英語のみ）と、作例を変えるなら prompts/system.md を直す。例・表・リンクは tests/test_docs.py が確かめる`.

- [ ] **Step 3: Check, CI and commit**

Run: `make check && make ci-local`
Expected: both pass.

```bash
git add docs/superpowers/specs/2026-10-12-docs-single-source-design.md
git commit -m "docs: Mark the docs single-source spec implemented"
```
