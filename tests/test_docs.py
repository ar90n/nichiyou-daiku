"""Keep the docs honest: examples, tables and links must match the code."""

import doctest
import json
import re
import runpy
from pathlib import Path

import pytest
from click.testing import CliRunner

from nichiyou_daiku.cli.dsl_cli import cli
from nichiyou_daiku.core.assembly import Assembly
from nichiyou_daiku.core.dowel import Dowel
from nichiyou_daiku.core.piece import PieceType, get_shape
from nichiyou_daiku.core.placement import find_overlaps, overall_bounds
from nichiyou_daiku.core.screw import CoarseThreadScrew, SlimScrew
from nichiyou_daiku.dsl import parse_dsl
from nichiyou_daiku.shell.cutting import DEFAULT_STANDARD_LENGTHS
from nichiyou_daiku.shell.stock import load_stock

ROOT = Path(__file__).parents[1]
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
OPENING = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([\w-]*)")
# Inline links, with an optional <...> target and "title", and reference
# definitions such as [spec]: docs/dsl-specification.md
LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
REFERENCE = re.compile(r"^\s*\[[^\]]+\]:\s*<?(\S+?)>?(?:\s+\"[^\"]*\")?\s*$", re.M)
# Paths written in code spans or prose, e.g. `skills/design/SKILL.md`. prompts/
# stays listed so a mention of the removed prompts fails
PATH = re.compile(
    r"(?<![\w/.-])((?:docs|prompts|examples|skills|bin|src|tests)/[\w./-]*[\w/])"
)
# Skill bodies name plugin files from the plugin root, the repository root
PLUGIN_PATH = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]*[\w/])")
DSL_SPEC = (ROOT / "docs" / "dsl-specification.md").read_text()


def _fences(text: str) -> list[tuple[int, str, str]]:
    """(line, language, body) of each fenced block, indented or not."""
    lines = text.splitlines(keepends=True)
    blocks = []
    i = 0
    while i < len(lines):
        opening = OPENING.match(lines[i])
        if opening is None:
            i += 1
            continue
        indent, fence, language = opening.groups()
        closing = re.compile(rf"^\s*{re.escape(fence[0])}{{{len(fence)},}}\s*$")
        body = []
        j = i + 1
        while j < len(lines) and not closing.match(lines[j]):
            line = lines[j]
            body.append(line[len(indent) :] if line.startswith(indent) else line)
            j += 1
        blocks.append((i + 1, language, "".join(body)))
        i = j + 1
    return blocks


def _blocks(*languages: str) -> list[tuple[str, str]]:
    return [
        (f"{path.relative_to(ROOT)}:{line}", body)
        for path in MARKDOWN
        for line, language, body in _fences(path.read_text())
        if language in languages
    ]


def _problems(source: str) -> list[str]:
    model = parse_dsl(source)
    assembly = Assembly.of(model)
    return [
        *(
            f"conflict {c.base_id} -> {c.target_id}"
            for c in assembly.placement.conflicts
        ),
        *(f"overlap {o.lhs}/{o.rhs}" for o in find_overlaps(model, assembly.placement)),
        *(f"fastener {i.base_id} -> {i.target_id}" for i in assembly.fastener_issues),
    ]


ND_BLOCKS = _blocks("nd")


def test_every_nd_fence_is_collected():
    # A parser slip would silently drop examples from the test above
    opening = re.compile(r"^\s*(`{3,}|~{3,})\s*nd\b", re.M)
    written = sum(len(opening.findall(path.read_text())) for path in MARKDOWN)
    assert len(ND_BLOCKS) == written > 0


@pytest.mark.parametrize(
    ("where", "source"), ND_BLOCKS, ids=[where for where, _ in ND_BLOCKS]
)
def test_nd_examples_in_the_docs_are_sound(where, source):
    assert _problems(source) == []


@pytest.mark.parametrize("path", ND_FILES, ids=lambda p: p.name)
def test_example_files_are_sound(path):
    assert _problems(path.read_text()) == []


def test_python_output_example_builds_a_sound_table():
    namespace = runpy.run_path(str(ROOT / "examples" / "side_table_api.py"))
    assembly = namespace["main"]()
    assert assembly.placement.conflicts == ()
    assert find_overlaps(assembly.model, assembly.placement) == ()
    assert assembly.fastener_issues == ()
    assert len(assembly.placement.groups) == 1
    low, high = overall_bounds(assembly.model, assembly.placement)
    size = sorted(round(v, 6) for v in (high.x - low.x, high.y - low.y, high.z - low.z))
    assert size == [400.0, 500.0, 600.0]  # the 500 x 400 x 600 side table


