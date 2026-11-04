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
    last_checked=None,
    tool="Claude Code 2.1.0",
    api_key_source="none",
    input_tokens=25_000,
    output_tokens=5_000,
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


def _no_opencode(*args):
    raise AssertionError("a test reached the real opencode: fake run_opencode")


@pytest.fixture
def fake(monkeypatch, seen, tmp_path_factory):
    """The agent writes the side table example for every case; the bench
    times out once. The judge passes everything."""
    calls = []
    judged = []
    tries: dict[str, int] = {}

    def agent(request, model, plugin, env, workdir, timeout_s):
        calls.append(workdir.name)
        seen.append(
            {
                "model": model,
                "in_git_checkout": in_git_checkout(workdir),
                "plugin_is_repo": plugin == run.REPO,
                "plugin_cli_first": env["PATH"].startswith(str(plugin / "bin")),
                "skill": (plugin / "skills" / "design" / "SKILL.md").is_file(),
                "launcher": os.access(plugin / "bin" / "nichiyou-daiku", os.X_OK),
                "hidden": [
                    name
                    for name in (
                        "evals",
                        ".claude",
                        "CLAUDE.md",
                        # The spec's requirement table and the tests' cases
                        "docs/superpowers",
                        "tests/evals",
                    )
                    if (plugin / name).exists()
                ],
            }
        )
        tries[workdir.name] = tries.get(workdir.name, 0) + 1
        if workdir.name == "bench-1" and tries["bench-1"] == 1:
            (workdir / "draft.nd").write_text("half a bench")
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
        elif workdir.name == "plant-stand-1":
            # A draft beside the design, which the agent checked last
            (workdir / "draft.nd").write_text("not a design")
            shutil.copy(EXAMPLE, workdir / "stand.nd")
            return TRANSCRIPT.model_copy(update={"last_checked": "stand.nd"})
        else:
            shutil.copy(EXAMPLE, workdir / "design.nd")
        return TRANSCRIPT

    def judge(design, request, model, plugin, env, workdir, timeout_s):
        judged.append(workdir.name)
        if workdir.name == "two-tier-shelf-1" and judged.count("two-tier-shelf-1") == 1:
            raise AgentFailed("judge", "no structured answer", cost_usd=0.02)
        checks = {name: Check(True, "looks right") for name in CRITERIA}
        return Judgement(checks=checks, model="claude-opus-5", cost_usd=0.05, usage={})

    monkeypatch.setattr(run, "ENVIRONMENTS", tmp_path_factory.mktemp("envs"))
    monkeypatch.setattr(run, "preflight", lambda plugin, env, scratch, model: None)
    monkeypatch.setattr(run, "run_agent", agent)
    # A test that reached the real opencode would spend a model's use
    monkeypatch.setattr(run, "run_opencode", _no_opencode)
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
            "plugin_cli_first": True,
            "skill": True,
            "launcher": True,
            "hidden": [],
        }
    ]
    # What the agent wrote ends up in the run directory
    assert (out / "side-table-1" / "design.nd").is_file()


def test_a_failed_preflight_spends_nothing(fake, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        run, "preflight", lambda plugin, env, scratch, model: "claude is not on PATH"
    )
    assert run.main(["--cases", "side-table", "--out", str(tmp_path / "out")]) == 2
    assert "claude is not on PATH" in capsys.readouterr().err
    assert fake == []


def test_the_evaluation_s_cli_is_only_for_its_run(fake, monkeypatch, tmp_path):
    # The checks run the CLI the evaluation built, which goes with its
    # temporary folder: later evaluations and tests must not reach for it
    before = os.environ["NICHIYOU_DAIKU_BIN"]
    built = tmp_path / "built"
    built.symlink_to(before)
    monkeypatch.setattr(run, "build_cli", lambda plugin, into: built)
    run.main(["--cases", "side-table", "--reps", "1", "--out", str(tmp_path / "out")])
    assert os.environ["NICHIYOU_DAIKU_BIN"] == before


def test_an_evaluation_without_cargo_stops_before_spending(
    fake, monkeypatch, tmp_path, capsys
):
    def no_cargo(plugin, into):
        raise FileNotFoundError("cargo")

    monkeypatch.setattr(run, "build_cli", no_cargo)
    assert run.main(["--cases", "side-table", "--out", str(tmp_path / "out")]) == 2
    said = capsys.readouterr().err
    assert "could not build the plugin's CLI with cargo" in said
    assert "https://rustup.rs" in said
    assert fake == []


