"""Tests for running the design skill with claude -p and reading its record."""

import json
import re
import sys
from pathlib import Path

import pytest

from evals.design.agent import (
    REFUSED,
    SKILL,
    AgentFailed,
    agent_command,
    agent_env,
    read_transcript,
    run_claude,
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


def test_the_repositorys_cli_comes_first_on_the_path():
    assert agent_env(REPO)["PATH"].startswith("/repo/.venv/bin")


def test_the_record_tells_what_the_agent_did():
    transcript = read_transcript(
        _events(
            {"type": "system", "subtype": "init", "model": "claude-sonnet-5"},
            _tool("Skill", skill=SKILL),
            _tool("Bash", command="nichiyou-daiku validate --json stool.nd"),
            _tool("Bash", command="nichiyou-daiku render stool.nd -o stool.png"),
            _tool("Read", file_path="/tmp/run/stool.png"),
            RESULT,
        )
    )
    assert transcript.model == "claude-sonnet-5"
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


def test_claude_codes_own_design_skill_does_not_count():
    # Claude Code ships a skill named plain "design"
    transcript = read_transcript(_events(_tool("Skill", skill="design"), RESULT))
    assert not transcript.skill_used


def test_a_record_without_a_result_is_a_failed_attempt():
    with pytest.raises(AgentFailed) as failed:
        read_transcript(_events(_tool("Skill", skill=SKILL)))
    assert failed.value.kind == "no_result"


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
