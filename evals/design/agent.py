"""Run the design skill headlessly with ``claude -p`` and read back what
the agent did."""

import json
import os
import re
import shutil
import signal
import subprocess
import threading
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
# A path in /tmp outside the run's own directories (ndk-eval-*): parallel
# runs share it, so a run may read another's scratch file
_SHARED_TMP = re.compile(r"/tmp/(?!ndk-eval-)")
# A CLI command, after any global options (-q, --verbose)
_COMMAND = r"nichiyou-daiku(?:\s+-[-\w]+)*\s+{}\b"
_VALIDATE = re.compile(_COMMAND.format("validate"))
_RENDER = re.compile(_COMMAND.format("render"))
# The design a validate or render command reads, after its options
_CHECKED = re.compile(
    _COMMAND.format("(?:validate|render)") + r"(?:\s+-[-\w]+)*\s+([^\s;&|]+\.nd)\b"
)


# Set when the evaluation is stopped: running sessions are ended and no new
# one starts
STOP = threading.Event()
# The sessions running now. Reentrant: the stop handler may run on a thread
# that holds it
_live: set[subprocess.Popen] = set()
_stopped: set[int] = set()
_live_lock = threading.RLock()


def stop_all() -> None:
    """End every running session with everything it started, and start no
    new one. Sessions run in their own process groups, so a Ctrl-C in the
    terminal does not reach them."""
    STOP.set()
    with _live_lock:
        for process in _live:
            _stopped.add(process.pid)
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


class AgentFailed(Exception):
    """The run produced no usable record: it timed out or ``claude`` failed.
    ``cost_usd`` is the usage it reported, None when it reported none."""

    def __init__(self, kind: str, message: str, cost_usd: float | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.cost_usd = cost_usd


class Transcript(BaseModel, frozen=True):
    """What one run did, read from the agent's record."""

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
    shared_tmp: int
    """Tool calls that touched /tmp outside the run's own directories."""
    last_checked: str | None
    """The file name of the last design the agent validated or rendered."""
    tool: str | None
    """The agent's tool and its version, as "Claude Code 2.1.0"."""
    api_key_source: str | None
    """Where claude took its credentials from: "none" is the plan's login."""
    input_tokens: int
    """Tokens read, including those from the cache."""
    output_tokens: int


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


def agent_env(plugin: Path, cache: Path, uv_cache: str, venv: Path) -> dict[str, str]:
    """The environment of a run, as a person who installed the plugin has
    it: the plugin's launcher first on PATH, building the CLI from the
    plugin's source into an environment under ``cache``, so edits to the
    repository during an evaluation do not reach it. Never an installed CLI
    or the developer's ``venv`` (python with nichiyou_daiku, the dev tools),
    which uv run puts on PATH."""
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)
    kept = [
        entry
        for entry in env.get("PATH", "").split(os.pathsep)
        if entry and Path(entry) != venv / "bin"
    ]
    env["PATH"] = os.pathsep.join([str(plugin / "bin"), *kept])
    # Otherwise the launcher hands over to a CLI it finds on PATH
    env["NICHIYOU_DAIKU_WRAPPED"] = "1"
    # The launcher keeps its environments under XDG_CACHE_HOME; uv's own
    # cache stays where it is
    env["XDG_CACHE_HOME"] = str(cache)
    env["UV_CACHE_DIR"] = uv_cache
    return env


def run_claude(
    command: list[str], cwd: Path, env: dict[str, str], stdout: Path, timeout_s: float
) -> int:
    """Run ``command`` in ``cwd``, writing its output to ``stdout``; kill it
    with everything it started when it runs past ``timeout_s``."""
    with (
        stdout.open("w", encoding="utf-8") as out,
        (cwd / "stderr.log").open("w", encoding="utf-8") as err,
        _live_lock,
    ):
        if STOP.is_set():
            raise AgentFailed("stopped", "the evaluation was stopped")
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            start_new_session=True,
        )
        # A pid of a session stopped earlier may come back
        _stopped.discard(process.pid)
        _live.add(process)
    try:
        code = process.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        raise AgentFailed(
            "timeout", f"no result within {timeout_s / 60:g} minutes"
        ) from None
    finally:
        with _live_lock:
            _live.discard(process)
        forget_project(cwd)
    if process.pid in _stopped:
        raise AgentFailed("stopped", "the evaluation was stopped")
    return code


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
    validates = renders = images_read = shared_tmp = 0
    last_checked = version = key_source = None
    result: dict | None = None
    for line in lines:
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("type") == "system" and event.get("subtype") == "init":
            model = event.get("model")
            version = event.get("claude_code_version")
            key_source = event.get("apiKeySource")
        elif event.get("type") == "assistant":
            for block in event["message"].get("content", []):
                if block.get("type") != "tool_use":
                    continue
                name, args = block.get("name"), block.get("input", {})
                target = " ".join(
                    str(args.get(key, "")) for key in ("command", "file_path", "path")
                )
                shared_tmp += bool(_SHARED_TMP.search(target))
                if name == "Skill" and args.get("skill") == SKILL:
                    skill_used = True
                elif name == "Bash":
                    command = args.get("command", "")
                    validates += len(_VALIDATE.findall(command))
                    renders += len(_RENDER.findall(command))
                    for checked in _CHECKED.findall(command):
                        last_checked = Path(checked.strip("'\"")).name
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
    usage = result.get("usage") or {}
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
        usage=usage,
        shared_tmp=shared_tmp,
        last_checked=last_checked,
        tool=f"Claude Code {version}" if version else None,
        api_key_source=key_source,
        input_tokens=sum(
            usage.get(key, 0)
            for key in (
                "input_tokens",
                "cache_creation_input_tokens",
                "cache_read_input_tokens",
            )
        ),
        output_tokens=usage.get("output_tokens", 0),
    )


def run_agent(
    request: str,
    model: str,
    plugin: Path,
    env: dict[str, str],
    workdir: Path,
    timeout_s: float,
) -> Transcript:
    """Have the design skill of ``plugin`` answer ``request`` in ``workdir``,
    in ``env`` (see ``agent_env``)."""
    record = workdir / "run.jsonl"
    code = run_claude(
        agent_command(request, model, plugin), workdir, env, record, timeout_s
    )
    lines = record.read_text(encoding="utf-8").splitlines()
    try:
        return read_transcript(lines)
    except AgentFailed:
        raise
    except Exception as e:
        raise AgentFailed("bad_record", f"unreadable record ({e}); exit {code}") from e
