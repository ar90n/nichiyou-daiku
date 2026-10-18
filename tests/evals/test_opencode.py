"""Tests for running the design skill with opencode and reading its record."""

import json
import os
from pathlib import Path

import pytest

from evals.design.agent import AgentFailed
from evals.design.opencode import (
    MODELS,
    model_id,
    opencode_command,
    opencode_config,
    opencode_env,
    read_opencode,
    run_opencode,
    uses_opencode,
)

MODEL = "opencode/deepseek-v4.1-flash-free"


def _event(kind: str, at: int, **part) -> str:
    return json.dumps({"type": kind, "timestamp": at, "sessionID": "s", "part": part})


def _tool(tool: str, at: int, status: str = "completed", **args) -> str:
    state = {"status": status, "input": args}
    if status == "error":
        state["error"] = (
            "The user has specified a rule which prevents you from using this "
            "specific tool call."
        )
    return _event("tool_use", at, type="tool", tool=tool, state=state)


def _finish(at: int, reason: str, read: int, wrote: int) -> str:
    tokens = {
        "input": read,
        "output": wrote,
        "reasoning": 5,
        "cache": {"write": 0, "read": 1000},
    }
    return _event(
        "step_finish", at, type="step-finish", reason=reason, cost=0, tokens=tokens
    )


RECORD = [
    _event("step_start", 1_000, type="step-start"),
    _tool("skill", 2_000, name="design"),
    _tool("bash", 3_000, command="nichiyou-daiku validate --json stool.nd"),
    _tool("bash", 4_000, command="nichiyou-daiku render stool.nd -o stool.png"),
    _tool("read", 5_000, filePath="/tmp/ndk-eval-abc/stool-1/stool.png"),
    _tool("write", 6_000, filePath="/tmp/out.json", content="{}"),
    _tool("bash", 7_000, status="error", command="rm -f stool.png"),
    _finish(8_000, "tool-calls", read=100, wrote=50),
    _event("text", 9_000, type="text", text="The stool is in stool.nd."),
    _finish(91_000, "stop", read=200, wrote=20),
]


def test_short_names_point_at_free_models():
    assert model_id("deepseek") == MODELS["deepseek"] == MODEL
    assert model_id("opencode-go/glm-5.3") == "opencode-go/glm-5.3"
    assert uses_opencode("glm") and uses_opencode("opencode-go/kimi-k3")
    assert not uses_opencode("sonnet")


def test_the_command_runs_the_model_without_asking():
    command = opencode_command("make a stool", "deepseek")
    assert command[:2] == ["opencode", "run"]
    assert command[command.index("-m") + 1] == MODEL
    assert {"--format", "json", "--auto"} <= set(command)
    assert command[-1] == "make a stool"


def test_opencode_keeps_its_settings_and_records_apart():
    inherited = {
        "PATH": "/plugin/bin",
        "XDG_CACHE_HOME": "/cache",
        "OPENCODE_CONFIG": "/home/me/opencode.json",
    }
    env = opencode_env(inherited, Path("/run/opencode"))
    assert env["XDG_CONFIG_HOME"] == "/run/opencode/config"
    assert env["XDG_DATA_HOME"] == "/run/opencode/data"
    # opencode tells agents to work in <tmp>/opencode, which the user's own
    # sessions and every other run share
    assert env["TMPDIR"] == "/run/opencode/tmp"
    # Its locks, beside the cache the runs of one evaluation share
    assert env["XDG_STATE_HOME"] == "/cache/opencode-state"
    # Not the skills under ~/.claude or ~/.agents, nor the developer's settings
    assert env["OPENCODE_DISABLE_CLAUDE_CODE"] == "1"
    assert env["OPENCODE_DISABLE_EXTERNAL_SKILLS"] == "1"
    assert "OPENCODE_CONFIG" not in env
    assert env["PATH"] == "/plugin/bin"


