# Design Skill Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship nichiyou-daiku as a Claude Code plugin whose `nichiyou-daiku:design` skill designs furniture as a `.nd` file and checks it with the CLI, replacing `prompts/`.

**Architecture:** The repository root is the plugin root and its own marketplace (`.claude-plugin/`). The skill lives in `skills/design/` and points at `docs/` through `${CLAUDE_PLUGIN_ROOT}`. `bin/nichiyou-daiku` is a POSIX sh wrapper on the Bash tool's PATH: it runs an installed CLI, else the plugin's own source with `uv tool run --from <root>`.

**Tech Stack:** Claude Code plugins (plugin.json, marketplace.json, skills, bin), POSIX sh, uv, pytest.

**Spec:** `docs/superpowers/specs/2026-10-12-design-skill-plugin-design.md`

## Global Constraints

- Branch `docs/single-source`, in the main working tree. `make check` before every commit; commit only what the step names.
- Plugin name `nichiyou-daiku`, marketplace name `nichiyou-daiku`, marketplace entry `"source": "./"`. No `version` in `plugin.json`.
- Skill at `skills/design/SKILL.md`, frontmatter `name: design`; skill content is English (specs stay Japanese).
- `${CLAUDE_PLUGIN_ROOT}` appears only in SKILL.md bodies: Claude Code substitutes it there and nowhere else (supporting files read later keep it literal). `CLAUDE_PLUGIN_ROOT` is not in the Bash tool's environment.
- `bin/nichiyou-daiku`: `#!/bin/sh`, git mode 100755. Hand-over flag `NICHIYOU_DAIKU_WRAPPED=1`. uv form: `uv tool run --from <root> nichiyou-daiku ...`; with `export`/`drawing`/`view` in the arguments, `--from "nichiyou-daiku[viz] @ <root>"`. Neither CLI nor uv: exit 127 with how to install.
- Spike result (done while planning, 2026-10-12): `uv tool run --from` works for the core and for viz (build123d from the git source in `tool.uv.sources`), with a space in the plugin path, writes nothing under the plugin root, and starts in 0.26s once cached. `uv run --project` wrote `__pycache__` into the plugin root, so it is out.
- Dotfiles stay uncommitted except `.claude-plugin/` (and the existing `.github/`).
- Never touch the user's own `uv tool` install (`~/.local/bin/nichiyou-daiku`); checks use `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR` under `/tmp` and a PATH without `~/.local/bin`.

## Review Focus

1. The wrapper reached through a symlink (absolute or relative) must still find the plugin root, not the link's directory. Test: Task 2 `test_wrapper_reached_through_a_symlink_uses_the_plugin_root`.
2. An empty PATH entry (the current directory) or a directory named `nichiyou-daiku` on PATH (e.g. a checkout) must never be executed. Test: Task 2 `test_wrapper_skips_the_current_directory_and_directories`.
3. A plugin path or a file name with spaces must reach uv / the CLI as one argument. Tests: Task 2 `test_wrapper_keeps_a_plugin_path_with_spaces_whole`, and `"my table.nd"` in every wrapper test.
4. `${CLAUDE_PLUGIN_ROOT}` written in a supporting file (`patterns.md`, examples) reaches the agent as a literal, unusable path. Test: Task 3 `test_plugin_root_appears_only_in_skill_bodies`.
5. A global option before the command (`nichiyou-daiku -v export x.nd`) must still bring the viz extra. Test: Task 2 `test_wrapper_adds_the_viz_extra_for_3d_commands` with `("-v", "export", ...)`.

---

### Task 1: Plugin and marketplace manifests

**Files:**
- Create: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
- Test: `tests/test_plugin.py` (new)

**Interfaces:**
- Produces: `tests/test_plugin.py` with `ROOT = Path(__file__).parents[1]`; later tasks append to it. Plugin name `nichiyou-daiku`.

- [ ] **Step 1: Write the failing tests**

`tests/test_plugin.py`:

```python
"""The Claude Code plugin: manifests, skills and the CLI wrapper."""

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def _json(name: str) -> dict:
    return json.loads((ROOT / ".claude-plugin" / name).read_text())


def test_plugin_manifest_names_the_plugin():
    manifest = _json("plugin.json")
    assert manifest["name"] == "nichiyou-daiku"
    assert manifest["description"]
    # A version pins users to it; without one they follow the commits
    assert "version" not in manifest


def test_marketplace_offers_the_repository_as_the_plugin():
    marketplace = _json("marketplace.json")
    assert marketplace["name"] == "nichiyou-daiku"
    assert marketplace["owner"]["name"]
    [entry] = marketplace["plugins"]
    assert entry["name"] == _json("plugin.json")["name"]
    assert entry["source"] == "./"
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/test_plugin.py -q`
Expected: 2 failed, `FileNotFoundError: ... .claude-plugin/plugin.json`

- [ ] **Step 3: Write the manifests**

`.claude-plugin/plugin.json`:

```json
{
  "name": "nichiyou-daiku",
  "description": "Design DIY furniture from standard 1x/2x lumber with the nichiyou-daiku DSL and CLI",
  "author": { "name": "Masahiro Wada" },
  "homepage": "https://github.com/ar90n/nichiyou-daiku",
  "repository": "https://github.com/ar90n/nichiyou-daiku",
  "license": "Apache-2.0",
  "keywords": ["woodworking", "diy", "furniture", "cad"]
}
```

