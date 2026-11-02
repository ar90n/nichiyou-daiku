"""Collect .nd sources and write the Rust core's golden files with the Python version.

    rm -f /tmp/nd-captured.jsonl
    ND_CAPTURE=/tmp/nd-captured.jsonl PYTHONPATH=. .venv/bin/python -m pytest \\
        -p tools.capture_dsl tests/ -q
    .venv/bin/python tools/make_goldens.py --captured /tmp/nd-captured.jsonl

Each source becomes NAME.nd, NAME.validate.json (what `validate --json` prints),
NAME.holes.json (every piece's holes and each connection's fasteners),
NAME.steps.json (the parts, the assembly steps with their fasteners and
dimensions), NAME.parts.json (what each drilled part's drawing says) and
NAME.chains.json (the technical drawing's chain dimensions); the last four
only when the source assembles. `--steps-only` writes the steps, parts and
chains files again for the corpus that is there. `--cli` writes what the CLI
prints (NAME.cli-validate.txt and, for examples,
NAME.cli-validate-json.txt), NAME.steps.md (the steps command's page) and,
for the examples and the documents' examples, NAME.render.json (what the
check image labels and notes), and the option cases in
crates/nichiyou-daiku-cli/tests/cli. The report's golden files are the Rust CLI's own
since countersinks (2026-11-02): ND_BLESS=1 cargo test -p nichiyou-daiku-cli
writes them.
"""

import argparse
import contextlib
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from click.testing import CliRunner  # noqa: E402

from nichiyou_daiku.cli.commands.validate import _classify  # noqa: E402
from nichiyou_daiku.cli.dsl_cli import cli  # noqa: E402
from nichiyou_daiku.core.assembly import Assembly  # noqa: E402
from nichiyou_daiku.core.assembly.parts import (  # noqa: E402
    face_letters,
    face_point,
    face_size,
    part_groups,
)
from nichiyou_daiku.core.assembly.steps import plan_steps  # noqa: E402
from nichiyou_daiku.core.placement import overall_bounds  # noqa: E402
from nichiyou_daiku.core.geometry import Point3D  # noqa: E402
from nichiyou_daiku.core.placement import round_mm  # noqa: E402
from nichiyou_daiku.dsl import parse_dsl  # noqa: E402
from nichiyou_daiku.shell.diagnostics import (  # noqa: E402
    failure_report,
    validation_report,
)
from nichiyou_daiku.shell.dimensioning import (  # noqa: E402
    chain_for,
    chain_from_stops,
    chains,
)
from nichiyou_daiku.shell.parts import part_title  # noqa: E402
from nichiyou_daiku.shell.instructions import grouping_hint, steps_markdown  # noqa: E402
from nichiyou_daiku.shell.resources import count_hardware  # noqa: E402
from nichiyou_daiku.shell.views import axis_view, project  # noqa: E402
from tests.test_docs import ND_BLOCKS, ND_FILES  # noqa: E402

CORPUS = ROOT / "crates" / "nichiyou-daiku-core" / "tests" / "corpus"
GENERATED = (
    "*.nd",
    "*.validate.json",
    "*.holes.json",
    "*.steps.json",
    "*.parts.json",
    "*.chains.json",
)


def sources(captured: Path | None):
    for path in ND_FILES:
        yield "example", path.read_text(encoding="utf-8")
    for _, source in ND_BLOCKS:
        yield "doc", source
    for path in sorted((ROOT / "evals" / "design" / "runs").rglob("*.nd")):
        yield "eval", path.read_text(encoding="utf-8")
    if captured is not None:
        for line in captured.read_text(encoding="utf-8").splitlines():
            yield "test", json.loads(line)


