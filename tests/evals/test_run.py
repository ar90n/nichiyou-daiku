"""Tests for running the cases, recording them and writing the report."""

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

import evals.design.agent as agent_module
import evals.design.run as run
from evals.design.agent import AgentFailed, Transcript
from evals.design.checks import CHECKS, Check
from evals.design.judge import CRITERIA, Judgement
from evals.design.report import load_jsonl, rates, report_markdown, wilson

EXAMPLE = Path(__file__).parents[2] / "skills" / "design" / "examples" / "side-table.nd"
TRANSCRIPT = Transcript(
    model="claude-sonnet-5",
    skill_used=True,
    validates=2,
    renders=1,
    images_read=1,
    denials=0,
    turns=10,
    duration_s=300.0,
    cost_usd=0.5,
    usage={},
    shared_tmp=0,
)


def in_git_checkout(path: Path) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(path), "rev-parse"], capture_output=True
        ).returncode
        == 0
    )


@pytest.fixture
def seen():
    """What the agent found where it ran."""
    return []


@pytest.fixture
def fake(monkeypatch, seen):
    """The agent writes the side table example for every case; the bench
    times out once. The judge passes everything."""
    calls = []
    judged = []
    tries: dict[str, int] = {}

    def agent(request, model, plugin, repo, workdir, timeout_s):
        calls.append(workdir.name)
        seen.append(
            {
                "model": model,
                "in_git_checkout": in_git_checkout(workdir),
                "plugin_is_repo": plugin == repo,
                "skill": (plugin / "skills" / "design" / "SKILL.md").is_file(),
                "launcher": os.access(plugin / "bin" / "nichiyou-daiku", os.X_OK),
                "hidden": [
                    name
                    for name in ("evals", ".claude", "CLAUDE.md")
                    if (plugin / name).exists()
                ],
            }
        )
        tries[workdir.name] = tries.get(workdir.name, 0) + 1
        if workdir.name == "bench-1" and tries["bench-1"] == 1:
            raise AgentFailed("timeout", "no result within 40 minutes")
        if workdir.name == "desk-1":
            raise AgentFailed("agent_error", "usage limit reached", cost_usd=0.3)
        if workdir.name == "step-stool-1":
            # Ctrl-C while claude works
            os.kill(os.getpid(), signal.SIGINT)
            command = [sys.executable, "-c", "import time; time.sleep(30)"]
            agent_module.run_claude(
                command, workdir, dict(os.environ), workdir / "out", 60
            )
        if workdir.name == "shoe-rack-1":
            (workdir / "shoe-rack.nd").write_text("not a design")
        else:
            shutil.copy(EXAMPLE, workdir / "design.nd")
        return TRANSCRIPT

    def judge(design, request, model, repo, workdir, timeout_s):
        judged.append(workdir.name)
        if workdir.name == "two-tier-shelf-1" and judged.count("two-tier-shelf-1") == 1:
            raise AgentFailed("judge", "no structured answer", cost_usd=0.02)
        checks = {name: Check(True, "looks right") for name in CRITERIA}
        return Judgement(checks=checks, model="claude-opus-5", cost_usd=0.05, usage={})

    monkeypatch.setattr(run, "run_agent", agent)
    monkeypatch.setattr(run, "judge", judge)
    monkeypatch.setattr(run, "_commit", lambda: "abc123")
    return calls


def test_a_run_records_each_graded_design_and_each_failed_attempt(fake, tmp_path):
    assert (
        run.main(["--cases", "side-table,bench", "--reps", "1", "--out", str(tmp_path)])
        == 0
    )
    rows = load_jsonl(tmp_path / "results.jsonl")
    errors = load_jsonl(tmp_path / "errors.jsonl")
    assert [(row["case"], row["rep"]) for row in rows] == [("side-table", 1)]
    assert rows[0]["checks"]["size"]["passed"] is True
    assert rows[0]["judge"]["furniture"]["passed"] is True
    assert errors == [
        {
            "case": "bench",
            "rep": 1,
            "kind": "timeout",
            "message": "no result within 40 minutes",
            "cost_usd": None,
        }
    ]