`.claude-plugin/marketplace.json`:

```json
{
  "name": "nichiyou-daiku",
  "owner": { "name": "Masahiro Wada" },
  "description": "The nichiyou-daiku plugin for Claude Code",
  "plugins": [
    {
      "name": "nichiyou-daiku",
      "source": "./",
      "description": "Design DIY furniture from standard 1x/2x lumber with the nichiyou-daiku DSL and CLI"
    }
  ]
}
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/test_plugin.py -q`
Expected: `2 passed`

- [ ] **Step 5: Validate with Claude Code on a copy without local files**

```bash
rm -rf /tmp/ndk-plugin && mkdir /tmp/ndk-plugin
git ls-files -co --exclude-standard -z | tar -c --null -T - | tar -x -C /tmp/ndk-plugin
claude plugin validate /tmp/ndk-plugin
```

Expected: `Validation passed` (warnings allowed only for the missing `version`). If `"source": "./"` is rejected, use `"."` (the docs allow both), update the test and ledger a Ruling.

- [ ] **Step 6: Commit**

```bash
uv run ruff format tests/test_plugin.py && make check
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json tests/test_plugin.py
git commit -m "feat: Make the repository a Claude Code plugin and marketplace"
```

---

### Task 2: CLI wrapper `bin/nichiyou-daiku`

**Files:**
- Create: `bin/nichiyou-daiku` (mode 755)
- Test: `tests/test_plugin.py` (append)

**Interfaces:**
- Consumes: `ROOT` from Task 1's `tests/test_plugin.py`.
- Produces: `bin/nichiyou-daiku` — same arguments as the CLI. Environment flag `NICHIYOU_DAIKU_WRAPPED=1`. Calls `uv tool run --from <root|nichiyou-daiku[viz] @ root> nichiyou-daiku <args>`.

- [ ] **Step 1: Write the failing tests**

Add to the imports of `tests/test_plugin.py`:

```python
import os
import shutil
import stat
import subprocess

import pytest
```

Append:

