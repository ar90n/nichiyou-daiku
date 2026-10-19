"""Run the design skill on the cases and grade each design.

uv run python -m evals.design.run --cases core --reps 1
"""

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, wait
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .agent import (
    CLAUDE_MODELS,
    STOP,
    AgentFailed,
    agent_env,
    is_claude,
    run_agent,
    stop_all,
)
from .cases import Case, load_cases
from .checks import assembles, check_design, find_design
from .judge import judge, self_check
from .opencode import MODELS, model_id, opencode_env, run_opencode, uses_opencode
from .report import load_jsonl, report_markdown

REPO = Path(__file__).resolve().parents[2]
RUNS = Path(__file__).parent / "runs"
# The plugin CLI's environments, one per evaluation: on uv's file system,
# so that uv links the packages instead of copying them
ENVIRONMENTS = (
    Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    / "nichiyou-daiku-eval"
)
# The row of a design the machine graded and the judge could not: --resume
# judges it again instead of running the agent again
UNJUDGED = "unjudged.json"
# What a run measures, kept in its meta.json; --resume takes them from there
CONDITIONS = {"cases": "core", "reps": 1, "model": "sonnet", "judge_model": "opus"}
# Left out of the plugin the agent loads: the requirements (the cases, the
# spec's table, the tests) and earlier runs, and the developer's Claude Code
# setup
HIDDEN = ("evals/", "docs/superpowers/", "tests/evals/", ".claude/", "CLAUDE.md")


# Never part of the plugin when the repository is copied without git
_NOT_SOURCE = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}


def _source_files(repo: Path) -> list[str]:
    """The files git tracks or would track; in a copy without git (as CI
    tests it), every file outside caches and environments."""
    if (repo / ".git").exists():
        return subprocess.run(
            ["git", "-C", str(repo), "ls-files", "-z", "--cached", "--others"]
            + ["--exclude-standard"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split("\0")
    names = []
    for directory, subdirectories, files in os.walk(repo):
        subdirectories[:] = [d for d in subdirectories if d not in _NOT_SOURCE]
        names += [str((Path(directory) / f).relative_to(repo)) for f in files]
    return names


def plugin_copy(repo: Path, into: Path) -> Path:
    """The plugin as a person installs it, with today's changes: the
    repository's source files without HIDDEN."""
    for name in _source_files(repo):
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
        "--cases",
        help="all, core, heldout or names joined by commas (default: core)",
    )
    parser.add_argument("--reps", type=int, help="runs of each case (default: 1)")
    parser.add_argument("--model", help="model that designs (default: sonnet)")
    parser.add_argument(
        "--judge-model", help="model that judges the pictures (default: opus)"
    )
    parser.add_argument("--jobs", type=int, default=2, help="runs at the same time")
    parser.add_argument(
        "--timeout-min", type=float, default=40, help="limit of one run"
    )
    parser.add_argument(
        "--out", type=Path, help="directory for this run (default: runs/<time>)"
    )
    parser.add_argument(
        "--resume",
        type=Path,
        help="continue a run with its own cases and models, skipping graded ones",
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

    def error(self, case: str, rep: int, failed: AgentFailed) -> None:
        self._append(
            self.errors,
            {
                "case": case,
                "rep": rep,
                "kind": failed.kind,
                "message": str(failed),
                "cost_usd": failed.cost_usd,
            },
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
    env: dict[str, str],
) -> None:
    """One design of ``case``: run the agent, then grade what it wrote. A
    run that gives no result goes to errors.jsonl so that --resume retries
    it; so does a failed judge, which --resume retries alone."""
    if STOP.is_set():
        return
    keep = out / f"{case.name}-{rep}"
    unjudged = keep / UNJUDGED
    row = (
        json.loads(unjudged.read_text(encoding="utf-8")) if unjudged.exists() else None
    )
    if row is None and keep.exists():
        # An earlier attempt's files would mix into this one's; keep them
        # apart for a look at why it failed
        attempt = 1
        while keep.with_name(f"{keep.name}.attempt-{attempt}").exists():
            attempt += 1
        keep.rename(keep.with_name(f"{keep.name}.attempt-{attempt}"))
    timeout_s = args.timeout_min * 60
    with outside_repo(keep) as workdir:
        if row is None:
            try:
                design_with = run_opencode if uses_opencode(args.model) else run_agent
                transcript = design_with(
                    case.request, args.model, plugin, env, workdir, timeout_s
                )
            except AgentFailed as e:
                record.error(case.name, rep, e)
                return
            design = find_design(workdir, case.name, transcript.last_checked)
            checks = check_design(design, case)
            row = {
                "case": case.name,
                "rep": rep,
                "design": design.name if design else None,
                "designs": len(list(workdir.glob("*.nd"))),
                "checks": {name: check._asdict() for name, check in checks.items()},
                "judge": None,
                "judge_model": None,
                "judge_cost_usd": 0.0,
                "judge_usage": {},
                **transcript.model_dump(),
            }
            # A design that does not assemble cannot be drawn; the machine
            # checks have failed it already
            if design is None or not assembles(design):
                record.result(row)
                return
        else:
            design = workdir / row["design"]
            shutil.copy2(keep / row["design"], design)
        try:
            judgement = judge(
                design, case.request, args.judge_model, plugin, env, workdir, timeout_s
            )
        except AgentFailed as e:
            record.error(case.name, rep, e)
            (workdir / UNJUDGED).write_text(json.dumps(row), encoding="utf-8")
            return
        row |= {
            "judge": {
                name: check._asdict() for name, check in judgement.checks.items()
            },
            "judge_model": judgement.model,
            "judge_cost_usd": judgement.cost_usd,
            "judge_usage": judgement.usage,
        }
    unjudged.unlink(missing_ok=True)
    record.result(row)


def _run_safely(
    case: Case,
    rep: int,
    args: argparse.Namespace,
    out: Path,
    record: Record,
    plugin: Path,
    env: dict[str, str],
) -> None:
    """``run_one``, with a bug of the evaluation itself recorded as a failed
    attempt: the other runs go on and the report is written."""
    try:
        run_one(case, rep, args, out, record, plugin, env)
    except Exception as e:
        record.error(case.name, rep, AgentFailed("harness", f"{type(e).__name__}: {e}"))


def _diff() -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), "diff", "HEAD"], capture_output=True, text=True
    ).stdout