def test_api_spec_examples_run():
    text = (ROOT / "docs" / "api-specification.md").read_text()
    blocks = [
        (line + 1, body)
        for line, language, body in _fences(text)
        if language in ("python", "py")
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
    results = runner.summarize(verbose=False)
    assert results.failed == 0
    assert results.attempted > 0


def test_the_stock_file_example_reads_as_described(tmp_path):
    [example] = [body for _, language, body in _fences(DSL_SPEC) if language == "toml"]
    path = tmp_path / "stock.toml"
    path.write_text(example)
    stock = load_stock(path)
    assert stock.kerf == 2
    assert stock.lengths[PieceType.PT_1x4] == [910, 1820]
    # Lumber types left out keep the defaults
    assert stock.lengths[PieceType.PT_2x6] == DEFAULT_STANDARD_LENGTHS[PieceType.PT_2x6]


def test_lumber_table_matches_the_code():
    section = DSL_SPEC.split("### Lumber Types", 1)[1].split("###", 1)[0]
    rows = re.findall(r"^\| `(\d+x\d+)` \| (\d+) \| (\d+) \|", section, re.M)
    documented = {name: (float(w), float(t)) for name, w, t in rows}
    actual = {t.value: (get_shape(t).width, get_shape(t).height) for t in PieceType}
    assert documented == actual


def test_preset_tables_match_the_code():
    # Lumber rows look like dowel rows, so read only the dowel section
    dowel_section = DSL_SPEC.split("### Dowel Connection", 1)[1].split("### Screw", 1)[
        0
    ]
    dowels = set(
        re.findall(r"^\| `(\d+x\d+)` \| [\d.]+ \| [\d.]+ \|", dowel_section, re.M)
    )
    screws = set(
        re.findall(r"^\| `((?:Slim|Coarse):[\d.]+x[\d.]+)` \|", DSL_SPEC, re.M)
    )
    assert dowels == {preset.value for preset in Dowel}
    assert screws == {f"Slim:{p.value}" for p in SlimScrew} | {
        f"Coarse:{p.value}" for p in CoarseThreadScrew
    }


@pytest.mark.parametrize("path", MARKDOWN, ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_links_point_at_existing_files(path):
    text = path.read_text()
    missing = []
    for target in [*LINK.findall(text), *REFERENCE.findall(text)]:
        if re.match(r"^(https?:|mailto:|#)", target):
            continue
        file_part = target.split("#", 1)[0]
        if not (path.parent / file_part).exists():
            missing.append(target)
    assert missing == []


def _missing_mentions(text: str, directory: Path) -> list[str]:
    return [
        *(
            mention
            for mention in PATH.findall(text)
            if not (ROOT / mention).exists() and not (directory / mention).exists()
        ),
        *(
            mention
            for mention in PLUGIN_PATH.findall(text)
            if not (ROOT / mention).exists()
        ),
    ]


def test_missing_mentions_are_found():
    text = "Read `${CLAUDE_PLUGIN_ROOT}/docs/nope.md` and `prompts/system.md`."
    assert _missing_mentions(text, ROOT) == ["prompts/system.md", "docs/nope.md"]


@pytest.mark.parametrize("path", MARKDOWN, ids=lambda p: str(p.relative_to(ROOT)))
def test_mentioned_repo_paths_exist(path):
    # Prompts and skills name files in code spans rather than links
    assert _missing_mentions(path.read_text(), path.parent) == []


def test_validate_json_example_matches_the_cli():
    command = "validate --json examples/nd_files/corner_angle_compact.nd"
    blocks = _fences(DSL_SPEC)
    index = next(i for i, (_, _, body) in enumerate(blocks) if command in body)
    _, language, documented = blocks[index + 1]
    assert language == "json"
    result = CliRunner().invoke(
        cli, ["validate", "--json", str(ROOT / command.split()[-1])]
    )
    assert json.loads(documented) == json.loads(result.stdout)


def test_every_cli_command_is_documented():
    # The DSL specification is the CLI's reference
    missing = [
        name for name in cli.commands if f"nichiyou-daiku {name}" not in DSL_SPEC
    ]
    assert missing == []