def holes(assembly: Assembly) -> dict:
    pieces = {}
    for piece_id, entries in assembly.pilot_holes.items():
        box = assembly.boxes[piece_id]
        listed = []
        for at, hole in entries:
            point = Point3D.of(box, at)
            listed.append(
                {
                    "face": at.face,
                    "center": [round_mm(point.x), round_mm(point.y), round_mm(point.z)],
                    "diameter": round_mm(hole.diameter),
                    "depth": None if hole.depth is None else round_mm(hole.depth),
                }
            )
        pieces[piece_id] = sorted(listed, key=lambda h: (h["face"], h["center"]))
    fasteners: list[dict] = []
    for fastener in assembly.fasteners:
        key = {
            "base": fastener.base_id,
            "target": fastener.target_id,
            "kind": fastener.kind,
            "diameter": round_mm(fastener.diameter),
        }
        if fasteners and all(fasteners[-1][k] == v for k, v in key.items()):
            fasteners[-1]["count"] += 1
        else:
            fasteners.append({**key, "count": 1})
    return {"pieces": pieces, "fasteners": fasteners}


def step_dimensions(assembly: Assembly, step, origin) -> list[dict]:
    """The step's chains as the CLI's step image picks them (instructions.py:
    _dimension_view), moved to the model's origin."""
    view = axis_view(*step.view)
    partners = {p for key in step.connections for p in key if p not in step.pieces}
    chosen = [*step.pieces, *sorted(partners)]
    model, poses = assembly.model, assembly.placement.poses
    world = {p: poses[p].bounds(model.pieces[p]) for p in step.shown}
    chains = []
    for axis in (a for a in range(3) if a != step.view[0]):
        unit = [0.0, 0.0, 0.0]
        unit[axis] = 1.0
        x, y = project(view, unit)
        side = "below" if abs(x) > abs(y) else "left"
        name = "xyz"[axis]
        chain = chain_for(view.caption, name, side, world, dict(model.pieces), chosen)
        shift = getattr(origin, name)
        chains.append(
            {
                "axis": name,
                "side": side,
                "stops": [round_mm(s - shift) for s in chain.stops],
                "segments": [
                    {
                        "start": round_mm(s.start - shift),
                        "end": round_mm(s.end - shift),
                        "lumber": s.lumber,
                    }
                    for s in chain.segments
                ],
            }
        )
    return chains


def steps_report(assembly: Assembly) -> dict:
    """The parts, the steps with their fasteners, and the grouping hint, as
    the Rust core's view gives them."""
    plan = plan_steps(assembly)
    origin = overall_bounds(assembly.model, assembly.placement)[0]
    return {
        "parts": [
            {
                "pieces": list(group.pieces),
                "type": assembly.model.pieces[group.pieces[0]].type.value,
                "length": round_mm(group.size[2]),
                "count": len(group.pieces),
                "drilled": bool(group.holes),
            }
            for group in part_groups(assembly)
        ],
        "steps": [
            {
                "number": step.number,
                "name": step.name,
                "kind": step.kind,
                "pieces": list(step.pieces),
                "connections": [list(key) for key in step.connections],
                "shown": list(step.shown),
                "view": {"axis": "xyz"[step.view[0]], "side": step.view[1]},
                "hardware": [
                    {"name": item.name, "count": item.count}
                    for item in count_hardware(assembly, step.connections)
                ],
                "dimensions": step_dimensions(assembly, step, origin),
            }
            for step in plan.steps
        ],
        "steps_declared": plan.declared,
        "steps_hint": grouping_hint(plan),
    }


def chains_report(assembly: Assembly) -> list[dict]:
    """The technical drawing's chains (dimensioning.chains), moved to the
    model's origin as the step dimensions are."""
    found = chains(assembly)
    if not found:
        return []
    origin = overall_bounds(assembly.model, assembly.placement)[0]
    reports = []
    for chain in found:
        shift = getattr(origin, chain.axis)
        reports.append(
            {
                "view": chain.view,
                "axis": chain.axis,
                "side": chain.side,
                "stops": [round_mm(s - shift) for s in chain.stops],
                "segments": [
                    {
                        "start": round_mm(s.start - shift),
                        "end": round_mm(s.end - shift),
                        "lumber": s.lumber,
                    }
                    for s in chain.segments
                ],
            }
        )
    return reports