def _commit() -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO), "describe", "--always", "--dirty"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or "unknown"


def _stop(signum: int, frame: object) -> None:
    print(
        "Stopping: ending the running sessions and starting no more",
        file=sys.stderr,
    )
    stop_all()


def _conditions(args: argparse.Namespace) -> str | None:
    """Fill the run's conditions in ``args``: from the run itself on
    --resume, else the defaults. Return what is wrong, if anything."""
    if args.resume is None:
        for name, default in CONDITIONS.items():
            if getattr(args, name) is None:
                setattr(args, name, default)
    else:
        meta_path = args.resume / "meta.json"
        if not meta_path.exists():
            return f"{args.resume} has no meta.json; give --resume a directory an earlier run wrote"
        if any(getattr(args, name) is not None for name in CONDITIONS):
            return (
                f"--resume continues {args.resume} with its own cases, repetitions and "
                "models; leave out --cases, --reps, --model and --judge-model"
            )
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        args.cases = ",".join(meta["cases"])
        for name in ("reps", "model", "judge_model"):
            setattr(args, name, meta[name])
    if not (is_claude(args.model) or uses_opencode(args.model)):
        return (
            f"Unknown model {args.model}; use {', '.join(CLAUDE_MODELS)} or a "
            f"claude-... name for Claude Code, or {', '.join(MODELS)} or an "
            "opencode/... or opencode-go/... name for opencode"
        )
    return None


def _uv_cache() -> str:
    if cache := os.environ.get("UV_CACHE_DIR"):
        return cache
    try:
        found = subprocess.run(["uv", "cache", "dir"], capture_output=True, text=True)
    except FileNotFoundError:
        return ""
    return found.stdout.strip()