def test_a_run_that_claude_ends_in_error_is_a_failed_attempt(fake, tmp_path):
    # Not a failed design: --resume runs it again
    run.main(["--cases", "desk", "--out", str(tmp_path)])
    assert load_jsonl(tmp_path / "results.jsonl") == []
    assert load_jsonl(tmp_path / "errors.jsonl") == [
        {
            "case": "desk",
            "rep": 1,
            "kind": "agent_error",
            "message": "usage limit reached",
            "cost_usd": 0.3,
        }
    ]


def test_the_agent_works_outside_the_repository_on_a_copy_of_the_plugin(
    fake, seen, tmp_path
):
    # Inside a git checkout Claude Code takes the checkout as the project and
    # loads its CLAUDE.md, settings and memory; the plugin root would show
    # the requirements and earlier runs
    checkout = tmp_path / "checkout"
    subprocess.run(["git", "init", "-q", str(checkout)], check=True)
    out = checkout / "runs"
    run.main(["--cases", "side-table", "--out", str(out)])
    assert seen == [
        {
            "model": "sonnet",
            "in_git_checkout": False,
            "plugin_is_repo": False,
            "skill": True,
            "launcher": True,
            "hidden": [],
        }
    ]
    # What the agent wrote ends up in the run directory
    assert (out / "side-table-1" / "design.nd").is_file()


def test_the_self_check_judges_outside_the_repository(monkeypatch, tmp_path):
    places = []

    def self_check(request, model, repo, workdir, timeout_s):
        workdir.mkdir(parents=True, exist_ok=True)
        places.append(in_git_checkout(workdir))
        (workdir / "judge.json").write_text("{}")
        return []

    monkeypatch.setattr(run, "self_check", self_check)
    checkout = tmp_path / "checkout"
    subprocess.run(["git", "init", "-q", str(checkout)], check=True)
    assert run.main(["--self-check", "--out", str(checkout / "check")]) == 0
    assert places == [False]
    assert (checkout / "check" / "judge.json").is_file()


def test_resuming_runs_only_what_was_not_graded(fake, tmp_path):
    run.main(["--cases", "side-table,bench", "--out", str(tmp_path)])
    fake.clear()
    run.main(["--resume", str(tmp_path)])
    assert fake == ["bench-1"]
    assert len(load_jsonl(tmp_path / "results.jsonl")) == 2
    # The first attempt stays on record, marked as graded later
    report = (tmp_path / "report.md").read_text()
    assert (
        "- bench-1: timeout: no result within 40 minutes (graded on a later attempt)"
        in report
    )
    assert "failed attempts: 1 (0 not graded yet)" in report


def test_resuming_keeps_the_run_s_own_cases_and_models(fake, seen, tmp_path):
    run.main(
        ["--cases", "side-table,bench", "--reps", "2", "--model", "opus"]
        + ["--out", str(tmp_path)]
    )
    fake.clear()
    seen.clear()
    run.main(["--resume", str(tmp_path)])
    assert fake == ["bench-1"]
    assert [s["model"] for s in seen] == ["opus"]


def test_resuming_with_other_cases_or_models_is_refused(fake, tmp_path, capsys):
    run.main(["--cases", "side-table", "--out", str(tmp_path)])
    fake.clear()
    assert run.main(["--resume", str(tmp_path), "--model", "opus"]) == 2
    assert "leave out --cases, --reps, --model" in capsys.readouterr().err
    assert fake == []


def test_runs_not_graded_yet_are_counted_from_the_conditions():
    # A stopped run leaves cases that never started, with no failed attempt
    meta = {"cases": ["bench", "desk"], "reps": 2}
    row = {
        "case": "bench",
        "rep": 1,
        "design": None,
        "checks": {name: {"passed": False, "detail": ""} for name in CHECKS},
        "judge": None,
        "judge_cost_usd": 0.0,
        **TRANSCRIPT.model_dump(),
    }
    assert "failed attempts: 0 (3 not graded yet)" in report_markdown(meta, [row], [])