```python
WRAPPER = ROOT / "bin" / "nichiyou-daiku"


def _tools(tmp_path: Path) -> Path:
    """Only the utilities the wrapper needs, so a uv or nichiyou-daiku
    installed on this machine stays out of the tests."""
    tools = tmp_path / "tools"
    tools.mkdir(exist_ok=True)
    for name in ("dirname", "basename", "readlink"):
        if not (tools / name).exists():
            (tools / name).symlink_to(shutil.which(name))
    return tools


def _fake(directory: Path, name: str, label: str) -> None:
    """An executable that prints its label, then each argument on a line."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(f'#!/bin/sh\necho {label}\nfor arg in "$@"; do echo "$arg"; done\n')
    path.chmod(0o755)


def _plugin(tmp_path: Path, name: str = "plugin") -> Path:
    """A plugin root holding a copy of the wrapper."""
    bin_dir = tmp_path / name / "bin"
    bin_dir.mkdir(parents=True)
    shutil.copy2(WRAPPER, bin_dir / "nichiyou-daiku")
    return (tmp_path / name).resolve()


def _run(command: Path, *path: Path | str, args=("validate", "my table.nd"), env=None, cwd=None):
    return subprocess.run(
        [str(command), *args],
        env={"PATH": os.pathsep.join(str(p) for p in path), **(env or {})},
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_wrapper_is_an_executable_posix_shell_script():
    assert WRAPPER.read_text().startswith("#!/bin/sh\n")
    assert WRAPPER.stat().st_mode & stat.S_IXUSR
    assert subprocess.run(["sh", "-n", str(WRAPPER)]).returncode == 0


@pytest.mark.parametrize("installed_first", [True, False])
def test_wrapper_runs_an_installed_cli(tmp_path, installed_first):
    root = _plugin(tmp_path)
    _fake(tmp_path / "installed", "nichiyou-daiku", "installed")
    _fake(tmp_path / "uv-bin", "uv", "uv")
    dirs = [tmp_path / "installed", root / "bin"]
    if not installed_first:
        dirs.reverse()
    result = _run(root / "bin" / "nichiyou-daiku", *dirs, tmp_path / "uv-bin", _tools(tmp_path))
    assert result.stdout.splitlines() == ["installed", "validate", "my table.nd"]


def test_wrapper_runs_its_own_source_through_uv(tmp_path):
    root = _plugin(tmp_path)
    _fake(tmp_path / "uv-bin", "uv", "uv")
    result = _run(root / "bin" / "nichiyou-daiku", root / "bin", tmp_path / "uv-bin", _tools(tmp_path))
    assert result.stdout.splitlines() == [
        "uv", "tool", "run", "--from", str(root), "nichiyou-daiku", "validate", "my table.nd",
    ]


@pytest.mark.parametrize(
    "args",
    [("export", "d.nd"), ("drawing", "d.nd"), ("view", "d.nd"), ("-v", "export", "d.nd")],
)
def test_wrapper_adds_the_viz_extra_for_3d_commands(tmp_path, args):
    root = _plugin(tmp_path)
    _fake(tmp_path / "uv-bin", "uv", "uv")
    result = _run(root / "bin" / "nichiyou-daiku", tmp_path / "uv-bin", _tools(tmp_path), args=args)
    assert result.stdout.splitlines()[3:5] == ["--from", f"nichiyou-daiku[viz] @ {root}"]
    assert result.stdout.splitlines()[6:] == list(args)


def test_wrapper_keeps_a_plugin_path_with_spaces_whole(tmp_path):
    root = _plugin(tmp_path, "claude plugins")
    _fake(tmp_path / "uv-bin", "uv", "uv")
    result = _run(root / "bin" / "nichiyou-daiku", tmp_path / "uv-bin", _tools(tmp_path))
    assert result.stdout.splitlines()[4] == str(root)


def test_wrapper_called_by_another_copy_goes_straight_to_uv(tmp_path):
    root = _plugin(tmp_path)
    _fake(tmp_path / "installed", "nichiyou-daiku", "installed")
    _fake(tmp_path / "uv-bin", "uv", "uv")
    result = _run(
        root / "bin" / "nichiyou-daiku",
        tmp_path / "installed",
        tmp_path / "uv-bin",
        _tools(tmp_path),
        env={"NICHIYOU_DAIKU_WRAPPED": "1"},
    )
    assert result.stdout.splitlines()[0] == "uv"


def test_copies_of_the_wrapper_do_not_call_each_other(tmp_path):
    first = _plugin(tmp_path, "first")
    second = _plugin(tmp_path, "second")
    _fake(tmp_path / "uv-bin", "uv", "uv")
    result = _run(
        first / "bin" / "nichiyou-daiku",
        first / "bin",
        second / "bin",
        tmp_path / "uv-bin",
        _tools(tmp_path),
    )
    lines = result.stdout.splitlines()
    assert lines[0] == "uv"
    assert lines[4] in (str(first), str(second))


def test_wrapper_reached_through_a_symlink_uses_the_plugin_root(tmp_path):
    root = _plugin(tmp_path)
    links = tmp_path / "links"
    links.mkdir()
    target = root / "bin" / "nichiyou-daiku"
    (links / "nichiyou-daiku").symlink_to(os.path.relpath(target, links))
    _fake(tmp_path / "uv-bin", "uv", "uv")
    result = _run(links / "nichiyou-daiku", links, tmp_path / "uv-bin", _tools(tmp_path))
    assert result.stdout.splitlines()[4] == str(root)


def test_wrapper_skips_the_current_directory_and_directories(tmp_path):
    root = _plugin(tmp_path)
    _fake(tmp_path / "work", "nichiyou-daiku", "from the current directory")
    (tmp_path / "checkouts" / "nichiyou-daiku").mkdir(parents=True)
    _fake(tmp_path / "uv-bin", "uv", "uv")
    result = _run(
        root / "bin" / "nichiyou-daiku",
        "",  # an empty entry means the current directory
        tmp_path / "checkouts",
        tmp_path / "uv-bin",
        _tools(tmp_path),
        cwd=tmp_path / "work",
    )
    assert result.stdout.splitlines()[0] == "uv"


def test_wrapper_without_cli_or_uv_says_how_to_install(tmp_path):
    root = _plugin(tmp_path)
    result = _run(root / "bin" / "nichiyou-daiku", root / "bin", _tools(tmp_path))
    assert result.returncode == 127
    assert "https://docs.astral.sh/uv/" in result.stderr
    assert 'uv tool install "git+https://github.com/ar90n/nichiyou-daiku"' in result.stderr
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/test_plugin.py -q`
Expected: the 2 manifest tests pass; every wrapper test fails (`FileNotFoundError` for `bin/nichiyou-daiku` / no such file to copy).

- [ ] **Step 3: Write the wrapper**

`bin/nichiyou-daiku`:

```sh
#!/bin/sh
# The nichiyou-daiku CLI for the Claude Code plugin: run an installed CLI if
# there is one, otherwise this plugin's own source through uv (the package is
# not on PyPI)
set -eu

# Follow symlinks so a link to this script still finds the plugin root
real_path() {
  target=$1
  while [ -L "$target" ]; do
    link=$(readlink -- "$target")
    case $link in
      /*) target=$link ;;
      *) target=$(dirname -- "$target")/$link ;;
    esac
  done
  printf '%s/%s\n' "$(CDPATH='' cd -P -- "$(dirname -- "$target")" && pwd -P)" "$(basename -- "$target")"
}

self=$(real_path "$0")
root=$(dirname -- "$(dirname -- "$self")")

# Another copy of this script (a second plugin version on PATH) hands over
# with the flag set, so the copies never exec each other in a loop
if [ -z "${NICHIYOU_DAIKU_WRAPPED:-}" ]; then
  export NICHIYOU_DAIKU_WRAPPED=1
  set -f
  saved_ifs=$IFS
  IFS=:
  for dir in $PATH; do
    # An empty entry means the current directory; never run a file from there
    [ -n "$dir" ] || continue
    candidate=$dir/nichiyou-daiku
    if [ -f "$candidate" ] && [ -x "$candidate" ] && [ "$(real_path "$candidate")" != "$self" ]; then
      IFS=$saved_ifs
      exec "$candidate" "$@"
    fi
  done
  IFS=$saved_ifs
  set +f
fi

if ! command -v uv >/dev/null 2>&1; then
  printf '%s\n' \
    "nichiyou-daiku: found neither an installed nichiyou-daiku nor uv to run the plugin's copy." \
    "Install uv (https://docs.astral.sh/uv/getting-started/installation/) and run the command again," \
    "or install the CLI itself: uv tool install \"git+https://github.com/ar90n/nichiyou-daiku\"" >&2
  exit 127
fi

# 3D export and drawings need build123d, which the viz extra brings
package=$root
for arg in "$@"; do
  case $arg in
    export | drawing | view) package="nichiyou-daiku[viz] @ $root" ;;
  esac
done
exec uv tool run --from "$package" nichiyou-daiku "$@"
```

