"""Tests for running the design skill with claude -p and reading its record."""

import json
import os
import re
import sys
import threading
import time
from pathlib import Path

import pytest

from evals.design.agent import (
    REFUSED,
    SKILL,
    STOP,
    AgentFailed,
    agent_command,
    agent_env,
    read_transcript,
    run_claude,
    stop_all,
)

REPO = Path("/repo")


def _events(*events: dict) -> list[str]:
    return [json.dumps(event) for event in events]


def _tool(name: str, **args) -> dict:
    return {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "name": name, "input": args}]},
    }


RESULT = {
    "type": "result",
    "num_turns": 12,
    "duration_ms": 90_000,
    "total_cost_usd": 0.42,
    "usage": {"input_tokens": 10, "output_tokens": 20},
    "permission_denials": [{"tool_name": "Bash"}],
    "is_error": False,
}


def test_the_command_loads_only_this_plugin_and_no_user_setup():
    command = agent_command("make a stool", "sonnet", REPO)
    assert command[:3] == ["claude", "-p", "make a stool"]
    assert command[command.index("--plugin-dir") + 1] == "/repo"
    assert command[command.index("--model") + 1] == "sonnet"
    assert "--strict-mcp-config" in command
    assert command[command.index("--setting-sources") + 1] == "project"
    assert "Bash(rm *)" in command[command.index("--disallowedTools") + 1]
    assert "WebFetch" in REFUSED


def test_a_run_uses_the_plugin_s_own_cli(monkeypatch):
    # As for a person who installed the plugin: its launcher builds the CLI
    # from the plugin's source into an environment of its own, never an
    # installed CLI or the developer's .venv (python with nichiyou_daiku,
    # the dev tools), which make eval's uv run puts on PATH
    monkeypatch.setenv("PATH", "/repo/.venv/bin:/usr/bin")
    monkeypatch.setenv("VIRTUAL_ENV", "/repo/.venv")
    env = agent_env(Path("/plugin"), Path("/cache"), "/uv-cache", Path("/repo/.venv"))
    assert env["PATH"] == "/plugin/bin:/usr/bin"
    assert "VIRTUAL_ENV" not in env
    # The launcher runs the plugin's source, not a CLI found on PATH
    assert env["NICHIYOU_DAIKU_WRAPPED"] == "1"
    assert env["XDG_CACHE_HOME"] == "/cache"
    assert env["UV_CACHE_DIR"] == "/uv-cache"


def test_the_record_tells_what_the_agent_did():
    transcript = read_transcript(
        _events(
            {
                "type": "system",
                "subtype": "init",
                "model": "claude-sonnet-5",
                "claude_code_version": "2.1.0",
                "apiKeySource": "none",
            },
            _tool("Skill", skill=SKILL),
            _tool("Bash", command="nichiyou-daiku validate --json stool.nd"),
            _tool("Bash", command="nichiyou-daiku render stool.nd -o stool.png"),
            _tool("Read", file_path="/tmp/run/stool.png"),
            RESULT,
        )
    )
    assert transcript.model == "claude-sonnet-5"
    # An alias such as sonnet moves to new models, and an API key in the
    # environment would bill an account instead of the plan
    assert (transcript.claude_code_version, transcript.api_key_source) == (
        "2.1.0",
        "none",
    )
    assert transcript.skill_used
    assert (transcript.validates, transcript.renders, transcript.images_read) == (
        1,
        1,
        1,
    )
    assert (transcript.turns, transcript.duration_s, transcript.cost_usd) == (
        12,
        90.0,
        0.42,
    )
    assert transcript.denials == 1


def test_each_validate_and_render_in_a_command_counts():
    transcript = read_transcript(
        _events(
            _tool(
                "Bash",
                command="nichiyou-daiku -q validate a.nd && nichiyou-daiku validate b.nd",
            ),
            _tool("Bash", command="nichiyou-daiku --verbose render a.nd -o a.png"),
            RESULT,
        )
    )
    assert (transcript.validates, transcript.renders) == (2, 1)


def test_the_last_design_checked_is_kept():
    transcript = read_transcript(
        _events(
            _tool("Bash", command="nichiyou-daiku validate draft.nd"),
            _tool(
                "Bash", command="cd /tmp/x && nichiyou-daiku render ./table.nd -o t.png"
            ),
            _tool("Bash", command="ls"),
            RESULT,
        )
    )
    assert transcript.last_checked == "table.nd"


