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
        *(
            f"conflict {c.base_id} -> {c.target_id}"
            for c in assembly.placement.conflicts
        ),
        *(f"overlap {o.lhs}/{o.rhs}" for o in find_overlaps(model, assembly.placement)),
        *(f"fastener {i.base_id} -> {i.target_id}" for i in assembly.fastener_issues),
    ]


ND_BLOCKS = _blocks("nd")


@pytest.mark.parametrize(
    ("where", "source"), ND_BLOCKS, ids=[where for where, _ in ND_BLOCKS]
)
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
    missing = []
    for target in LINK.findall(path.read_text()):
        if re.match(r"^(https?:|mailto:|#)", target):
            continue
        file_part = target.split("#", 1)[0]
        if not (path.parent / file_part).exists():
            missing.append(target)
    assert missing == []
