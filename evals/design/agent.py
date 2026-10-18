"""Run the design skill headlessly with ``claude -p`` and read back what
the agent did."""

import json
import os
import re
import shutil
import signal
import subprocess
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel

SKILL = "nichiyou-daiku:design"
# The agent works in a throwaway directory and uses the shell as a person
# would (sed, cat, python); only what reaches beyond it is refused
ALLOWED = ("Skill", "Read", "Write", "Edit", "Glob", "Grep", "Bash")
REFUSED = (
    "Bash(rm *)",
    "Bash(git *)",
    "Bash(curl *)",
    "Bash(wget *)",
    "Bash(ssh *)",
    "Bash(sudo *)",
    "Bash(uv tool *)",
    "Bash(pip *)",
    "WebFetch",
    "WebSearch",
)


class AgentFailed(Exception):
    """The run produced no usable record: it timed out or ``claude`` failed.
    ``cost_usd`` is the usage it reported, None when it reported none."""

    def __init__(self, kind: str, message: str, cost_usd: float | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.cost_usd = cost_usd


class Transcript(BaseModel, frozen=True):
    """What one run did, read from ``claude -p``'s stream-json record."""

    model: str | None
    skill_used: bool
    validates: int
    renders: int
    images_read: int
    denials: int
    turns: int
    duration_s: float
    cost_usd: float
    usage: dict


def isolated_flags() -> list[str]:
    """Keep the user's MCP servers, settings, skills and CLAUDE.md out."""
    return [
        "--strict-mcp-config",
        "--setting-sources",
        "project",
        "--no-session-persistence",
    ]


def agent_command(request: str, model: str, plugin: Path) -> list[str]:
    return [
        "claude",
        "-p",
        request,
        "--model",
        model,
        "--plugin-dir",
        str(plugin),
        "--output-format",
        "stream-json",
        "--verbose",
        *isolated_flags(),
        "--allowedTools",
        " ".join(ALLOWED),
        "--disallowedTools",
        " ".join(REFUSED),
    ]


def agent_env(repo: Path) -> dict[str, str]:
    """The environment of a run: the repository's own CLI comes first on
    PATH, so the plugin's launcher runs today's code, not an old install."""
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(repo / ".venv" / "bin"), env.get("PATH", "")])
    return env


def run_claude(
    command: list[str], cwd: Path, env: dict[str, str], stdout: Path, timeout_s: float
) -> int:
    """Run ``command`` in ``cwd``, writing its output to ``stdout``; kill it
    with everything it started when it runs past ``timeout_s``."""
    with (
        stdout.open("w", encoding="utf-8") as out,
        (cwd / "stderr.log").open("w", encoding="utf-8") as err,
    ):
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            start_new_session=True,
        )
        try:
            return process.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise AgentFailed(
                "timeout", f"no result within {timeout_s / 60:g} minutes"
            ) from None
        finally:
            forget_project(cwd)


def forget_project(cwd: Path) -> None:
    """Remove the directory Claude Code keeps for ``cwd`` under
    ~/.claude/projects when it holds no file: every run has its own
    directory, and each would leave an empty one behind."""
    name = re.sub("[^A-Za-z0-9]", "-", str(cwd.resolve()))
    project = Path.home() / ".claude" / "projects" / name
    if project.is_dir() and not any(path.is_file() for path in project.rglob("*")):
        shutil.rmtree(project)


def read_transcript(lines: Iterable[str]) -> Transcript:
    """Summarize a stream-json record; raise ``AgentFailed`` without a
    final result or when the result reports an error (a usage limit, an API
    error past the retries): those say nothing about the design."""
    model = None
    skill_used = False
    validates = renders = images_read = 0
    result: dict | None = None
    for line in lines:
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("type") == "system" and event.get("subtype") == "init":
            model = event.get("model")
        elif event.get("type") == "assistant":
            for block in event["message"].get("content", []):
                if block.get("type") != "tool_use":
                    continue
                name, args = block.get("name"), block.get("input", {})
                if name == "Skill" and args.get("skill") == SKILL:
                    skill_used = True
                elif name == "Bash":
                    command = args.get("command", "")
                    validates += "nichiyou-daiku validate" in command
                    renders += "nichiyou-daiku render" in command
                elif name == "Read" and args.get("file_path", "").endswith(".png"):
                    images_read += 1
        elif event.get("type") == "result":
            result = event
    if result is None:
        raise AgentFailed("no_result", "claude stopped without a final result")
    if result.get("is_error"):
        raise AgentFailed(
            "agent_error",
            f"claude reported an error: {str(result.get('result', ''))[:300]}",
            cost_usd=result.get("total_cost_usd"),
        )
    return Transcript(
        model=model,
        skill_used=skill_used,
        validates=validates,
        renders=renders,
        images_read=images_read,
        denials=len(result.get("permission_denials") or []),
        turns=result.get("num_turns", 0),
        duration_s=result.get("duration_ms", 0) / 1000,
        cost_usd=result.get("total_cost_usd", 0.0),
        usage=result.get("usage") or {},
    )


def run_agent(
    request: str,
    model: str,
    plugin: Path,
    repo: Path,
    workdir: Path,
    timeout_s: float,
) -> Transcript:
    """Have the design skill of ``plugin`` answer ``request`` in ``workdir``,
    with ``repo``'s CLI."""
    record = workdir / "run.jsonl"
    code = run_claude(
        agent_command(request, model, plugin),
        workdir,
        agent_env(repo),
        record,
        timeout_s,
    )
    lines = record.read_text(encoding="utf-8").splitlines()
    try:
        return read_transcript(lines)
    except AgentFailed:
        raise
    except Exception as e:
        raise AgentFailed("bad_record", f"unreadable record ({e}); exit {code}") from e