def test_the_preflight_names_what_does_not_work(tmp_path):
    plugin = tmp_path / "plugin"
    (plugin / "bin").mkdir(parents=True)
    cli = plugin / "bin" / "nichiyou-daiku"
    cli.write_text('#!/bin/sh\necho "cannot read the design" >&2\nexit 1\n')
    cli.chmod(0o755)
    tools = tmp_path / "tools"
    tools.mkdir()
    env = {"PATH": f"{plugin / 'bin'}:{tools}"}
    assert "claude is not on PATH" in run.preflight(plugin, env, tmp_path, "sonnet")
    (tools / "claude").write_text("#!/bin/sh\n")
    (tools / "claude").chmod(0o755)
    wrong = run.preflight(plugin, env, tmp_path, "sonnet")
    assert "could not validate" in wrong and "cannot read the design" in wrong


def _tool(directory: Path, name: str, script: str) -> None:
    (directory / name).write_text("#!/bin/sh\n" + script)
    (directory / name).chmod(0o755)


def test_the_preflight_checks_opencode_and_its_model(tmp_path):
    plugin = tmp_path / "plugin"
    (plugin / "bin").mkdir(parents=True)
    _tool(plugin / "bin", "nichiyou-daiku", "exit 0\n")
    tools = tmp_path / "tools"
    tools.mkdir()
    _tool(tools, "claude", "")
    env = {"PATH": f"{plugin / 'bin'}:{tools}"}
    assert "opencode is not on PATH" in run.preflight(plugin, env, tmp_path, "deepseek")
    # opencode models lists what it serves now, from its own settings
    _tool(
        tools,
        "opencode",
        f'echo "$XDG_CONFIG_HOME" > "{tmp_path}/config_home"\n'
        f'pwd > "{tmp_path}/models_cwd"\n'
        "echo opencode-go/glm-5.3-flash\n",
    )
    wrong = run.preflight(plugin, env, tmp_path, "deepseek")
    assert "opencode does not offer opencode-go/deepseek-v4.1-flash" in wrong
    assert run.preflight(plugin, env, tmp_path, "glm") is None
    assert (tmp_path / "config_home").read_text().strip() == str(
        tmp_path / "opencode" / "config"
    )
    # Not in the repository, where opencode would note it as a project
    assert (tmp_path / "models_cwd").read_text().strip() == str(tmp_path)
    # A Claude model does not need opencode
    assert run.preflight(plugin, env, tmp_path, "sonnet") is None


def test_the_preflight_asks_opencode_again_once_its_cache_is_filled(tmp_path):
    # On an empty cache opencode lists the catalog it ships with, and fetches
    # the current one for the next call
    plugin = tmp_path / "plugin"
    (plugin / "bin").mkdir(parents=True)
    _tool(plugin / "bin", "nichiyou-daiku", "exit 0\n")
    tools = tmp_path / "tools"
    tools.mkdir()
    _tool(tools, "claude", "")
    _tool(
        tools,
        "opencode",
        f'if [ -e "{tmp_path}/filled" ]; then echo opencode-go/glm-5.3-flash; '
        f'else : > "{tmp_path}/filled"; echo opencode-go/old-flash; fi\n',
    )
    env = {"PATH": f"{plugin / 'bin'}:{tools}"}
    assert run.preflight(plugin, env, tmp_path, "glm") is None


def test_the_plugin_is_copied_without_git_too(tmp_path):
    # A copy of the repository without .git, as CI tests it
    repo = tmp_path / "repo"
    for name in (
        "skills/design/SKILL.md",
        "src/nichiyou_daiku/__init__.py",
        "src/nichiyou_daiku/__pycache__/x.pyc",
        ".venv/bin/python",
        "evals/design/cases/bench.toml",
        ".claude/settings.json",
        "CLAUDE.md",
    ):
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(name)
    copy = run.plugin_copy(repo, tmp_path / "copy")
    assert sorted(
        str(path.relative_to(copy)) for path in copy.rglob("*") if path.is_file()
    ) == ["skills/design/SKILL.md", "src/nichiyou_daiku/__init__.py"]


def test_the_self_check_judges_outside_the_repository(monkeypatch, tmp_path):
    places = []

    def self_check(request, model, repo, plugin, env, workdir, timeout_s):
        workdir.mkdir(parents=True, exist_ok=True)
        places.append(in_git_checkout(workdir))
        (workdir / "judge.json").write_text("{}")
        return []

    monkeypatch.setattr(run, "self_check", self_check)
    monkeypatch.setattr(run, "ENVIRONMENTS", tmp_path / "envs")
    monkeypatch.setattr(run, "preflight", lambda plugin, env, scratch, model: None)
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
    # What the first attempt left stays for a look at why it failed
    assert (tmp_path / "bench-1.attempt-1" / "draft.nd").read_text() == "half a bench"
    assert (tmp_path / "bench-1" / "design.nd").is_file()


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