def test_the_config_offers_the_plugin_s_skill_and_refuses_what_claude_refuses():
    config = opencode_config(Path("/plugin"))
    assert config["skills"] == {"paths": ["/plugin/skills"]}
    bash = config["permission"]["bash"]
    # The last matching rule wins
    assert list(bash)[0] == "*" and bash["*"] == "allow"
    assert bash["rm *"] == bash["git *"] == bash["curl *"] == "deny"
    assert config["permission"]["webfetch"] == "deny"
    # A subagent's work never reaches the record, and claude runs have none
    assert config["permission"]["task"] == "deny"
    assert config["share"] == "disabled"


def test_the_record_tells_what_the_agent_did():
    transcript = read_opencode(RECORD, MODEL, "opencode 1.18.30")
    assert transcript.skill_used
    assert (transcript.validates, transcript.renders, transcript.images_read) == (
        1,
        1,
        1,
    )
    assert transcript.denials == 1
    assert transcript.shared_tmp == 1
    assert transcript.last_checked == "stool.nd"
    assert (transcript.turns, transcript.duration_s, transcript.cost_usd) == (
        2,
        90.0,
        0.0,
    )
    # Input with the cache, output with the reasoning
    assert (transcript.input_tokens, transcript.output_tokens) == (2300, 80)
    assert (transcript.model, transcript.tool) == (MODEL, "opencode 1.18.30")
    assert transcript.api_key_source is None
    assert transcript.ended is None


def test_a_run_cut_at_the_model_s_output_limit_says_so():
    # GLM's free model stopped before writing a design: a failed design, and
    # the report says why
    cut = [*RECORD[:-1], _finish(91_000, "length", read=200, wrote=20)]
    assert read_opencode(cut, MODEL, "opencode").ended == "length"


def test_a_skill_the_agent_could_not_load_does_not_count():
    record = [_tool("skill", 1_000, status="error", name="design"), RECORD[-1]]
    assert not read_opencode(record, MODEL, "opencode").skill_used


def test_an_error_is_a_failed_attempt():
    # A free model's endpoint is sometimes unavailable
    error = json.dumps(
        {
            "type": "error",
            "timestamp": 2_000,
            "error": {
                "name": "APIError",
                "data": {
                    "message": "Upstream request failed: Endpoint is unavailable."
                },
            },
        }
    )
    with pytest.raises(AgentFailed) as failed:
        read_opencode([RECORD[0], error], MODEL, "opencode")
    assert failed.value.kind == "agent_error"
    assert "Endpoint is unavailable" in str(failed.value)


def test_a_record_without_a_finished_step_is_a_failed_attempt():
    with pytest.raises(AgentFailed) as failed:
        read_opencode(RECORD[:3], MODEL, "opencode")
    assert failed.value.kind == "no_result"


def test_a_run_reads_the_record_opencode_writes(tmp_path):
    # A stand-in for opencode that answers --version, writes the record and
    # notes where it ran
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (tmp_path / "record.jsonl").write_text("\n".join(RECORD) + "\n")
    fake = bin_dir / "opencode"
    fake.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = --version ]; then echo 1.18.30; exit 0; fi\n'
        f'echo "$PWD" > "{tmp_path}/cwd"\n'
        f'echo "$XDG_CONFIG_HOME" > "{tmp_path}/config_home"\n'
        f'[ -d "$TMPDIR" ] && echo "$TMPDIR" > "{tmp_path}/tmpdir"\n'
        f'cat "{tmp_path}/record.jsonl"\n'
    )
    fake.chmod(0o755)
    workdir = tmp_path / "stool-1"
    workdir.mkdir()
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    transcript = run_opencode(
        "make a stool", "deepseek", Path("/plugin"), env, workdir, 60
    )
    assert transcript.tool == "opencode 1.18.30"
    assert (workdir / "run.jsonl").read_text().splitlines() == RECORD
    assert (tmp_path / "cwd").read_text().strip() == str(workdir)
    # Settings beside the run's directory, not in it
    home = Path((tmp_path / "config_home").read_text().strip())
    assert home == tmp_path / "opencode" / "config"
    assert (tmp_path / "tmpdir").read_text().strip() == str(
        tmp_path / "opencode" / "tmp"
    )
    config = json.loads((home / "opencode" / "opencode.json").read_text())
    assert config["skills"] == {"paths": ["/plugin/skills"]}