```bash
chmod 755 bin/nichiyou-daiku
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/test_plugin.py -q`
Expected: all pass (2 manifest + 15 wrapper = 17 passed).

- [ ] **Step 5: Mutation check of the loop guard**

```bash
cp bin/nichiyou-daiku /tmp/wrapper.bak
sed -i '/^  export NICHIYOU_DAIKU_WRAPPED=1$/d' bin/nichiyou-daiku
uv run pytest tests/test_plugin.py -q -k "call_each_other"   # Expected: FAIL (TimeoutExpired)
cp /tmp/wrapper.bak bin/nichiyou-daiku
uv run pytest tests/test_plugin.py -q 2>&1 | tail -1          # Expected: 17 passed
```

- [ ] **Step 6: Commit**

```bash
uv run ruff format tests/test_plugin.py && make check
git add bin/nichiyou-daiku tests/test_plugin.py
git ls-files -s bin/nichiyou-daiku   # Expected: 100755
git commit -m "feat: Add the plugin's nichiyou-daiku CLI wrapper"
```

---

### Task 3: The design skill (moving `prompts/` into `skills/design/`)

**Files:**
- Move: `prompts/system.md` → `skills/design/patterns.md`; `prompts/user-template.md` → `skills/design/requirements.md`;
  `prompts/examples/user-specs/{side-table,two-tier-shelf}.md` and `prompts/examples/nd-output/{side-table,two-tier-shelf,corner-joint}.nd` → `skills/design/examples/`;
  `prompts/examples/python-output/simple-table.py` → `examples/side_table_api.py`
- Delete: `prompts/README.md` (then `prompts/` is gone)
- Create: `skills/design/SKILL.md`
- Modify: `tests/test_docs.py`, `tests/test_plugin.py`, `README.md:57`, `skills/design/examples/corner-joint.nd`
- Test: `tests/test_docs.py`, `tests/test_plugin.py`

**Interfaces:**
- Consumes: `ROOT` from `tests/test_plugin.py`; `bin/nichiyou-daiku` (named in SKILL.md).
- Produces: `skills/design/SKILL.md` (skill `nichiyou-daiku:design`), `skills/design/examples/{side-table,two-tier-shelf}.md` (used by Task 6), `examples/side_table_api.py`.

- [ ] **Step 1: Point the doc tests at the new places**

In `tests/test_docs.py` replace the `MARKDOWN`, `ND_FILES` and `PATH` definitions with:

```python
MARKDOWN = sorted(
    [
        *(p for p in (ROOT / "docs").glob("*.md")),
        ROOT / "README.md",
        *(ROOT / "skills").rglob("*.md"),
    ]
)
ND_FILES = sorted(
    [
        *(ROOT / "examples" / "nd_files").glob("*.nd"),
        *(ROOT / "skills").rglob("*.nd"),
    ]
)
```

```python
# Paths written in code spans or prose, e.g. `skills/design/SKILL.md`. prompts/
# stays listed so a mention of the removed prompts fails
PATH = re.compile(
    r"(?<![\w/.-])((?:docs|prompts|examples|skills|bin|src|tests)/[\w./-]*[\w/])"
)
# Skill bodies name plugin files from the plugin root, the repository root
PLUGIN_PATH = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]*[\w/])")
```

Replace the python example path in `test_python_output_example_builds_a_sound_table`:

```python
    namespace = runpy.run_path(str(ROOT / "examples" / "side_table_api.py"))
```

Replace `test_mentioned_repo_paths_exist` with:

```python
def _missing_mentions(text: str, directory: Path) -> list[str]:
    return [
        *(
            mention
            for mention in PATH.findall(text)
            if not (ROOT / mention).exists() and not (directory / mention).exists()
        ),
        *(mention for mention in PLUGIN_PATH.findall(text) if not (ROOT / mention).exists()),
    ]


def test_missing_mentions_are_found():
    text = "Read `${CLAUDE_PLUGIN_ROOT}/docs/nope.md` and `prompts/system.md`."
    assert _missing_mentions(text, ROOT) == ["prompts/system.md", "docs/nope.md"]


@pytest.mark.parametrize("path", MARKDOWN, ids=lambda p: str(p.relative_to(ROOT)))
def test_mentioned_repo_paths_exist(path):
    # Prompts and skills name files in code spans rather than links
    assert _missing_mentions(path.read_text(), path.parent) == []
```

Append to `tests/test_plugin.py` (add `import re` to its imports):