def parts_report(assembly: Assembly) -> dict:
    """What each drilled part's drawing says: its title, the letters of its
    faces and each drilled face's stops along its right and up."""
    parts = []
    for index, group in enumerate(part_groups(assembly)):
        if not group.holes:
            continue
        letters = face_letters(group.holes, group.size)
        faces = []
        for face in (f for f in letters if any(h.face == f for h in group.holes)):
            width, height = face_size(face, group.size)
            us, vs = [0.0, width], [0.0, height]
            for hole in group.holes:
                if hole.face == face:
                    u, v = face_point(face, hole.point, group.size)
                    us.append(u)
                    vs.append(v)
            faces.append(
                {
                    "face": face,
                    "right": [
                        round_mm(s)
                        for s in chain_from_stops("v", "x", "below", us).stops
                    ],
                    "up": [
                        round_mm(s)
                        for s in chain_from_stops("v", "z", "left", vs).stops
                    ],
                }
            )
        parts.append(
            {
                "index": index,
                "title": part_title(assembly, group),
                "letters": dict(letters),
                "faces": faces,
            }
        )
    return {"parts": parts}


def reports(
    source: str,
) -> tuple[dict, dict | None, dict | None, dict | None, list | None]:
    try:
        model = parse_dsl(source)
    except Exception as error:
        report = failure_report(_classify(error)[0], error)
        return report.model_dump(mode="json"), None, None, None, None
    try:
        assembly = Assembly.of(model)
    except Exception as error:
        failed = failure_report("assembly", error).model_dump(mode="json")
        return failed, None, None, None, None
    report = validation_report(assembly).model_dump(mode="json")
    return (
        report,
        holes(assembly),
        steps_report(assembly),
        parts_report(assembly),
        chains_report(assembly),
    )


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


CLI_DIR = ROOT / "crates" / "nichiyou-daiku-cli" / "tests" / "cli"
# The report's golden files are the Rust CLI's own since countersinks
# (2026-11-02): ND_BLESS=1 cargo test -p nichiyou-daiku-cli writes them
CLI_GENERATED = (
    "*.cli-validate.txt",
    "*.cli-validate-json.txt",
    "*.steps.md",
    "*.render.json",
)
RENDERED = ("example-", "doc-")
"""Cases whose check image's labels and note are recorded: drawing them in
Python takes build123d's hidden lines, too slow for every case."""
GENERATED_ON = re.compile(r"^\*Generated on \d{4}-\d{2}-\d{2} \d{2}:\d{2}\*$", re.M)

# A design with a problem (an unconnected piece) and one with a piece longer
# than every stock board
UNCONNECTED = "(a:2x4 =400)\n(b:2x4 =400)\n"
OVERSIZE = "(a:2x4 =4000)\n(b:2x4 =400)\na -[TF<0 BD<0]- b\n"
TABLE = "examples/nd_files/simple_table_compact.nd"

STOCK_FILES: dict[str, str | bytes] = {
    "ok.toml": 'kerf = 2\n\n[lengths]\n"2x4" = [1820, 2440]\n"1x4" = [910.5]\n',
    "bad-toml.toml": "kerf = = 3\n",
    "not-utf8.toml": b"kerf = 3 # \xff\n",
    "unknown-key.toml": "kerf = 3\nwidth = 5\n",
    "kerf-text.toml": 'kerf = "3mm"\n',
    "kerf-negative.toml": "kerf = -1\n",
    "lengths-not-table.toml": "lengths = 5\n",
    "kerf-in-lengths.toml": '[lengths]\n"2x4" = [1820]\nkerf = 2\n',
    "unknown-type.toml": '[lengths]\n"2x3" = [1820]\n',
    "not-list.toml": '[lengths]\n"2x4" = 1820\n',
    "empty-list.toml": '[lengths]\n"2x4" = []\n',
    "bad-lengths.toml": '[lengths]\n"2x4" = [1820, "a", true, -5]\n',
}