def test_the_report_says_what_ran_and_sums_up_each_case(fake, tmp_path):
    run.main(["--cases", "side-table,bench", "--out", str(tmp_path)])
    report = (tmp_path / "report.md").read_text()
    assert (
        "- Agent: claude-sonnet-5 on Claude Code 2.1.0, API key: none; "
        "judge: claude-opus-5" in report
    )
    assert "at API prices" in report
    assert "| Case | Graded | All checks | Judge | Time | Usage | Tokens |" in report
    assert "| side-table | 1 | 1/1 | 1/1 | 5.0 min | 0.50 USD | 30.0 k |" in report
    assert "| bench | 0 | - | - | - | - | - |" in report
    # Free models cost nothing: tokens compare their runs
    assert "- Agent tokens in: 25.0 k (25.0 – 25.0)" in report
    assert "- Agent tokens out: 5.0 k (5.0 – 5.0)" in report


def test_a_run_without_an_api_key_source_says_nothing_of_one():
    row = {
        "case": "bench",
        "rep": 1,
        "design": "bench.nd",
        "checks": {name: {"passed": True, "detail": ""} for name in CHECKS},
        "judge": None,
        "judge_cost_usd": 0.0,
        **TRANSCRIPT.model_copy(
            update={
                "model": "opencode-go/deepseek-v4.1-flash",
                "tool": "opencode 1.18.30",
                "api_key_source": None,
            }
        ).model_dump(),
    }
    report = report_markdown({"cases": ["bench"], "reps": 1}, [row], [])
    assert (
        "- Agent: opencode-go/deepseek-v4.1-flash on opencode 1.18.30; judge: -"
        in report
    )


def test_a_run_of_changed_code_keeps_the_changes(fake, monkeypatch, tmp_path):
    monkeypatch.setattr(run, "_commit", lambda: "abc123-dirty")
    monkeypatch.setattr(run, "_diff", lambda: "--- a/skills/design/SKILL.md\n")
    run.main(["--cases", "side-table", "--out", str(tmp_path)])
    assert (tmp_path / "commit.diff").read_text() == "--- a/skills/design/SKILL.md\n"
    report = (tmp_path / "report.md").read_text()
    assert "- Commit: abc123-dirty (the changes are in commit.diff)" in report


def test_the_report_says_why_an_agent_stopped_early():
    row = {
        "case": "bench",
        "rep": 1,
        "design": None,
        "checks": {name: {"passed": False, "detail": ""} for name in CHECKS},
        "judge": None,
        "judge_cost_usd": 0.0,
        **TRANSCRIPT.model_copy(update={"ended": "length"}).model_dump(),
    }
    report = report_markdown({"cases": ["bench"], "reps": 1}, [row], [])
    assert "; its last step ended with length" in report


def test_a_bar_in_a_reason_keeps_the_table(tmp_path):
    row = {
        "case": "bench",
        "rep": 1,
        "design": "bench.nd",
        "checks": {name: {"passed": True, "detail": "a | b"} for name in CHECKS},
        "judge": None,
        "judge_cost_usd": 0.0,
        **TRANSCRIPT.model_dump(),
    }
    report = report_markdown({"cases": ["bench"], "reps": 1}, [row], [])
    assert "| valid | ✓ | a \\| b |" in report


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


def test_the_design_the_agent_checked_last_is_graded(fake, tmp_path):
    run.main(["--cases", "plant-stand", "--out", str(tmp_path)])
    [row] = load_jsonl(tmp_path / "results.jsonl")
    assert row["design"] == "stand.nd"
    report = (tmp_path / "report.md").read_text()
    assert "- Design: stand.nd (chosen of 2 .nd files);" in report


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


def test_a_bug_while_grading_one_run_spares_the_others(fake, monkeypatch, tmp_path):
    check_design = run.check_design

    def failing(path, case):
        if case.name == "tv-stand":
            raise RuntimeError("boom")
        return check_design(path, case)

    monkeypatch.setattr(run, "check_design", failing)
    assert run.main(["--cases", "side-table,tv-stand", "--out", str(tmp_path)]) == 0
    assert [row["case"] for row in load_jsonl(tmp_path / "results.jsonl")] == [
        "side-table"
    ]
    [error] = load_jsonl(tmp_path / "errors.jsonl")
    assert (error["case"], error["kind"]) == ("tv-stand", "harness")
    assert error["message"] == "RuntimeError: boom"
    assert (tmp_path / "report.md").is_file()