```python
SKILLS = sorted((ROOT / "skills").glob("*/SKILL.md"))
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def test_the_design_skill_exists():
    assert ROOT / "skills" / "design" / "SKILL.md" in SKILLS


@pytest.mark.parametrize("path", SKILLS, ids=lambda p: p.parent.name)
def test_skill_frontmatter_names_and_describes_the_skill(path):
    header = FRONTMATTER.match(path.read_text())
    assert header is not None
    fields = dict(re.findall(r"^(\w+): (.+)$", header.group(1), re.M))
    assert fields["name"] == path.parent.name
    assert 0 < len(fields["description"]) <= 1024


def test_plugin_root_appears_only_in_skill_bodies():
    # Claude Code substitutes it in SKILL.md; a file read later keeps it literal
    literal = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "skills").rglob("*")
        if path.is_file()
        and path.name != "SKILL.md"
        and "${CLAUDE_PLUGIN_ROOT}" in path.read_text()
    ]
    assert literal == []
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/test_docs.py tests/test_plugin.py -q 2>&1 | tail -5`
Expected: FAIL — `test_python_output_example_builds_a_sound_table` (no `examples/side_table_api.py`), `test_the_design_skill_exists`. `test_missing_mentions_are_found` passes (it checks the helper).

- [ ] **Step 3: Move the files**

```bash
mkdir -p skills/design/examples
git mv prompts/system.md skills/design/patterns.md
git mv prompts/user-template.md skills/design/requirements.md
git mv prompts/examples/user-specs/side-table.md prompts/examples/user-specs/two-tier-shelf.md skills/design/examples/
git mv prompts/examples/nd-output/side-table.nd prompts/examples/nd-output/two-tier-shelf.nd prompts/examples/nd-output/corner-joint.nd skills/design/examples/
git mv prompts/examples/python-output/simple-table.py examples/side_table_api.py
git rm -q prompts/README.md
test ! -e prompts || find prompts   # Expected: no output (prompts/ is gone)
```

- [ ] **Step 4: Trim `patterns.md` to the LLM guidance**

```bash
uv run python - <<'EOF'
from pathlib import Path

path = Path("skills/design/patterns.md")
text = path.read_text()
_, rest = text.split("## Verified Patterns (Follow These Exactly)", 1)
rest = rest.split("### 5. Visual Verification", 1)[0].rstrip() + "\n"
header = (
    "# Design Patterns\n\n"
    "Verified layouts, length formulas and rules for writing `.nd` files. "
    "The DSL specification defines every construct used here.\n\n"
)
path.write_text(
    header
    + "## Verified Patterns (Follow These Exactly)"
    + rest.replace("Before output:", "Before running `validate`:")
)
EOF
head -8 skills/design/patterns.md; tail -4 skills/design/patterns.md
```

Expected: starts with `# Design Patterns`, then `## Verified Patterns (Follow These Exactly)`; ends with the checklist line `- [ ] Lengths match the formulas above ...`; no `Output Format`, `DSL Specification` or `Visual Verification` section (`grep -c 'Output Format\|Visual Verification\|## DSL Specification' skills/design/patterns.md` → 0).

- [ ] **Step 5: Turn the template into the requirements list**

Replace the first 5 lines of `skills/design/requirements.md` (`# Furniture Design Specification` … `- Output format: [nd / python]`) with:

```markdown
# Furniture Requirements

What a design needs. Ask the user only for the items the request leaves open and that change the design; choose the rest and say what you chose. The specs in [examples/](examples/) are filled in.

## Basic Info
- Name:
```

Drop the output-format line from the example specs:

```bash
sed -i '/^- Output format: /d' skills/design/examples/side-table.md skills/design/examples/two-tier-shelf.md
grep -rn 'Output format' skills/   # Expected: no output
```

- [ ] **Step 6: Fix the corner example**

`skills/design/examples/corner-joint.nd` says the pieces meet at 90 degrees, but `TF<0 DF<0` is the end-to-end joint in `patterns.md`. Replace the file with:

```nd
// Minimal Corner Joint Example
// Two 2x4 pieces connected at 90 degrees

(piece_a:2x4 =400)
(piece_b:2x4 =400)

// piece_b lies across piece_a's top end (back face down), its down end
// flush with piece_a's front face
piece_a -[TF<0 BD<0]- piece_b
```

- [ ] **Step 7: Point the Python example at its .nd twin**

In `examples/side_table_api.py` replace `Equivalent to the side-table.nd DSL example, with the lengths and offsets` with `Equivalent to skills/design/examples/side-table.nd, with the lengths and offsets`.

- [ ] **Step 8: Write the skill**

`skills/design/SKILL.md`:

````markdown
---
name: design
description: Design DIY furniture from standard 1x/2x SPF lumber (1x4, 2x4, 2x2, ...) as a nichiyou-daiku .nd file, then check and fix it with the nichiyou-daiku CLI. Use when the user wants to design, size or change a table, shelf, bench, rack or other furniture built from 2x4/1x4 lumber, or works on a .nd file.
---

# Design furniture with nichiyou-daiku

Write the furniture as a `.nd` file (the nichiyou-daiku DSL), check it with the `nichiyou-daiku` CLI and fix it until it is sound. Work in the user's project directory.

## 1. Settle the requirements

Check the request against [requirements.md](requirements.md). Ask only for what is missing and changes the design: the overall width × depth × height, the lumber and the joints. Where the user doesn't care, choose (a 2x4 frame, `8x30` dowels for the frame, screws for boards) and say what you chose.

## 2. Read

- The DSL specification: `${CLAUDE_PLUGIN_ROOT}/docs/dsl-specification.md`. Every rule in it applies: faces and offsets, placement, variables, unknowns, fasteners.
- [patterns.md](patterns.md): verified joints and layouts, length formulas, naming and a checklist.
- [examples/](examples/): requirements with a matching `.nd` (a side table, a two-tier shelf, a corner joint). Start from the closest one.