def test_the_same_request_s_runs_do_not_run_together(fake, tmp_path):
    # They would write the same scratch files in /tmp
    run.main(
        ["--cases", "side-table,tv-stand", "--reps", "2", "--jobs", "1"]
        + ["--out", str(tmp_path)]
    )
    assert fake == ["side-table-1", "tv-stand-1", "side-table-2", "tv-stand-2"]
    report = (tmp_path / "report.md").read_text()
    assert "- Runs that used /tmp outside their own directory: 0 of 4" in report


def test_the_report_rates_come_from_the_rows(fake, tmp_path):
    run.main(["--cases", "side-table,bench", "--out", str(tmp_path)])
    report = (tmp_path / "report.md").read_text()
    counts = rates(load_jsonl(tmp_path / "results.jsonl"))
    # The timed-out bench is a failed attempt, not a failed design
    assert counts["all checks"] == (1, 1)
    assert "| all checks | 1/1 | 100% |" in report
    assert "- bench-1: timeout: no result within 40 minutes" in report
    assert "![side-table-1](side-table-1/judge/render.png)" in report


def test_the_report_counts_the_usage_of_failed_attempts(fake, tmp_path):
    # A 40-minute timeout uses allowance too; the spend must not hide it
    run.main(["--cases", "side-table,bench,desk", "--out", str(tmp_path)])
    report = (tmp_path / "report.md").read_text()
    assert (
        "- Failed attempts: 2, 0.30 USD and 1 without a usage record (timed out or stopped)"
        in report
    )
    # The graded side table's agent and judge, and the failed desk
    assert "- Total usage: 0.85 USD" in report


def test_a_failed_judge_is_retried_on_resume_without_the_agent(fake, tmp_path):
    run.main(["--cases", "two-tier-shelf", "--out", str(tmp_path)])
    # The machine checks are done; the design waits for its judge
    assert load_jsonl(tmp_path / "results.jsonl") == []
    assert [e["kind"] for e in load_jsonl(tmp_path / "errors.jsonl")] == ["judge"]
    fake.clear()
    run.main(["--resume", str(tmp_path)])
    assert fake == []
    [row] = load_jsonl(tmp_path / "results.jsonl")
    assert row["judge"]["furniture"]["passed"] is True
    assert row["checks"]["valid"]["passed"] is True
    assert row["cost_usd"] == 0.5
    report = (tmp_path / "report.md").read_text()
    assert "no structured answer (graded on a later attempt)" in report


def test_a_design_that_does_not_assemble_is_not_judged(fake, tmp_path):
    # Its picture cannot be drawn; that is the design's failure, not the judge's
    run.main(["--cases", "shoe-rack", "--out", str(tmp_path)])
    [row] = load_jsonl(tmp_path / "results.jsonl")
    assert row["checks"]["valid"]["passed"] is False
    assert row["judge"] is None
    assert load_jsonl(tmp_path / "errors.jsonl") == []


def test_ctrl_c_ends_the_sessions_and_starts_no_more(fake, tmp_path, capsys):
    started = time.monotonic()
    code = run.main(
        ["--cases", "step-stool,tv-stand,workbench", "--jobs", "1"]
        + ["--out", str(tmp_path)]
    )
    assert code == 130
    assert time.monotonic() - started < 10
    assert fake == ["step-stool-1"]
    assert [e["kind"] for e in load_jsonl(tmp_path / "errors.jsonl")] == ["stopped"]
    assert "(3 not graded yet)" in (tmp_path / "report.md").read_text()
    assert "--resume" in capsys.readouterr().err
    # The next run starts again
    agent_module.STOP.clear()


def test_an_earlier_run_is_compared(fake, tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    run.main(["--cases", "side-table", "--out", str(first)])
    run.main(["--cases", "side-table", "--out", str(second), "--compare", str(first)])
    assert (
        "| all checks | 1/1 | 100% | 21–100% | 100% |"
        in (second / "report.md").read_text()
    )


def test_an_unknown_case_stops_before_anything_runs(fake, tmp_path, capsys):
    assert run.main(["--cases", "nope", "--out", str(tmp_path)]) == 2
    assert "Unknown case nope" in capsys.readouterr().err
    assert fake == []


def test_the_interval_of_a_pass_rate():
    assert wilson(0, 0) == (0.0, 1.0)
    low, high = wilson(5, 5)
    assert high == 1.0 and 0.5 < low < 0.6
