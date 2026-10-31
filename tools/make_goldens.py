"""Collect .nd sources and write the Rust core's golden files with the Python version.

    rm -f /tmp/nd-captured.jsonl
    ND_CAPTURE=/tmp/nd-captured.jsonl PYTHONPATH=. .venv/bin/python -m pytest \\
        -p tools.capture_dsl tests/ -q
    .venv/bin/python tools/make_goldens.py --captured /tmp/nd-captured.jsonl

Each source becomes NAME.nd, NAME.validate.json (what `validate --json` prints),
NAME.holes.json (every piece's holes and each connection's fasteners) and
NAME.steps.json (the parts, the assembly steps with their fasteners and
dimensions); the last two only when the source assembles. `--steps-only` adds
NAME.steps.json to the corpus that is there.
"""

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nichiyou_daiku.cli.commands.validate import _classify  # noqa: E402
from nichiyou_daiku.core.assembly import Assembly  # noqa: E402
from nichiyou_daiku.core.assembly.parts import part_groups  # noqa: E402
from nichiyou_daiku.core.assembly.steps import plan_steps  # noqa: E402
from nichiyou_daiku.core.placement import overall_bounds  # noqa: E402
from nichiyou_daiku.core.geometry import Point3D  # noqa: E402
from nichiyou_daiku.core.placement import round_mm  # noqa: E402
from nichiyou_daiku.dsl import parse_dsl  # noqa: E402
from nichiyou_daiku.shell.diagnostics import (  # noqa: E402
    failure_report,
    validation_report,
)
from nichiyou_daiku.shell.dimensioning import chain_for  # noqa: E402
from nichiyou_daiku.shell.instructions import grouping_hint  # noqa: E402
from nichiyou_daiku.shell.resources import count_hardware  # noqa: E402
from nichiyou_daiku.shell.views import axis_view, project  # noqa: E402
from tests.test_docs import ND_BLOCKS, ND_FILES  # noqa: E402

CORPUS = ROOT / "crates" / "nichiyou-daiku-core" / "tests" / "corpus"
GENERATED = ("*.nd", "*.validate.json", "*.holes.json", "*.steps.json")


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


def reports(source: str) -> tuple[dict, dict | None, dict | None]:
    try:
        model = parse_dsl(source)
    except Exception as error:
        report = failure_report(_classify(error)[0], error)
        return report.model_dump(mode="json"), None, None
    try:
        assembly = Assembly.of(model)
    except Exception as error:
        return failure_report("assembly", error).model_dump(mode="json"), None, None
    report = validation_report(assembly).model_dump(mode="json")
    return report, holes(assembly), steps_report(assembly)


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--captured", type=Path, help="JSON lines from tools/capture_dsl.py"
    )
    parser.add_argument(
        "--steps-only",
        action="store_true",
        help="write NAME.steps.json for the .nd files already in the corpus",
    )
    args = parser.parse_args()
    if args.steps_only:
        for old in CORPUS.glob("*.steps.json"):
            old.unlink()
        written = 0
        for path in sorted(CORPUS.glob("*.nd")):
            try:
                assembly = Assembly.of(parse_dsl(path.read_text(encoding="utf-8")))
            except Exception:
                continue  # No holes.json either: it does not assemble
            write(path.with_suffix(".steps.json"), steps_report(assembly))
            written += 1
        print(f"steps.json {written}")
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
        report, hole_list, steps = reports(source)
        write(CORPUS / f"{name}.validate.json", report)
        if hole_list is not None:
            write(CORPUS / f"{name}.holes.json", hole_list)
        if steps is not None:
            write(CORPUS / f"{name}.steps.json", steps)
        error = report["error"] or {}
        kind = error.get("kind") or ("problems" if report["problems"] else "valid")
        counts[f"{origin}/{kind}"] += 1
    for key, count in sorted(counts.items()):
        print(f"{key:24} {count}")
    print(f"{'total':24} {len(seen)}")


if __name__ == "__main__":
    main()