## 3. Write

Create `<name>.nd`. Name the overall sizes as variables and derive lengths and offsets from them; leave a length unknown (`=?`) where the pieces at both ends fix it. Put the overall size in a comment at the top and group the pieces by section.

## 4. Check and fix

Run `nichiyou-daiku validate <name>.nd`. Fix every error and warning it reports and run it again, until the model is valid. The messages name the piece or connection and say how to fix it. If the same problem survives three attempts, stop and explain it to the user with what you tried.

## 5. Compare with the request

Run `nichiyou-daiku report <name>.nd`. Check the overall size against the request, and read the bill of materials and the shopping list. If the size is off, fix the lengths or offsets and go back to step 4.

## 6. Output files on request

- Drawing: `nichiyou-daiku drawing <name>.nd -o <name>.pdf`
- 3D model: `nichiyou-daiku export <name>.nd -f step` (or `-f stl`)

The first run of these installs build123d and can take a few minutes; tell the user.

## 7. Report

Tell the user the file path, the overall size, the lumber to buy (from the shopping list) and any warning left, with its reason.

## The CLI

`nichiyou-daiku` runs an installed nichiyou-daiku if there is one, otherwise this plugin's own copy through uv. If it says it found neither, ask the user to install uv.
````

- [ ] **Step 9: Replace the prompts link in the README**

In `README.md` replace

```markdown
- [LLM prompts](prompts/README.md): generate designs with an LLM
```

with

```markdown
- [Design skill](skills/design/SKILL.md): the Claude Code skill that designs furniture and checks it with the CLI
```

- [ ] **Step 10: Run the tests to see them pass**

Run: `uv run pytest tests/test_docs.py tests/test_plugin.py -q 2>&1 | tail -3`
Expected: all pass, including `test_example_files_are_sound[corner-joint.nd]`, `[side-table.nd]`, `[two-tier-shelf.nd]` and `test_mentioned_repo_paths_exist[skills/design/SKILL.md]`.

- [ ] **Step 11: Mutation checks of the new guards**

Back up with `cp`, not git: the Step 4 edit is not staged yet, so a git restore would drop it.

```bash
cp skills/design/patterns.md /tmp/patterns.bak && cp skills/design/SKILL.md /tmp/skill.bak
printf '\nSee ${CLAUDE_PLUGIN_ROOT}/docs/dsl-specification.md\n' >> skills/design/patterns.md
uv run pytest tests/test_plugin.py -q -k plugin_root   # Expected: FAIL, literal == ['skills/design/patterns.md']
sed -i 's|docs/dsl-specification.md`|docs/dsl-spec.md`|' skills/design/SKILL.md
uv run pytest tests/test_docs.py -q -k "SKILL"          # Expected: FAIL, missing docs/dsl-spec.md
cp /tmp/patterns.bak skills/design/patterns.md && cp /tmp/skill.bak skills/design/SKILL.md
uv run pytest tests/test_docs.py tests/test_plugin.py -q 2>&1 | tail -1   # Expected: all pass
```

- [ ] **Step 12: Commit**

```bash
uv run ruff format tests/ && make check
git add -A prompts skills examples/side_table_api.py tests/test_docs.py tests/test_plugin.py README.md
git status --short   # Expected: nothing unstaged or untracked left
git commit -m "feat: Replace the prompts with the nichiyou-daiku:design skill"
```

---

### Task 4: README — Claude Code and installing from GitHub

**Files:**
- Modify: `README.md` (the `## Installation` section)
- Test: `tests/test_docs.py` (existing link and path tests)

**Interfaces:**
- Consumes: plugin and marketplace names from Task 1, the skill name from Task 3.

- [ ] **Step 1: Check the install commands work, in a throwaway tool directory**

```bash
export UV_TOOL_DIR=/tmp/ndk-tools/tools UV_TOOL_BIN_DIR=/tmp/ndk-tools/bin
rm -rf /tmp/ndk-tools
uv tool install "git+https://github.com/ar90n/nichiyou-daiku"
/tmp/ndk-tools/bin/nichiyou-daiku validate examples/nd_files/simple_table.nd
uv tool install --force "nichiyou-daiku[viz] @ git+https://github.com/ar90n/nichiyou-daiku"
/tmp/ndk-tools/bin/nichiyou-daiku drawing examples/nd_files/simple_table.nd -o /tmp/ndk-tools/t.pdf
ls -l /tmp/ndk-tools/t.pdf
unset UV_TOOL_DIR UV_TOOL_BIN_DIR
```

Expected: `✓ Model is valid`, then `Successfully created technical drawing: /tmp/ndk-tools/t.pdf` and a non-empty PDF. If a command fails, change it until it works and use the working form in Step 2 (ledger a Ruling).

- [ ] **Step 2: Rewrite the Installation section**

In `README.md` replace the whole `## Installation` section (from `## Installation` up to, not including, `## Documentation`) with:

````markdown
## Use with Claude Code

Add this repository as a plugin marketplace and install the plugin:

```text
/plugin marketplace add ar90n/nichiyou-daiku
/plugin install nichiyou-daiku@nichiyou-daiku
```