def test_an_endpoint_that_stops_answering_stops_the_evaluation(
    fake, monkeypatch, tmp_path, capsys
):
    tried = []

    def silent(request, model, plugin, env, workdir, timeout_s):
        tried.append(workdir.name)
        raise AgentFailed("stalled", "no output within 3 minutes")

    monkeypatch.setattr(run, "run_opencode", silent)
    code = run.main(
        ["--cases", "all", "--model", "deepseek", "--jobs", "1", "--out", str(tmp_path)]
    )
    assert code == 130
    # Three in a row, then no more runs start
    assert len(tried) == 3
    assert "stopped answering" in capsys.readouterr().err
    assert "(10 not graded yet)" in (tmp_path / "report.md").read_text()
    run.STOP.clear()


def test_an_earlier_run_is_compared(fake, tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    run.main(["--cases", "side-table", "--out", str(first)])
    run.main(["--cases", "side-table", "--out", str(second), "--compare", str(first)])
    assert (
        "| all checks | 1/1 | 100% | 21–100% | 100% (1/1) | ±0 pt |"
        in (second / "report.md").read_text()
    )


def test_only_the_cases_both_runs_have_are_compared(fake, tmp_path):
    # The earlier run also had a tv stand, which the side table design fails
    first, second = tmp_path / "first", tmp_path / "second"
    run.main(["--cases", "side-table,tv-stand", "--out", str(first)])
    run.main(["--cases", "side-table", "--out", str(second), "--compare", str(first)])
    report = (second / "report.md").read_text()
    assert "| all checks | 1/1 | 100% | 21–100% | 100% (1/1) | ±0 pt |" in report
    assert "on the cases both ran: side-table" in report


def test_rows_from_before_a_check_existed_are_not_counted_for_it():
    row = {
        "checks": {name: {"passed": True, "detail": ""} for name in CHECKS[:-1]},
        "judge": {name: {"passed": True, "detail": ""} for name in list(CRITERIA)[:-1]},
    }
    counts = rates([row])
    assert counts[CHECKS[-1]] == (0, 0)
    assert counts[f"judge: {list(CRITERIA)[-1]}"] == (0, 0)


def test_an_unknown_model_stops_before_anything_runs(fake, tmp_path, capsys):
    assert run.main(["--model", "gpt-9", "--out", str(tmp_path)]) == 2
    said = capsys.readouterr().err
    assert "Unknown model gpt-9" in said and "deepseek" in said
    assert fake == []


def test_a_model_outside_the_subscription_stops_before_anything_runs(
    fake, tmp_path, capsys
):
    model = "opencode/deepseek-v4.1-flash-free"
    assert run.main(["--model", model, "--out", str(tmp_path)]) == 2
    said = capsys.readouterr().err
    assert f"{model} runs on OpenCode Zen" in said and "opencode-go/" in said
    assert fake == []


def test_a_model_opencode_serves_runs_through_opencode(fake, monkeypatch, tmp_path):
    asked = []

    def opencode(request, model, plugin, env, workdir, timeout_s):
        asked.append(model)
        shutil.copy(EXAMPLE, workdir / "design.nd")
        return TRANSCRIPT

    monkeypatch.setattr(run, "run_opencode", opencode)
    run.main(["--cases", "side-table", "--model", "glm", "--out", str(tmp_path)])
    assert (asked, fake) == (["glm"], [])
    assert [row["case"] for row in load_jsonl(tmp_path / "results.jsonl")] == [
        "side-table"
    ]


def test_each_model_gets_its_own_run_directory(fake, monkeypatch, tmp_path):
    # Runs of two models started in the same second must not mix
    monkeypatch.setattr(run, "RUNS", tmp_path)
    monkeypatch.setattr(run, "run_opencode", lambda *args: TRANSCRIPT)
    run.main(["--cases", "side-table"])
    run.main(["--cases", "side-table", "--model", "opencode-go/glm-5.3-flash"])
    names = sorted(path.name for path in tmp_path.iterdir())
    assert len(names) == 2
    assert names[0].endswith("-opencode-go-glm-5.3-flash") or names[1].endswith(
        "-opencode-go-glm-5.3-flash"
    )
    assert any(name.endswith("-sonnet") for name in names)


def test_an_unknown_case_stops_before_anything_runs(fake, tmp_path, capsys):
    assert run.main(["--cases", "nope", "--out", str(tmp_path)]) == 2
    assert "Unknown case nope" in capsys.readouterr().err
    assert fake == []


def test_the_interval_of_a_pass_rate():
    assert wilson(0, 0) == (0.0, 1.0)
    low, high = wilson(5, 5)
    assert high == 1.0 and 0.5 < low < 0.6
