"""Run the design skill with opencode, for LLMs other than Claude's, and
read back what the agent did."""

import json
import subprocess
from collections.abc import Iterable
from pathlib import Path

from .agent import AgentFailed, Transcript, cli_calls, in_shared_tmp, run_claude

# The OpenCode Go subscription's models by short name. Only its models run:
# opencode/... is OpenCode Zen, billed apart. Its catalog changes, so the
# names live here only
MODELS = {
    "deepseek": "opencode-go/deepseek-v4.1-flash",
    "glm": "opencode-go/glm-5.3-flash",
}
# The skill's name in its SKILL.md: opencode gives it no plugin prefix
SKILL = "design"
# The commands the claude runs refuse, so that the tool makes no difference
REFUSED_COMMANDS = (
    "rm *",
    "git *",
    "curl *",
    "wget *",
    "ssh *",
    "sudo *",
    "uv tool *",
    "pip *",
)
# A working run writes its first event within seconds; an endpoint that
# stopped answering leaves the record empty
FIRST_OUTPUT_S = 180.0
# What opencode answers a tool call that a permission rule refuses
_DENIED = "rule which prevents"


def uses_opencode(model: str) -> bool:
    return model in MODELS or model.startswith("opencode-go/")


def model_id(model: str) -> str:
    return MODELS.get(model, model)


def opencode_command(request: str, model: str) -> list[str]:
    return [
        "opencode",
        "run",
        "--format",
        "json",
        "--auto",
        "-m",
        model_id(model),
        request,
    ]


def opencode_config(plugin: Path) -> dict:
    """The run's opencode.json: the plugin's skills and the refusals."""
    return {
        "$schema": "https://opencode.ai/config.json",
        "autoupdate": False,
        "share": "disabled",
        "skills": {"paths": [str(plugin / "skills")]},
        "permission": {
            # opencode applies the last matching rule: allow, then refuse
            "bash": {"*": "allow", **dict.fromkeys(REFUSED_COMMANDS, "deny")},
            "webfetch": "deny",
            "websearch": "deny",
            # A subagent's work never reaches the record; claude runs have none
            "task": "deny",
        },
    }


def opencode_env(env: dict[str, str], home: Path) -> dict[str, str]:
    """``env`` without the developer's OPENCODE_* settings, with opencode's
    settings, records and scratch space under ``home``, its locks beside the
    cache that one evaluation's runs share, and without the skills under
    ~/.claude and ~/.agents."""
    kept = {key: value for key, value in env.items() if not key.startswith("OPENCODE_")}
    cache = env.get("XDG_CACHE_HOME")
    return {
        **kept,
        "XDG_CONFIG_HOME": str(home / "config"),
        "XDG_DATA_HOME": str(home / "data"),
        # opencode tells agents to work in <tmp>/opencode, which the user's
        # own sessions and every other run share
        "TMPDIR": str(home / "tmp"),
        "XDG_STATE_HOME": str(
            Path(cache) / "opencode-state" if cache else home / "state"
        ),
        "OPENCODE_DISABLE_CLAUDE_CODE": "1",
        "OPENCODE_DISABLE_EXTERNAL_SKILLS": "1",
    }


def read_opencode(lines: Iterable[str], model: str, tool: str) -> Transcript:
    """Summarize ``opencode run --format json``'s record; raise
    ``AgentFailed`` when it reports an error or stops before a step ends."""
    events = [json.loads(line) for line in lines if line.strip()]
    for event in events:
        if event.get("type") == "error":
            message = (event.get("error") or {}).get("data", {}).get("message", "")
            raise AgentFailed("agent_error", f"opencode reported an error: {message}")
    skill_used = False
    validates = renders = images_read = denials = shared_tmp = 0
    last_checked = None
    for event in events:
        part = event.get("part") or {}
        if event.get("type") != "tool_use":
            continue
        state = part.get("state") or {}
        args = state.get("input") or {}
        target = " ".join(
            str(args.get(key, "")) for key in ("command", "filePath", "path")
        )
        shared_tmp += in_shared_tmp(target)
        if state.get("status") == "error":
            denials += _DENIED in str(state.get("error", ""))
            continue
        if part.get("tool") == "skill" and args.get("name") == SKILL:
            skill_used = True
        elif part.get("tool") == "bash":
            valid, drawn, checked = cli_calls(args.get("command", ""))
            validates, renders = validates + valid, renders + drawn
            last_checked = checked or last_checked
        elif part.get("tool") == "read" and args.get("filePath", "").endswith(".png"):
            images_read += 1
    steps = [event["part"] for event in events if event.get("type") == "step_finish"]
    if not steps:
        raise AgentFailed("no_result", "opencode stopped before a step finished")
    tokens = [step.get("tokens") or {} for step in steps]
    read = sum(
        t.get("input", 0)
        + t.get("cache", {}).get("read", 0)
        + t.get("cache", {}).get("write", 0)
        for t in tokens
    )
    wrote = sum(t.get("output", 0) + t.get("reasoning", 0) for t in tokens)
    return Transcript(
        model=model,
        skill_used=skill_used,
        validates=validates,
        renders=renders,
        images_read=images_read,
        denials=denials,
        turns=len(steps),
        duration_s=(events[-1]["timestamp"] - events[0]["timestamp"]) / 1000,
        cost_usd=sum(step.get("cost") or 0.0 for step in steps),
        usage={"input": read, "output": wrote},
        shared_tmp=shared_tmp,
        last_checked=last_checked,
        tool=tool,
        api_key_source=None,
        input_tokens=read,
        output_tokens=wrote,
        ended=None if steps[-1].get("reason") == "stop" else steps[-1].get("reason"),
    )


def run_opencode(
    request: str,
    model: str,
    plugin: Path,
    env: dict[str, str],
    workdir: Path,
    timeout_s: float,
) -> Transcript:
    """Have the design skill of ``plugin`` answer ``request`` with opencode
    in ``workdir``, in ``env`` (see ``agent_env``). opencode's settings and
    records go beside ``workdir``, so the agent does not see them."""
    home = workdir.parent / "opencode"
    config = home / "config" / "opencode"
    config.mkdir(parents=True, exist_ok=True)
    (home / "tmp").mkdir(exist_ok=True)
    (config / "opencode.json").write_text(
        json.dumps(opencode_config(plugin), indent=2), encoding="utf-8"
    )
    env = opencode_env(env, home)
    record = workdir / "run.jsonl"
    code = run_claude(
        opencode_command(request, model),
        workdir,
        env,
        record,
        timeout_s,
        first_output_s=FIRST_OUTPUT_S,
    )
    version = subprocess.run(
        ["opencode", "--version"], env=env, capture_output=True, text=True
    ).stdout.strip()
    lines = record.read_text(encoding="utf-8").splitlines()
    try:
        return read_opencode(lines, model_id(model), f"opencode {version}")
    except AgentFailed:
        raise
    except Exception as e:
        raise AgentFailed("bad_record", f"unreadable record ({e}); exit {code}") from e