OPTION_CASES: list[tuple[str, list[str], str | None, str | None]] = [
    # name, args, file, text
    ("report-no-cut-diagram", ["report", "--no-cut-diagram", "-"], TABLE, None),
    ("report-no-anchor-details", ["report", "--no-anchor-details", "-"], TABLE, None),
    ("report-no-pilot-holes", ["report", "--no-pilot-holes", "-"], TABLE, None),
    (
        "report-last-flag-wins",
        ["report", "--no-cut-diagram", "--include-cut-diagram", "-"],
        TABLE,
        None,
    ),
    (
        "report-project-name",
        ["report", "--project-name", "Side table", "-"],
        TABLE,
        None,
    ),
    ("report-stock", ["report", "--stock", "stock/ok.toml", "-"], TABLE, None),
    ("report-oversize", ["report", "-"], None, OVERSIZE),
    ("report-warnings", ["report", "-"], None, UNCONNECTED),
    ("report-quiet", ["-q", "report", "-"], None, UNCONNECTED),
    ("report-verbose", ["-v", "report", "-"], None, UNCONNECTED),
    ("report-missing-file", ["report", "missing.nd"], None, None),
    (
        "report-stock-missing",
        ["report", "--stock", "stock/missing.toml", "-"],
        TABLE,
        None,
    ),
    *(
        (
            f"report-stock-{name.removesuffix('.toml')}",
            ["report", "--stock", f"stock/{name}", "-"],
            TABLE,
            None,
        )
        for name in STOCK_FILES
        if name != "ok.toml"
    ),
    ("validate-verbose", ["-v", "validate", "-"], TABLE, None),
    # click keeps the last of a repeated option; agents add theirs to defaults
    ("validate-verbose-twice", ["-v", "-v", "validate", "-"], TABLE, None),
    (
        "report-flag-twice",
        ["report", "--no-cut-diagram", "--no-cut-diagram", "-"],
        TABLE,
        None,
    ),
    (
        "report-project-name-twice",
        ["report", "--project-name", "A", "--project-name", "B", "-"],
        TABLE,
        None,
    ),
    ("validate-quiet", ["-q", "validate", "-"], None, UNCONNECTED),
    ("validate-missing-file", ["validate", "missing.nd"], None, None),
    ("validate-json-missing-file", ["validate", "--json", "missing.nd"], None, None),
]


def run_cli(args: list[str], source: str | None = None) -> str:
    """What the CLI prints, as the Rust CLI's tests read it: the exit code,
    then stdout and stderr, colourless, with the report's date fixed."""
    result = CliRunner().invoke(cli, args, input=source)
    if result.exception is not None and not isinstance(result.exception, SystemExit):
        raise result.exception
    text = f"exit: {result.exit_code}\n--- stdout\n{result.stdout}--- stderr\n{result.stderr}"
    return GENERATED_ON.sub("*Generated on DATE*", text)


def render_facts(assembly: Assembly) -> dict:
    """What the check image says (shell/render.py), drawn with square edges
    as the Rust version draws them."""
    from nichiyou_daiku.shell.build123d_export import assembly_to_build123d
    from nichiyou_daiku.shell.render import render_sheet

    part = assembly_to_build123d(assembly, fillet_radius=0)
    sheet = render_sheet(part, assembly, title="case.nd")
    labels: dict[str, list[str]] = {}
    for label in sheet.labels:
        labels.setdefault(label.caption, []).append(label.piece_id)
    return {
        "labels": labels,
        "unlabelled": list(sheet.unlabelled),
        "note": list(sheet.note),
    }