Then ask for furniture, e.g. "Design a 500 x 400 x 600 side table from 2x4". The `nichiyou-daiku:design` skill writes the `.nd` file, checks it with the CLI until it is sound and reports the size and the lumber to buy. The plugin runs an installed CLI if there is one, otherwise its own copy through [uv](https://docs.astral.sh/uv/).

## Installation

nichiyou-daiku is not on PyPI. Install the CLI from GitHub with uv:

```bash
uv tool install "git+https://github.com/ar90n/nichiyou-daiku"                       # core and CLI
uv tool install "nichiyou-daiku[viz] @ git+https://github.com/ar90n/nichiyou-daiku"  # plus 3D export and drawings (build123d)
```

> **Note** build123d currently has limited support for ARM64/aarch64. The core works everywhere.

````

- [ ] **Step 3: Run the doc tests**

Run: `uv run pytest tests/test_docs.py -q 2>&1 | tail -1`
Expected: all pass. `grep -n 'pip install' README.md` → no output.

- [ ] **Step 4: Commit**

```bash
make check
git add README.md
git commit -m "docs: Install from GitHub and as a Claude Code plugin"
```

---

### Task 5: Check the plugin as installed, and the local notes

No commit: these are the spec's manual checks. `CLAUDE.md` is local and untracked.

**Interfaces:**
- Consumes: everything committed in Tasks 1–4.
- Produces: `/tmp/ndk-plugin` (a clean copy of HEAD), used by Task 6.

- [ ] **Step 1: A clean copy of HEAD, validated**

```bash
rm -rf /tmp/ndk-plugin && mkdir /tmp/ndk-plugin && git archive HEAD | tar -x -C /tmp/ndk-plugin
claude plugin validate /tmp/ndk-plugin
```

Expected: `Validation passed` (warnings only for the missing `version`).

- [ ] **Step 2: The wrapper through uv, writing nothing into the plugin**

```bash
rm -rf /tmp/ndk-run && mkdir -p /tmp/ndk-run && cp examples/nd_files/simple_table.nd /tmp/ndk-run/ && touch /tmp/ndk-run/marker
(
  export PATH=$(echo "$PATH" | tr ':' '\n' | grep -v -e '/\.local/bin' -e '/nichiyou-daiku/\.venv' | paste -sd:)
  command -v nichiyou-daiku || echo "no CLI on PATH"   # Expected: no CLI on PATH
  cd /tmp/ndk-run
  /tmp/ndk-plugin/bin/nichiyou-daiku validate simple_table.nd
  /tmp/ndk-plugin/bin/nichiyou-daiku drawing simple_table.nd -o simple_table.pdf
)
find /tmp/ndk-plugin -newer /tmp/ndk-run/marker   # Expected: no output
```

Expected: `no CLI on PATH`, `✓ Model is valid`, `Successfully created technical drawing: simple_table.pdf`, and no file under `/tmp/ndk-plugin` newer than the marker.

- [ ] **Step 3: Claude Code sees the skill**

```bash
cd /tmp/ndk-run && claude -p --model haiku --plugin-dir /tmp/ndk-plugin --setting-sources project,local \
  --output-format stream-json --verbose --max-turns 1 "Reply with OK" | head -1 | grep -o 'nichiyou-daiku:design' | head -1
```

Expected: `nichiyou-daiku:design`. If the first (init) line doesn't list skills, drop `head -1` and search the whole stream.

- [ ] **Step 4: Update the local CLAUDE.md (untracked)**

In `CLAUDE.md`:
- Replace `- ドットファイル（`.claude/` など）はコミットしない。この CLAUDE.md も git 管理外。` with
  `- ドットファイル（`.claude/` など）はコミットしない（例外: `.github/` と、プラグインの `.claude-plugin/`）。この CLAUDE.md も git 管理外。`
- Append to `## 構成と責務`:
  `- プラグイン: `.claude-plugin/`（plugin.json・marketplace.json。リポジトリのルートがプラグイン）、`skills/design/`（設計スキル）、`bin/nichiyou-daiku`（入っている CLI か、同梱のソースを `uv tool run` で動かす）`
- Replace `- LLM 用プロンプト: `prompts/system.md`（LLM 向けの作例と規則だけ。仕様は docs を一緒に渡す）` with
  `- 設計スキル: `skills/design/SKILL.md`（手順）、`patterns.md`（作例と規則）。仕様は `${CLAUDE_PLUGIN_ROOT}/docs/` を参照`
- Replace `作例を変えるなら `prompts/system.md` を直す` with `作例を変えるなら `skills/design/patterns.md` を直す`

`grep -n prompts CLAUDE.md` → no output.

---

### Task 6: Does the skill work? (sonnet, headless, 3 requests × 2)

**Files:**
- Modify: `docs/superpowers/specs/2026-10-12-design-skill-plugin-design.md` (status and result line)
- Scratch (not committed): `$WS/eval/` where `$WS` is this plan's workspace from `sdd-workspace`

**Interfaces:**
- Consumes: `/tmp/ndk-plugin` from Task 5 (rebuild it with Task 5 Step 1 if HEAD changed).

`WS` is this plan's workspace, the path `sdd-workspace docs/superpowers/plans/2026-10-12-design-skill-plugin.md` prints
(`/home/argon/workspace/nichiyou-daiku/.superpowers/sdd/2026-10-12-design-skill-plugin`). Set it in every command below.

- [ ] **Step 1: Write the requests**

```bash
mkdir -p $WS/eval
SUFFIX='質問はせず、決まっていないところは既定値で進めて。ファイルはカレントディレクトリに書いて。'
echo "幅500×奥行400×高さ600mmのサイドテーブルを2x4材で設計して。脚は4本、幕板は脚の上端にそろえる。天板も2x4を奥行方向に並べる。接合は8x30のダボ。$SUFFIX" > $WS/eval/side-table.txt
echo "幅600×奥行300×高さ800mmの2段の棚を設計して。骨組みは2x4、天板は1x4を奥行方向に並べる。脚は4本で、幕板は上端と床から150mmの2か所。下の段の棚板は2x4で下の幕板に載せる。接合は8x30のダボ。$SUFFIX" > $WS/eval/two-tier-shelf.txt
echo "2x2材で花台を作りたい。幅400×奥行300×高さ700mm。天板は1x4、床から200mmの位置に棚を1段。$SUFFIX" > $WS/eval/plant-stand.txt
```

- [ ] **Step 2: Run 6 sessions in parallel (background)**

Run this with the Bash tool's `run_in_background` (it outlasts the 10-minute tool timeout) and wait for its notification.

```bash
CLEAN_PATH=$(echo "$PATH" | tr ':' '\n' | grep -v -e '/\.local/bin' -e '/nichiyou-daiku/\.venv' | paste -sd:)
for case in side-table two-tier-shelf plant-stand; do for n in 1 2; do
  dir=$WS/eval/$case-$n; rm -rf $dir; mkdir -p $dir
  (cd $dir && env PATH="$CLEAN_PATH" $HOME/.local/bin/claude -p --model sonnet --plugin-dir /tmp/ndk-plugin \
     --setting-sources project,local \
     --allowedTools "Read,Write,Edit,Glob,Grep,Skill,Bash(nichiyou-daiku:*),Bash(ls:*),Bash(cat:*)" \
     --output-format stream-json --verbose "$(cat $WS/eval/$case.txt)" > run.jsonl 2> err.log) &
done; done; wait
```

`--setting-sources project,local` keeps the user's own plugins and hooks out; the PATH without `~/.local/bin` keeps the user's stale `uv tool` CLI out, so the wrapper runs the plugin's copy.

- [ ] **Step 3: Score the runs**

`$WS/eval/score.py`:

```python
"""Score the design skill runs: skill used, validate passes, size matches."""

import json
import re
import subprocess
import sys
from pathlib import Path

CLI = "/home/argon/workspace/nichiyou-daiku/.venv/bin/nichiyou-daiku"
WANTED = {
    "side-table": [400, 500, 600],
    "two-tier-shelf": [300, 600, 800],
    "plant-stand": [300, 400, 700],
}
SIZE = re.compile(r"Overall Size \(X × Y × Z\)\*\*: ([\d.]+) × ([\d.]+) × ([\d.]+)")

for run in sorted(p for p in Path(sys.argv[1]).iterdir() if p.is_dir()):
    case = run.name.rsplit("-", 1)[0]
    events = [json.loads(line) for line in (run / "run.jsonl").read_text().splitlines() if line.strip()]
    uses = [
        block
        for event in events
        if event.get("type") == "assistant"
        for block in event["message"]["content"]
        if block.get("type") == "tool_use"
    ]
    skill = any(u["name"] == "Skill" and "design" in json.dumps(u["input"]) for u in uses)
    validates = sum(
        u["name"] == "Bash" and "nichiyou-daiku validate" in u["input"].get("command", "")
        for u in uses
    )
    nd_files = sorted(run.glob("*.nd"))
    if not nd_files:
        print(f"{run.name}: skill={skill} validate_calls={validates} NO .nd")
        continue
    nd = nd_files[0]
    valid = subprocess.run([CLI, "validate", str(nd)], capture_output=True, text=True).returncode == 0
    report = subprocess.run([CLI, "report", str(nd)], capture_output=True, text=True).stdout
    match = SIZE.search(report)
    size = sorted(float(v) for v in match.groups()) if match else None
    ok = size is not None and all(abs(a - b) <= 1 for a, b in zip(size, WANTED[case]))
    print(f"{run.name}: skill={skill} validate_calls={validates} valid={valid} size={size} match={ok} file={nd.name}")
```

Run: `.venv/bin/python $WS/eval/score.py $WS/eval`
Expected (pass bar from the spec): all 6 runs `skill=True valid=True match=True`, and `validate_calls >= 1`.

- [ ] **Step 4: If a run misses the bar, improve the skill and rerun**

Read the failing run's `run.jsonl` (the agent's last messages and the validate output) to find the cause. Fix `skills/design/SKILL.md` or `patterns.md` (not the CLI), run `make check`, commit (`fix: ...`), rebuild `/tmp/ndk-plugin` (Task 5 Step 1) and rerun Steps 2–3 for all 6. Ledger each round. After two rounds without reaching the bar, stop and report the runs to the user.

- [ ] **Step 5: Record the result in the spec and commit**

In the spec, set `- ステータス: 実装済み（ブランチ docs/single-source）` and add after it a line in the style of the docs single-source spec:
`- 効果の確認: sonnet・非対話で 3 依頼 × 2 回。スキル <n>/6、validate <n>/6、外形寸法 <n>/6（validate の呼び出しは 1 回あたり <min>〜<max> 回）。`
filled in from the score output.

```bash
make check
git add docs/superpowers/specs/2026-10-12-design-skill-plugin-design.md
git commit -m "docs: Mark the design skill plugin spec implemented"
```