def preflight(
    plugin: Path, env: dict[str, str], scratch: Path, model: str | None
) -> str | None:
    """What would make every run fail, found before any allowance is spent:
    claude (the judge's), the plugin's CLI validating and drawing the skill's
    example (which builds its environments once for all the runs), and for
    an opencode ``model``, opencode serving it."""
    if shutil.which("claude", path=env["PATH"]) is None:
        return "claude is not on PATH; install Claude Code to run the evaluation"
    example = plugin / "skills" / "design" / "examples" / "side-table.nd"
    cli = str(plugin / "bin" / "nichiyou-daiku")
    for command in (
        ["validate", str(example)],
        ["render", str(example), "-o", str(scratch / "preflight.png")],
    ):
        result = subprocess.run(
            [cli, *command], env=env, capture_output=True, text=True
        )
        if result.returncode != 0:
            said = (result.stderr.strip().splitlines() or ["no message"])[-1]
            return (
                f"the plugin's CLI could not {command[0]} the skill's example "
                f"({said}); check that bin/nichiyou-daiku runs with uv"
            )
    if model is None or not uses_opencode(model):
        return None
    if shutil.which("opencode", path=env["PATH"]) is None:
        return "opencode is not on PATH; install it (https://opencode.ai) to run this model"
    # This also fills opencode's cache, which the runs share: on an empty
    # one, opencode lists the catalog it ships with and fetches the current
    # one for the next call, and the first run starts before its skills are
    # found
    (scratch / "opencode" / "tmp").mkdir(parents=True, exist_ok=True)
    # In scratch, not the repository: opencode notes its directory as a project
    settings = {**opencode_env(env, scratch / "opencode"), "PWD": str(scratch)}
    listed = subprocess.run(
        ["opencode", "models"],
        cwd=scratch,
        env=settings,
        capture_output=True,
        text=True,
    )
    if model_id(model) not in listed.stdout.split():
        listed = subprocess.run(
            ["opencode", "models"],
            cwd=scratch,
            env=settings,
            capture_output=True,
            text=True,
        )
    if model_id(model) in listed.stdout.split():
        return None
    said = (listed.stderr.strip().splitlines() or [""])[-1]
    return (
        f"opencode does not offer {model_id(model)} now"
        + (f" ({said})" if said else "")
        + "; pick a model from opencode models"
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if wrong := _conditions(args):
        print(wrong, file=sys.stderr)
        return 2
    cases: list[Case] = []
    if not args.self_check:
        try:
            cases = load_cases(args.cases)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 2
    ENVIRONMENTS.mkdir(parents=True, exist_ok=True)
    with (
        tempfile.TemporaryDirectory(prefix="ndk-eval-plugin-") as tmp,
        tempfile.TemporaryDirectory(dir=ENVIRONMENTS) as cache,
    ):
        plugin = plugin_copy(REPO, Path(tmp) / "plugin")
        env = agent_env(plugin, Path(cache), _uv_cache(), REPO / ".venv")
        if wrong := preflight(
            plugin, env, Path(tmp), None if args.self_check else args.model
        ):
            print(wrong, file=sys.stderr)
            return 2
        if args.self_check:
            return _self_check(args, plugin, env)
        return _evaluate(args, cases, plugin, env)


def _self_check(args: argparse.Namespace, plugin: Path, env: dict[str, str]) -> int:
    request = next(case for case in load_cases("side-table")).request
    directory = args.out or RUNS / f"self-check-{datetime.now():%Y%m%d-%H%M%S}"
    with outside_repo(directory) as workdir:
        wrong = self_check(
            request, args.judge_model, REPO, plugin, env, workdir, args.timeout_min * 60
        )
    print(
        "\n".join(wrong)
        if wrong
        else "The judge passes the example and fails the broken designs"
    )
    return 1 if wrong else 0


def _evaluate(
    args: argparse.Namespace, cases: list[Case], plugin: Path, env: dict[str, str]
) -> int:
    # The model in the name: two started in the same second do not mix
    named = f"{datetime.now():%Y%m%d-%H%M%S}-{re.sub(r'[^\w.-]+', '-', args.model)}"
    out = args.resume or args.out or RUNS / named
    out.mkdir(parents=True, exist_ok=True)
    meta_path = out / "meta.json"
    if not meta_path.exists():
        commit = _commit()
        meta = {
            "started": f"{datetime.now():%Y-%m-%d %H:%M}",
            "commit": commit,
            "cases": [case.name for case in cases],
            "reps": args.reps,
            "model": args.model,
            "judge_model": args.judge_model,
        }
        if commit.endswith("-dirty"):
            # What was measured is the commit and these changes
            (out / "commit.diff").write_text(_diff(), encoding="utf-8")
            meta["diff"] = "commit.diff"
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    record = Record(out)
    graded = record.graded()
    # Rep by rep: the same request's runs would write the same scratch
    # files in the shared /tmp
    todo = [
        (case, rep)
        for rep in range(1, args.reps + 1)
        for case in cases
        if (case.name, rep) not in graded
    ]
    STOP.clear()
    handlers = {
        sig: signal.signal(sig, _stop) for sig in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futures = [
                pool.submit(_run_safely, case, rep, args, out, record, plugin, env)
                for case, rep in todo
            ]
            # Wake now and then: a signal handler runs only between waits
            while wait(futures, timeout=1).not_done:
                pass
            for future in futures:
                future.result()
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
    previous = None
    if args.compare:
        before = args.compare / "meta.json"
        previous = (
            json.loads(before.read_text(encoding="utf-8")) if before.exists() else {},
            load_jsonl(args.compare / "results.jsonl"),
        )
    rows, errors = load_jsonl(record.results), load_jsonl(record.errors)
    (out / "report.md").write_text(
        report_markdown(meta, rows, errors, previous), encoding="utf-8"
    )
    print(
        f"Graded {len(rows)} runs, {len(errors)} failed attempts: {out / 'report.md'}"
    )
    if STOP.is_set():
        print(f"Stopped; continue with --resume {out}", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