def write_cli_goldens() -> None:
    for pattern in CLI_GENERATED:
        for old in CORPUS.glob(pattern):
            old.unlink()
    for path in sorted(CORPUS.glob("*.nd")):
        source = path.read_text(encoding="utf-8")
        name = path.name.removesuffix(".nd")
        (CORPUS / f"{name}.cli-validate.txt").write_text(
            run_cli(["validate", "-"], source), encoding="utf-8"
        )
        if name.startswith("example-"):
            (CORPUS / f"{name}.cli-validate-json.txt").write_text(
                run_cli(["validate", "--json", "-"], source), encoding="utf-8"
            )
        try:
            assembly = Assembly.of(parse_dsl(source))
        except Exception:
            continue  # Nothing to draw or plan
        (CORPUS / f"{name}.steps.md").write_text(
            steps_markdown(assembly, plan_steps(assembly), "case"), encoding="utf-8"
        )
        if name.startswith(RENDERED):
            write(CORPUS / f"{name}.render.json", render_facts(assembly))
    stock = CLI_DIR / "stock"
    stock.mkdir(parents=True, exist_ok=True)
    for old in CLI_DIR.glob("*.txt"):
        if not old.name.startswith("report-"):
            old.unlink()
    for name, content in STOCK_FILES.items():
        if isinstance(content, bytes):
            (stock / name).write_bytes(content)
        else:
            (stock / name).write_text(content, encoding="utf-8")
    cases = []
    with contextlib.chdir(CLI_DIR):
        for name, args, file, text in OPTION_CASES:
            cases.append({"name": name, "args": args, "file": file, "text": text})
            if "report" in args:
                continue  # The Rust CLI's own; see CLI_GENERATED
            source = (ROOT / file).read_text(encoding="utf-8") if file else text
            (CLI_DIR / f"{name}.txt").write_text(
                run_cli(args, source), encoding="utf-8"
            )
    (CLI_DIR / "cases.json").write_text(
        json.dumps(cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"cli goldens {len(list(CORPUS.glob('*.cli-validate.txt')))} cases, {len(cases)} option cases"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--captured", type=Path, help="JSON lines from tools/capture_dsl.py"
    )
    parser.add_argument(
        "--steps-only",
        action="store_true",
        help="write NAME.steps.json, NAME.parts.json and NAME.chains.json for the .nd files already in the corpus",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="write what the CLI prints (validate, report) for the corpus and the option cases",
    )
    args = parser.parse_args()
    if args.cli:
        write_cli_goldens()
        return
    if args.steps_only:
        for pattern in ("*.steps.json", "*.parts.json", "*.chains.json"):
            for old in CORPUS.glob(pattern):
                old.unlink()
        written = 0
        for path in sorted(CORPUS.glob("*.nd")):
            try:
                assembly = Assembly.of(parse_dsl(path.read_text(encoding="utf-8")))
            except Exception:
                continue  # No holes.json either: it does not assemble
            write(path.with_suffix(".steps.json"), steps_report(assembly))
            write(path.with_suffix(".parts.json"), parts_report(assembly))
            write(path.with_suffix(".chains.json"), chains_report(assembly))
            written += 1
        print(f"steps.json, parts.json and chains.json {written}")
        return
    CORPUS.mkdir(parents=True, exist_ok=True)
    for pattern in GENERATED:
        for old in CORPUS.glob(pattern):
            old.unlink()
    seen: set[str] = set()
    counts: Counter[str] = Counter()
    for origin, source in sources(args.captured):
        digest = hashlib.sha1(source.encode("utf-8")).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        name = f"{origin}-{digest[:10]}"
        (CORPUS / f"{name}.nd").write_text(source, encoding="utf-8")
        report, hole_list, steps, parts, chain_list = reports(source)
        write(CORPUS / f"{name}.validate.json", report)
        if hole_list is not None:
            write(CORPUS / f"{name}.holes.json", hole_list)
        if steps is not None:
            write(CORPUS / f"{name}.steps.json", steps)
        if parts is not None:
            write(CORPUS / f"{name}.parts.json", parts)
        if chain_list is not None:
            write(CORPUS / f"{name}.chains.json", chain_list)
        error = report["error"] or {}
        kind = error.get("kind") or ("problems" if report["problems"] else "valid")
        counts[f"{origin}/{kind}"] += 1
    for key, count in sorted(counts.items()):
        print(f"{key:24} {count}")
    print(f"{'total':24} {len(seen)}")


if __name__ == "__main__":
    main()
