"""Run the design skill on the cases and grade each design.

uv run python -m evals.design.run --cases core --reps 1
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .agent import AgentFailed, run_agent
from .cases import Case, load_cases
from .checks import check_design, find_design
from .judge import judge, self_check
from .report import load_jsonl, report_markdown

REPO = Path(__file__).resolve().parents[2]
RUNS = Path(__file__).parent / "runs"
# Left out of the plugin the agent loads: the requirements and earlier runs,
# and the developer's Claude Code setup
HIDDEN = ("evals/", ".claude/", "CLAUDE.md")


def plugin_copy(repo: Path, into: Path) -> Path:
    """The plugin as a person installs it, with today's changes: the files
    git tracks or would track, without HIDDEN."""
    names = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z", "--cached", "--others"]
        + ["--exclude-standard"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\0")
    for name in names:
        source = repo / name
        if not name or name.startswith(HIDDEN) or not source.is_file():
            continue
        target = into / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return into


@contextmanager
def outside_repo(keep: Path) -> Iterator[Path]:
    """A working directory outside any git checkout whose files end up in
    ``keep``: inside this repository Claude Code would take it as the project
    and load the developer's CLAUDE.md, settings and memory."""
    with tempfile.TemporaryDirectory(prefix="ndk-eval-") as tmp:
        workdir = Path(tmp) / keep.name
        workdir.mkdir()
        try:
            yield workdir
        finally:
            shutil.copytree(workdir, keep, symlinks=True, dirs_exist_ok=True)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m evals.design.run", description=__doc__
    )
    parser.add_argument(
        "--cases", default="core", help="all, core or names joined by commas"
    )
    parser.add_argument("--reps", type=int, default=1, help="runs of each case")
    parser.add_argument("--model", default="sonnet", help="model that designs")
    parser.add_argument(
        "--judge-model", default="opus", help="model that judges the pictures"
    )
    parser.add_argument("--jobs", type=int, default=2, help="runs at the same time")
    parser.add_argument(
        "--timeout-min", type=float, default=40, help="limit of one run"
    )
    parser.add_argument(
        "--out", type=Path, help="directory for this run (default: runs/<time>)"
    )
    parser.add_argument(
        "--resume", type=Path, help="continue a run, skipping graded cases"
    )
    parser.add_argument(
        "--compare", type=Path, help="an earlier run to compare pass rates with"
    )
    parser.add_argument(
        "--self-check", action="store_true", help="check the judge on known designs"
    )
    return parser.parse_args(argv)


class Record:
    """results.jsonl and errors.jsonl, written as each run finishes."""

    def __init__(self, directory: Path) -> None:
        self.results = directory / "results.jsonl"
        self.errors = directory / "errors.jsonl"
        self._lock = threading.Lock()

    def _append(self, path: Path, row: dict) -> None:
        with self._lock, path.open("a", encoding="utf-8") as out:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")

    def result(self, row: dict) -> None:
        self._append(self.results, row)

    def error(self, case: str, rep: int, kind: str, message: str) -> None:
        self._append(
            self.errors, {"case": case, "rep": rep, "kind": kind, "message": message}
        )

    def graded(self) -> set[tuple[str, int]]:
        return {(row["case"], row["rep"]) for row in load_jsonl(self.results)}


def run_one(
    case: Case,
    rep: int,
    args: argparse.Namespace,
    out: Path,
    record: Record,
    plugin: Path,
) -> None:
    """One design of ``case``: run the agent, then grade what it wrote. A
    run that gives no result goes to errors.jsonl so that --resume retries it."""
    keep = out / f"{case.name}-{rep}"
    # An earlier attempt's files would mix into this one's
    shutil.rmtree(keep, ignore_errors=True)
    timeout_s = args.timeout_min * 60
    with outside_repo(keep) as workdir:
        try:
            transcript = run_agent(
                case.request, args.model, plugin, REPO, workdir, timeout_s
            )
        except AgentFailed as e:
            record.error(case.name, rep, e.kind, str(e))
            return
        design = find_design(workdir, case.name)
        checks = check_design(design, case)
        judgement = None
        if design is not None:
            try:
                judgement = judge(
                    design, case.request, args.judge_model, REPO, workdir, timeout_s
                )
            except AgentFailed as e:
                record.error(case.name, rep, e.kind, str(e))
    record.result(
        {
            "case": case.name,
            "rep": rep,
            "design": design.name if design else None,
            "checks": {name: check._asdict() for name, check in checks.items()},
            "judge": {name: check._asdict() for name, check in judgement.checks.items()}
            if judgement
            else None,
            "judge_model": judgement.model if judgement else None,
            "judge_cost_usd": judgement.cost_usd if judgement else 0.0,
            "judge_usage": judgement.usage if judgement else {},
            **transcript.model_dump(),
        }
    )


def _commit() -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO), "describe", "--always", "--dirty"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or "unknown"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_check:
        request = next(case for case in load_cases("side-table")).request
        directory = args.out or RUNS / f"self-check-{datetime.now():%Y%m%d-%H%M%S}"
        with outside_repo(directory) as workdir:
            wrong = self_check(
                request, args.judge_model, REPO, workdir, args.timeout_min * 60
            )
        print(
            "\n".join(wrong)
            if wrong
            else "The judge passes the example and fails the broken designs"
        )
        return 1 if wrong else 0
    try:
        cases = load_cases(args.cases)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    out = args.resume or args.out or RUNS / f"{datetime.now():%Y%m%d-%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)
    meta_path = out / "meta.json"
    if not meta_path.exists():
        meta = {
            "started": f"{datetime.now():%Y-%m-%d %H:%M}",
            "commit": _commit(),
            "cases": [case.name for case in cases],
            "reps": args.reps,
            "model": args.model,
            "judge_model": args.judge_model,
        }
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    record = Record(out)
    graded = record.graded()
    todo = [
        (case, rep)
        for case in cases
        for rep in range(1, args.reps + 1)
        if (case.name, rep) not in graded
    ]
    with (
        tempfile.TemporaryDirectory(prefix="ndk-eval-plugin-") as tmp,
        ThreadPoolExecutor(max_workers=args.jobs) as pool,
    ):
        plugin = plugin_copy(REPO, Path(tmp))
        for future in [
            pool.submit(run_one, case, rep, args, out, record, plugin)
            for case, rep in todo
        ]:
            future.result()
    previous = load_jsonl(args.compare / "results.jsonl") if args.compare else None
    rows, errors = load_jsonl(record.results), load_jsonl(record.errors)
    (out / "report.md").write_text(
        report_markdown(meta, rows, errors, previous), encoding="utf-8"
    )
    print(
        f"Graded {len(rows)} runs, {len(errors)} failed attempts: {out / 'report.md'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