def test_files_in_the_shared_tmp_are_counted():
    # Parallel runs share /tmp: a run may read another's scratch file
    transcript = read_transcript(
        _events(
            _tool(
                "Bash", command="nichiyou-daiku validate --json x.nd > /tmp/out.json"
            ),
            _tool("Read", file_path="/tmp/out.json"),
            _tool("Read", file_path="/tmp/ndk-eval-plugin-abc/skills/design/SKILL.md"),
            _tool("Bash", command="cat /tmp/ndk-eval-xyz/bench-1/bench.nd"),
            RESULT,
        )
    )
    assert transcript.shared_tmp == 2


def test_claude_codes_own_design_skill_does_not_count():
    # Claude Code ships a skill named plain "design"
    transcript = read_transcript(_events(_tool("Skill", skill="design"), RESULT))
    assert not transcript.skill_used


def test_a_record_without_a_result_is_a_failed_attempt():
    with pytest.raises(AgentFailed) as failed:
        read_transcript(_events(_tool("Skill", skill=SKILL)))
    assert failed.value.kind == "no_result"


def test_a_result_that_reports_an_error_is_a_failed_attempt():
    # A usage limit or an API error that outlasts the retries still ends with
    # a result; it says nothing about the design
    error = {**RESULT, "is_error": True, "result": "Claude AI usage limit reached"}
    with pytest.raises(AgentFailed) as failed:
        read_transcript(_events(_tool("Skill", skill=SKILL), error))
    assert failed.value.kind == "agent_error"
    assert "usage limit" in str(failed.value)
    assert failed.value.cost_usd == 0.42


@pytest.fixture
def stop():
    yield stop_all
    STOP.clear()


def test_stopping_ends_a_running_session(tmp_path, stop):
    command = [sys.executable, "-c", "import time; time.sleep(30)"]
    failed = []

    def run():
        try:
            run_claude(command, tmp_path, dict(os.environ), tmp_path / "out", 60)
        except AgentFailed as e:
            failed.append(e.kind)

    thread = threading.Thread(target=run)
    thread.start()
    time.sleep(0.5)
    stop()
    thread.join(5)
    assert not thread.is_alive()
    assert failed == ["stopped"]


def test_no_session_starts_after_a_stop(tmp_path, stop):
    stop()
    command = [sys.executable, "-c", "open('started', 'w')"]
    with pytest.raises(AgentFailed) as failed:
        run_claude(command, tmp_path, dict(os.environ), tmp_path / "out", 60)
    assert failed.value.kind == "stopped"
    assert not (tmp_path / "started").exists()


def test_a_run_past_its_limit_is_killed(tmp_path):
    command = [sys.executable, "-c", "import time; time.sleep(30)"]
    with pytest.raises(AgentFailed) as failed:
        run_claude(command, tmp_path, {}, tmp_path / "out.jsonl", timeout_s=0.5)
    assert failed.value.kind == "timeout"


def test_the_empty_project_directory_of_a_run_is_removed(tmp_path, monkeypatch):
    # Claude Code keeps an (empty) auto-memory directory per working directory
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    workdir = tmp_path / "runs" / "stool-1"
    workdir.mkdir(parents=True)
    projects = tmp_path / "home" / ".claude" / "projects"
    left = projects / re.sub("[^A-Za-z0-9]", "-", str(workdir)) / "memory"
    left.mkdir(parents=True)
    run_claude(
        [sys.executable, "-c", "pass"], workdir, {}, workdir / "out.jsonl", timeout_s=5
    )
    assert not left.parent.exists()


def test_a_project_directory_with_files_is_kept(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    workdir = tmp_path / "runs" / "stool-1"
    workdir.mkdir(parents=True)
    projects = tmp_path / "home" / ".claude" / "projects"
    note = projects / re.sub("[^A-Za-z0-9]", "-", str(workdir)) / "memory" / "note.md"
    note.parent.mkdir(parents=True)
    note.write_text("kept")
    run_claude(
        [sys.executable, "-c", "pass"], workdir, {}, workdir / "out.jsonl", timeout_s=5
    )
    assert note.exists()
