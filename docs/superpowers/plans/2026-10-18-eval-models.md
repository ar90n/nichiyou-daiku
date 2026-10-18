# Choosing the LLM of the Design Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `make eval MODEL=deepseek` (and `make eval-full`, `python -m evals.design.run --model ...`) runs the design evaluation with Claude Code's models or, through opencode, with DeepSeek, GLM and other opencode models; every LLM reads the same skill, runs isolated like `claude -p`, and the report shows its tool and tokens.

**Architecture:**
- **The skill (`skills/design/SKILL.md`):** links the DSL specification relative to itself instead of through `${CLAUDE_PLUGIN_ROOT}`, which only Claude Code substitutes.
- **The record (`agent.py`, `report.py`):** `Transcript` names the agent's tool and version and counts input and output tokens; the report shows them, since a free model's usage in USD is 0.
- **opencode (`opencode.py`):** runs `opencode run --format json --auto -m <model>` in the run's directory with its settings, records and the plugin's skill path in a directory beside it, refuses what the `claude` runs refuse, and reads its JSON events into a `Transcript`. Every session's `PWD` is its directory.
- **Choosing the model (`run.py`, `Makefile`):** `--model` picks Claude Code or opencode; the preflight checks opencode and its model (filling opencode's cache); each model's run directory carries its name.

**Tech Stack:** Python 3.13, pydantic, subprocess, the `claude` CLI, opencode 1.18.30 (`opencode run --format json --auto`, `opencode models`), pytest. Run commands with `uv run` from the repository root on branch `feat/eval-models`.

**Spec:** `docs/superpowers/specs/2026-10-18-eval-models-design.md` (Japanese; binding).

**How the code was checked:** every patch below was written and run in a scratch copy before this plan. In a fresh clone of this branch, applying each task's test patch and then its implementation patch passes `ruff format --check`, `ruff check`, `pyright` and the whole suite; each task's tests fail before its implementation patch as each step's `Expected:` says. With the real CLIs: `--self-check` passed; `plant-stand` with `deepseek` passed every machine check and every judge question (12.0 minutes, 38 turns, 3.2 M input and 71 k output tokens, 0.2 USD for the judge); with `glm` the agent loaded the skill and read the specification through the new link, then its fourth step hit the model's output limit (`length`) before any design, in 3.5 minutes. With `PWD` set, neither wrote anything outside its run (`git status` stayed empty); before, both wrote their designs into the repository.

## Global Constraints

- **One LLM per evaluation:** `--model` (make: `MODEL`, default `sonnet`). `sonnet`, `opus`, `haiku` and `claude-...` run with `claude -p`; `deepseek` (`opencode/deepseek-v4.1-flash-free`), `glm` (`opencode/glm-5.3-flash-free`), `opencode/...` and `opencode-go/...` run with opencode. Any other name stops with exit code 2 before anything runs.
- **The short names live in one table** (`MODELS` in `evals/design/opencode.py`): opencode's free catalog changes.
- **The same skill for every LLM:** no file under `skills/` may contain `${CLAUDE_PLUGIN_ROOT}`.
- **opencode isolation:** `XDG_CONFIG_HOME` and `XDG_DATA_HOME` in a directory beside the run's directory, `OPENCODE_DISABLE_CLAUDE_CODE=1`, the run's `opencode.json` with `skills.paths` = the plugin copy's `skills/`, `share: disabled`, `autoupdate: false`, and the refusals `rm *`, `git *`, `curl *`, `wget *`, `ssh *`, `sudo *`, `uv tool *`, `pip *`, `webfetch`, `websearch`.
- **Every session's `PWD` is its working directory** (opencode takes its directory from `PWD`).
- **The judge is opus through `claude -p` for every LLM.**
- **Failures:** an `error` event (a free endpoint's 503) or a record without a finished step is a failed attempt in `errors.jsonl`, for `--resume` to retry.
- **Messages:** code, comments, docstrings, the report and the README in English; comments few and saying why.
- **Patches:** apply each patch exactly with `git apply` from the repository root. Each one sits between the `git apply <<'EOF'` line and the closing `EOF` line.
- **Commits:** run `make check` before every commit and commit only if it passes: `make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log; [ $rc -eq 0 ] && git commit ...`.
- **Never commit:** dotfiles, `CLAUDE.md` or `evals/design/runs/`.

## Review Focus

1. **The real opencode and its free endpoints.** Unit tests stub `opencode`; only real runs exercise `skills.paths`, the permission rules, the JSON events and the endpoints' 503s. Run Task 4, Step 5 before merging, and read the run's `run.jsonl` when a number looks wrong.
2. **An agent writing outside its directory.** `PWD` now points at the run's directory, but nothing stops a write to another absolute path; only `/tmp` outside the run's directories is counted (`shared /tmp`). After a real run, `git status` must stay empty.
3. **opencode's own state.** Its cache (filled by the preflight) is shared by the runs of one evaluation; its sessions must not land in the user's `~/.local/share/opencode`, and its config must not come from `~/.config/opencode` or `~/.claude`.
4. **Long free-model runs.** A GLM trial took 27 minutes; the 40-minute limit ends slower ones as failed attempts, which `--resume` retries.
5. **Tokens mean different things per tool.** Claude Code's input counts cache reads and writes; opencode's adds reasoning to the output. Compare tokens within one LLM, across skill changes, more than across LLMs.

---

### Task 1: The skill links the DSL specification itself

**Files:**
- Modify: `skills/design/SKILL.md` (step 2, "Read")
- Test: `tests/test_plugin.py` (replaces `test_plugin_root_appears_only_in_skill_bodies`)

**Interfaces:**
- Consumes: nothing.
- Produces: no file under `skills/` contains `${CLAUDE_PLUGIN_ROOT}`; SKILL.md links `../../docs/dsl-specification.md`, which `tests/test_docs.py` checks exists.

- [ ] **Step 1: Write the failing test**

````bash
git apply <<'EOF'
diff --git a/tests/test_plugin.py b/tests/test_plugin.py
index c5ddb17..263d1e4 100644
--- a/tests/test_plugin.py
+++ b/tests/test_plugin.py
@@ -284,14 +284,13 @@ def test_skill_frontmatter_names_and_describes_the_skill(path):
     assert 0 < len(fields["description"]) <= 1024
 
 
-def test_plugin_root_appears_only_in_skill_bodies():
-    # Claude Code substitutes it in SKILL.md; a file read later keeps it literal
+def test_the_skill_does_not_rely_on_claude_code_s_plugin_root():
+    # Only Claude Code substitutes it: opencode and other tools read the same
+    # skill, so files are linked relative to the skill instead
     literal = [
         str(path.relative_to(ROOT))
         for path in (ROOT / "skills").rglob("*")
-        if path.is_file()
-        and path.name != "SKILL.md"
-        and "${CLAUDE_PLUGIN_ROOT}" in path.read_text()
+        if path.is_file() and "${CLAUDE_PLUGIN_ROOT}" in path.read_text()
     ]
     assert literal == []
 
EOF
````

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/test_plugin.py tests/test_docs.py -q`
Expected: 1 failed, 76 passed (`test_the_skill_does_not_rely_on_claude_code_s_plugin_root`: `['skills/design/SKILL.md'] == []`)

- [ ] **Step 3: Implement**

Claude Code shows a skill's base directory and opencode its location, so a link relative to SKILL.md reaches the specification in both; with `${CLAUDE_PLUGIN_ROOT}` unsubstituted, a DeepSeek trial searched the disk with `find /`.

````bash
git apply <<'EOF'
diff --git a/skills/design/SKILL.md b/skills/design/SKILL.md
index a2a9ea9..c3e4ca8 100644
--- a/skills/design/SKILL.md
+++ b/skills/design/SKILL.md
@@ -13,7 +13,7 @@ Check the request against [requirements.md](requirements.md). Ask only for what
 
 ## 2. Read
 
-- The DSL specification: `${CLAUDE_PLUGIN_ROOT}/docs/dsl-specification.md`. Every rule in it applies: faces and offsets, placement, variables, unknowns, fasteners.
+- The DSL specification: [docs/dsl-specification.md](../../docs/dsl-specification.md), in the plugin's root two directories above this skill. Every rule in it applies: faces and offsets, placement, variables, unknowns, fasteners.
 - [patterns.md](patterns.md): verified joints and layouts, length formulas, naming and a checklist.
 - [examples/](examples/): requirements with a matching `.nd` (a side table, a two-tier shelf, a corner joint). Start from the closest one.
 
EOF
````

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_plugin.py tests/test_docs.py -q`
Expected: 77 passed

- [ ] **Step 5: Commit**

```bash
make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log
[ $rc -eq 0 ] && git add skills/design/SKILL.md tests/test_plugin.py && git commit -m "fix: Link the DSL specification from the skill itself

Only Claude Code substitutes CLAUDE_PLUGIN_ROOT; under opencode a
DeepSeek trial searched the disk for the specification. SKILL.md now
links it relative to itself, which every tool can follow."
```

---

### Task 2: The tool and the tokens in the record and the report

**Files:**
- Modify: `evals/design/agent.py` (`Transcript`, `read_transcript`), `evals/design/report.py`, `evals/design/README.md`
- Test: `tests/evals/test_agent.py`, `tests/evals/test_run.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `Transcript` fields `tool: str | None` (as `"Claude Code 2.1.0"`; replaces `claude_code_version`), `api_key_source: str | None`, `input_tokens: int` (input, cache creation and cache reads), `output_tokens: int`. The report's lines `- Agent: <models> on <tools>[, API key: <sources>]; judge: <models>` (no API key part when no run has one), `- Agent tokens in: <median> k (<min> – <max>)`, `- Agent tokens out: ...`, and a `Tokens` column (median of input and output, in thousands) in the table of cases.

- [ ] **Step 1: Write the failing tests**

````bash
git apply <<'EOF'
diff --git a/tests/evals/test_agent.py b/tests/evals/test_agent.py
index 1d4cef0..d9991db 100644
--- a/tests/evals/test_agent.py
+++ b/tests/evals/test_agent.py
@@ -94,10 +94,11 @@ def test_the_record_tells_what_the_agent_did():
     assert transcript.model == "claude-sonnet-5"
     # An alias such as sonnet moves to new models, and an API key in the
     # environment would bill an account instead of the plan
-    assert (transcript.claude_code_version, transcript.api_key_source) == (
-        "2.1.0",
+    assert (transcript.tool, transcript.api_key_source) == (
+        "Claude Code 2.1.0",
         "none",
     )
+    assert (transcript.input_tokens, transcript.output_tokens) == (10, 20)
     assert transcript.skill_used
     assert (transcript.validates, transcript.renders, transcript.images_read) == (
         1,
@@ -112,6 +113,17 @@ def test_the_record_tells_what_the_agent_did():
     assert transcript.denials == 1
 
 
+def test_tokens_read_from_the_cache_count_as_input():
+    usage = {
+        "input_tokens": 10,
+        "cache_creation_input_tokens": 100,
+        "cache_read_input_tokens": 1000,
+        "output_tokens": 20,
+    }
+    transcript = read_transcript(_events({**RESULT, "usage": usage}))
+    assert (transcript.input_tokens, transcript.output_tokens) == (1110, 20)
+
+
 def test_each_validate_and_render_in_a_command_counts():
     transcript = read_transcript(
         _events(
diff --git a/tests/evals/test_run.py b/tests/evals/test_run.py
index 798d9d8..a81a518 100644
--- a/tests/evals/test_run.py
+++ b/tests/evals/test_run.py
@@ -31,8 +31,10 @@ TRANSCRIPT = Transcript(
     usage={},
     shared_tmp=0,
     last_checked=None,
-    claude_code_version="2.1.0",
+    tool="Claude Code 2.1.0",
     api_key_source="none",
+    input_tokens=25_000,
+    output_tokens=5_000,
 )
 
 
@@ -293,9 +295,35 @@ def test_the_report_says_what_ran_and_sums_up_each_case(fake, tmp_path):
         "judge: claude-opus-5" in report
     )
     assert "at API prices" in report
-    assert "| Case | Graded | All checks | Judge | Time | Usage |" in report
-    assert "| side-table | 1 | 1/1 | 1/1 | 5.0 min | 0.50 USD |" in report
-    assert "| bench | 0 | - | - | - | - |" in report
+    assert "| Case | Graded | All checks | Judge | Time | Usage | Tokens |" in report
+    assert "| side-table | 1 | 1/1 | 1/1 | 5.0 min | 0.50 USD | 30.0 k |" in report
+    assert "| bench | 0 | - | - | - | - | - |" in report
+    # Free models cost nothing: tokens compare their runs
+    assert "- Agent tokens in: 25.0 k (25.0 – 25.0)" in report
+    assert "- Agent tokens out: 5.0 k (5.0 – 5.0)" in report
+
+
+def test_a_run_without_an_api_key_source_says_nothing_of_one():
+    row = {
+        "case": "bench",
+        "rep": 1,
+        "design": "bench.nd",
+        "checks": {name: {"passed": True, "detail": ""} for name in CHECKS},
+        "judge": None,
+        "judge_cost_usd": 0.0,
+        **TRANSCRIPT.model_copy(
+            update={
+                "model": "opencode/deepseek-v4.1-flash-free",
+                "tool": "opencode 1.18.30",
+                "api_key_source": None,
+            }
+        ).model_dump(),
+    }
+    report = report_markdown({"cases": ["bench"], "reps": 1}, [row], [])
+    assert (
+        "- Agent: opencode/deepseek-v4.1-flash-free on opencode 1.18.30; judge: -"
+        in report
+    )
 
 
 def test_a_run_of_changed_code_keeps_the_changes(fake, monkeypatch, tmp_path):
EOF
````

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/evals -q`
Expected: collection error in `tests/evals/test_run.py`: `ValidationError` for `Transcript` (`claude_code_version` Field required)

- [ ] **Step 3: Implement**

A free model's usage is 0 USD, so tokens are what compare its runs; the tool's name and version say which harness designed.

````bash
git apply <<'EOF'
diff --git a/evals/design/README.md b/evals/design/README.md
index ccc9fca..4e99d0e 100644
--- a/evals/design/README.md
+++ b/evals/design/README.md
@@ -19,4 +19,4 @@ uv run python -m evals.design.run --self-check   # check the judge on known desi
 - Machine checks (`checks.py`) read the design with nichiyou-daiku. The judge (`judge.py`) is a second `claude -p` that looks at the rendered picture (drawn in the run's `judge/` directory from a copy named `design.nd`, since the picture shows the file name) and answers three questions with a JSON schema.
 - Runs at the same time share `/tmp`, where agents like to keep scratch files (`/tmp/validate_out.json`), so one may read another's. Runs go rep by rep, so the same request's runs do not run together, and the report counts the runs that used `/tmp` outside their own directory; use `--jobs 1` when that count is not 0 and the numbers matter.
 - Ctrl-C (or SIGTERM) ends the running `claude` sessions, starts no more and writes the report; `--resume` continues.
-- `results.jsonl` holds one row per graded design, `errors.jsonl` the attempts that gave no result (timeouts, errors, usage limits); `--resume` retries those and keeps what the earlier attempt left in `<case>-<rep>.attempt-<n>/`. When only the judge failed, the run keeps its machine checks in `unjudged.json` and `--resume` judges it again without running the agent. `report.md` shows what ran (models, Claude Code version, where the credentials came from, the commit and, for uncommitted changes, `commit.diff`), the pass rates with their 95% intervals, a line per case, the time and usage, and each design's picture.
+- `results.jsonl` holds one row per graded design, `errors.jsonl` the attempts that gave no result (timeouts, errors, usage limits); `--resume` retries those and keeps what the earlier attempt left in `<case>-<rep>.attempt-<n>/`. When only the judge failed, the run keeps its machine checks in `unjudged.json` and `--resume` judges it again without running the agent. `report.md` shows what ran (models, the agent's tool and its version, where Claude Code took its credentials from, the commit and, for uncommitted changes, `commit.diff`), the pass rates with their 95% intervals, a line per case, the time, usage and tokens, and each design's picture.
diff --git a/evals/design/agent.py b/evals/design/agent.py
index fabd1a1..a48f125 100644
--- a/evals/design/agent.py
+++ b/evals/design/agent.py
@@ -77,7 +77,7 @@ class AgentFailed(Exception):
 
 
 class Transcript(BaseModel, frozen=True):
-    """What one run did, read from ``claude -p``'s stream-json record."""
+    """What one run did, read from the agent's record."""
 
     model: str | None
     skill_used: bool
@@ -93,9 +93,13 @@ class Transcript(BaseModel, frozen=True):
     """Tool calls that touched /tmp outside the run's own directories."""
     last_checked: str | None
     """The file name of the last design the agent validated or rendered."""
-    claude_code_version: str | None
+    tool: str | None
+    """The agent's tool and its version, as "Claude Code 2.1.0"."""
     api_key_source: str | None
     """Where claude took its credentials from: "none" is the plan's login."""
+    input_tokens: int
+    """Tokens read, including those from the cache."""
+    output_tokens: int
 
 
 def isolated_flags() -> list[str]:
@@ -249,6 +253,7 @@ def read_transcript(lines: Iterable[str]) -> Transcript:
             f"claude reported an error: {str(result.get('result', ''))[:300]}",
             cost_usd=result.get("total_cost_usd"),
         )
+    usage = result.get("usage") or {}
     return Transcript(
         model=model,
         skill_used=skill_used,
@@ -259,11 +264,20 @@ def read_transcript(lines: Iterable[str]) -> Transcript:
         turns=result.get("num_turns", 0),
         duration_s=result.get("duration_ms", 0) / 1000,
         cost_usd=result.get("total_cost_usd", 0.0),
-        usage=result.get("usage") or {},
+        usage=usage,
         shared_tmp=shared_tmp,
         last_checked=last_checked,
-        claude_code_version=version,
+        tool=f"Claude Code {version}" if version else None,
         api_key_source=key_source,
+        input_tokens=sum(
+            usage.get(key, 0)
+            for key in (
+                "input_tokens",
+                "cache_creation_input_tokens",
+                "cache_read_input_tokens",
+            )
+        ),
+        output_tokens=usage.get("output_tokens", 0),
     )
 
 
diff --git a/evals/design/report.py b/evals/design/report.py
index 7448b6c..63e4d42 100644
--- a/evals/design/report.py
+++ b/evals/design/report.py
@@ -106,7 +106,7 @@ def _values(rows: list[dict], key: str) -> str:
 def _case_line(case: str, rows: list[dict]) -> str:
     runs = [row for row in rows if row["case"] == case]
     if not runs:
-        return f"| {case} | 0 | - | - | - | - |"
+        return f"| {case} | 0 | - | - | - | - | - |"
     judged = [row for row in runs if row.get("judge")]
     judge_passed = sum(
         all(verdict["passed"] for verdict in row["judge"].values()) for row in judged
@@ -114,12 +114,17 @@ def _case_line(case: str, rows: list[dict]) -> str:
     judge = f"{judge_passed}/{len(judged)}" if judged else "-"
     minutes = median(row["duration_s"] / 60 for row in runs)
     usage = median(row["cost_usd"] for row in runs)
+    tokens = median(_tokens(row) for row in runs) / 1000
     return (
         f"| {case} | {len(runs)} | {sum(all_passed(row) for row in runs)}/{len(runs)} "
-        f"| {judge} | {minutes:.1f} min | {usage:.2f} USD |"
+        f"| {judge} | {minutes:.1f} min | {usage:.2f} USD | {tokens:.1f} k |"
     )
 
 
+def _tokens(row: dict) -> int:
+    return row.get("input_tokens", 0) + row.get("output_tokens", 0)
+
+
 def _mark(passed: bool | None) -> str:
     return {True: "✓", False: "✗", None: "–"}[passed]
 
@@ -155,10 +160,13 @@ def report_markdown(
         f"- Repetitions: {meta.get('reps')}; model: {meta.get('model')}; judge: {meta.get('judge_model')}",
         f"- Commit: {meta.get('commit')}"
         + (f" (the changes are in {meta['diff']})" if meta.get("diff") else ""),
-        f"- Agent: {_values(rows, 'model')} on Claude Code "
-        f"{_values(rows, 'claude_code_version')}, API key: "
-        f"{_values(rows, 'api_key_source')}; judge: "
-        f"{_values([row for row in rows if row.get('judge')], 'judge_model')}",
+        f"- Agent: {_values(rows, 'model')} on {_values(rows, 'tool')}"
+        + (
+            f", API key: {_values(keyed, 'api_key_source')}"
+            if (keyed := [row for row in rows if row.get("api_key_source")])
+            else ""
+        )
+        + f"; judge: {_values([row for row in rows if row.get('judge')], 'judge_model')}",
         f"- Graded runs: {len(rows)}; failed attempts: {len(errors)} ({pending} not graded yet)",
         f"- Runs that used /tmp outside their own directory: "
         f"{sum(1 for row in rows if row.get('shared_tmp'))} of {len(rows)}",
@@ -193,8 +201,8 @@ def report_markdown(
         "",
         "## Cases",
         "",
-        "| Case | Graded | All checks | Judge | Time | Usage |",
-        "|---|---|---|---|---|---|",
+        "| Case | Graded | All checks | Judge | Time | Usage | Tokens |",
+        "|---|---|---|---|---|---|---|",
         *(_case_line(case, rows) for case in meta.get("cases", [])),
     ]
     lines += [
@@ -208,6 +216,8 @@ def report_markdown(
         f"- Turns: {_spread([float(row['turns']) for row in rows], '')}",
         f"- Agent usage: {_spread([row['cost_usd'] for row in rows], 'USD')}",
         f"- Judge usage: {_spread([row['judge_cost_usd'] for row in rows if row.get('judge')], 'USD')}",
+        f"- Agent tokens in: {_spread([row.get('input_tokens', 0) / 1000 for row in rows], 'k')}",
+        f"- Agent tokens out: {_spread([row.get('output_tokens', 0) / 1000 for row in rows], 'k')}",
         _failed_usage(errors),
         f"- Total usage: {_total_usage(rows, errors):.2f} USD",
         "",
EOF
````

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/evals -q`
Expected: 73 passed

- [ ] **Step 5: Commit**

```bash
make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log
[ $rc -eq 0 ] && git add evals tests/evals && git commit -m "feat: Record the agent's tool and tokens and report them

A free model's usage is 0 USD, so the report now gives the input and
output tokens of every run, and names the tool and version that ran."
```

---

### Task 3: Running the design skill with opencode

**Files:**
- Create: `evals/design/opencode.py`
- Modify: `evals/design/agent.py` (`CLAUDE_MODELS`, `is_claude`, `cli_calls`, `in_shared_tmp`; `run_claude` sets `PWD`)
- Test: `tests/evals/test_opencode.py`, `tests/evals/test_agent.py`

**Interfaces:**
- Consumes: Task 2's `Transcript` fields; `agent.AgentFailed`, `agent.run_claude`.
- Produces: in `opencode.py`: `MODELS` (short name → model), `SKILL = "design"`, `REFUSED_COMMANDS`, `uses_opencode(model: str) -> bool`, `model_id(model: str) -> str`, `opencode_command(request: str, model: str) -> list[str]`, `opencode_config(plugin: Path) -> dict`, `opencode_env(env: dict[str, str], home: Path) -> dict[str, str]`, `read_opencode(lines: Iterable[str], model: str, tool: str) -> Transcript`, `run_opencode(request, model, plugin, env, workdir, timeout_s) -> Transcript` (the same signature as `agent.run_agent`; opencode's settings and records go to `workdir.parent / "opencode"`). In `agent.py`: `Transcript.ended: str | None = None` (why the last step ended when not with the answer; opencode's `length` is the model's output limit), `CLAUDE_MODELS`, `is_claude(model: str) -> bool`, `cli_calls(command: str) -> tuple[int, int, str | None]` (validate calls, render calls, the last design either reads), `in_shared_tmp(text: str) -> bool`; `run_claude` gives every session `PWD` = its directory.

- [ ] **Step 1: Write the failing tests**

````bash
git apply <<'EOF'
diff --git a/tests/evals/test_agent.py b/tests/evals/test_agent.py
index d9991db..2d9df3d 100644
--- a/tests/evals/test_agent.py
+++ b/tests/evals/test_agent.py
@@ -225,6 +225,15 @@ def test_no_session_starts_after_a_stop(tmp_path, stop):
     assert not (tmp_path / "started").exists()
 
 
+def test_a_session_s_pwd_is_its_directory(tmp_path):
+    # opencode takes its working directory from PWD, not from the process: a
+    # PWD left at the repository had the agent write its design there
+    command = [sys.executable, "-c", "import os; print(os.environ['PWD'])"]
+    env = {**os.environ, "PWD": "/somewhere/else"}
+    run_claude(command, tmp_path, env, tmp_path / "out", 60)
+    assert (tmp_path / "out").read_text().strip() == str(tmp_path)
+
+
 def test_a_run_past_its_limit_is_killed(tmp_path):
     command = [sys.executable, "-c", "import time; time.sleep(30)"]
     with pytest.raises(AgentFailed) as failed:
diff --git a/tests/evals/test_opencode.py b/tests/evals/test_opencode.py
new file mode 100644
index 0000000..b9a219e
--- /dev/null
+++ b/tests/evals/test_opencode.py
@@ -0,0 +1,188 @@
+"""Tests for running the design skill with opencode and reading its record."""
+
+import json
+import os
+from pathlib import Path
+
+import pytest
+
+from evals.design.agent import AgentFailed
+from evals.design.opencode import (
+    MODELS,
+    model_id,
+    opencode_command,
+    opencode_config,
+    opencode_env,
+    read_opencode,
+    run_opencode,
+    uses_opencode,
+)
+
+MODEL = "opencode/deepseek-v4.1-flash-free"
+
+
+def _event(kind: str, at: int, **part) -> str:
+    return json.dumps({"type": kind, "timestamp": at, "sessionID": "s", "part": part})
+
+
+def _tool(tool: str, at: int, status: str = "completed", **args) -> str:
+    state = {"status": status, "input": args}
+    if status == "error":
+        state["error"] = (
+            "The user has specified a rule which prevents you from using this "
+            "specific tool call."
+        )
+    return _event("tool_use", at, type="tool", tool=tool, state=state)
+
+
+def _finish(at: int, reason: str, read: int, wrote: int) -> str:
+    tokens = {
+        "input": read,
+        "output": wrote,
+        "reasoning": 5,
+        "cache": {"write": 0, "read": 1000},
+    }
+    return _event(
+        "step_finish", at, type="step-finish", reason=reason, cost=0, tokens=tokens
+    )
+
+
+RECORD = [
+    _event("step_start", 1_000, type="step-start"),
+    _tool("skill", 2_000, name="design"),
+    _tool("bash", 3_000, command="nichiyou-daiku validate --json stool.nd"),
+    _tool("bash", 4_000, command="nichiyou-daiku render stool.nd -o stool.png"),
+    _tool("read", 5_000, filePath="/tmp/ndk-eval-abc/stool-1/stool.png"),
+    _tool("write", 6_000, filePath="/tmp/out.json", content="{}"),
+    _tool("bash", 7_000, status="error", command="rm -f stool.png"),
+    _finish(8_000, "tool-calls", read=100, wrote=50),
+    _event("text", 9_000, type="text", text="The stool is in stool.nd."),
+    _finish(91_000, "stop", read=200, wrote=20),
+]
+
+
+def test_short_names_point_at_free_models():
+    assert model_id("deepseek") == MODELS["deepseek"] == MODEL
+    assert model_id("opencode-go/glm-5.3") == "opencode-go/glm-5.3"
+    assert uses_opencode("glm") and uses_opencode("opencode-go/kimi-k3")
+    assert not uses_opencode("sonnet")
+
+
+def test_the_command_runs_the_model_without_asking():
+    command = opencode_command("make a stool", "deepseek")
+    assert command[:2] == ["opencode", "run"]
+    assert command[command.index("-m") + 1] == MODEL
+    assert {"--format", "json", "--auto"} <= set(command)
+    assert command[-1] == "make a stool"
+
+
+def test_opencode_keeps_its_settings_and_records_apart():
+    env = opencode_env({"PATH": "/plugin/bin"}, Path("/run/opencode"))
+    assert env["XDG_CONFIG_HOME"] == "/run/opencode/config"
+    assert env["XDG_DATA_HOME"] == "/run/opencode/data"
+    # Not the skills and CLAUDE.md under ~/.claude
+    assert env["OPENCODE_DISABLE_CLAUDE_CODE"] == "1"
+    assert env["PATH"] == "/plugin/bin"
+
+
+def test_the_config_offers_the_plugin_s_skill_and_refuses_what_claude_refuses():
+    config = opencode_config(Path("/plugin"))
+    assert config["skills"] == {"paths": ["/plugin/skills"]}
+    bash = config["permission"]["bash"]
+    # The last matching rule wins
+    assert list(bash)[0] == "*" and bash["*"] == "allow"
+    assert bash["rm *"] == bash["git *"] == bash["curl *"] == "deny"
+    assert config["permission"]["webfetch"] == "deny"
+    assert config["share"] == "disabled"
+
+
+def test_the_record_tells_what_the_agent_did():
+    transcript = read_opencode(RECORD, MODEL, "opencode 1.18.30")
+    assert transcript.skill_used
+    assert (transcript.validates, transcript.renders, transcript.images_read) == (
+        1,
+        1,
+        1,
+    )
+    assert transcript.denials == 1
+    assert transcript.shared_tmp == 1
+    assert transcript.last_checked == "stool.nd"
+    assert (transcript.turns, transcript.duration_s, transcript.cost_usd) == (
+        2,
+        90.0,
+        0.0,
+    )
+    # Input with the cache, output with the reasoning
+    assert (transcript.input_tokens, transcript.output_tokens) == (2300, 80)
+    assert (transcript.model, transcript.tool) == (MODEL, "opencode 1.18.30")
+    assert transcript.api_key_source is None
+    assert transcript.ended is None
+
+
+def test_a_run_cut_at_the_model_s_output_limit_says_so():
+    # GLM's free model stopped before writing a design: a failed design, and
+    # the report says why
+    cut = [*RECORD[:-1], _finish(91_000, "length", read=200, wrote=20)]
+    assert read_opencode(cut, MODEL, "opencode").ended == "length"
+
+
+def test_a_skill_the_agent_could_not_load_does_not_count():
+    record = [_tool("skill", 1_000, status="error", name="design"), RECORD[-1]]
+    assert not read_opencode(record, MODEL, "opencode").skill_used
+
+
+def test_an_error_is_a_failed_attempt():
+    # A free model's endpoint is sometimes unavailable
+    error = json.dumps(
+        {
+            "type": "error",
+            "timestamp": 2_000,
+            "error": {
+                "name": "APIError",
+                "data": {
+                    "message": "Upstream request failed: Endpoint is unavailable."
+                },
+            },
+        }
+    )
+    with pytest.raises(AgentFailed) as failed:
+        read_opencode([RECORD[0], error], MODEL, "opencode")
+    assert failed.value.kind == "agent_error"
+    assert "Endpoint is unavailable" in str(failed.value)
+
+
+def test_a_record_without_a_finished_step_is_a_failed_attempt():
+    with pytest.raises(AgentFailed) as failed:
+        read_opencode(RECORD[:3], MODEL, "opencode")
+    assert failed.value.kind == "no_result"
+
+
+def test_a_run_reads_the_record_opencode_writes(tmp_path):
+    # A stand-in for opencode that answers --version, writes the record and
+    # notes where it ran
+    bin_dir = tmp_path / "bin"
+    bin_dir.mkdir()
+    (tmp_path / "record.jsonl").write_text("\n".join(RECORD) + "\n")
+    fake = bin_dir / "opencode"
+    fake.write_text(
+        "#!/bin/sh\n"
+        'if [ "$1" = --version ]; then echo 1.18.30; exit 0; fi\n'
+        f'echo "$PWD" > "{tmp_path}/cwd"\n'
+        f'echo "$XDG_CONFIG_HOME" > "{tmp_path}/config_home"\n'
+        f'cat "{tmp_path}/record.jsonl"\n'
+    )
+    fake.chmod(0o755)
+    workdir = tmp_path / "stool-1"
+    workdir.mkdir()
+    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
+    transcript = run_opencode(
+        "make a stool", "deepseek", Path("/plugin"), env, workdir, 60
+    )
+    assert transcript.tool == "opencode 1.18.30"
+    assert (workdir / "run.jsonl").read_text().splitlines() == RECORD
+    assert (tmp_path / "cwd").read_text().strip() == str(workdir)
+    # Settings beside the run's directory, not in it
+    home = Path((tmp_path / "config_home").read_text().strip())
+    assert home == tmp_path / "opencode" / "config"
+    config = json.loads((home / "opencode" / "opencode.json").read_text())
+    assert config["skills"] == {"paths": ["/plugin/skills"]}
EOF
````

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/evals/test_opencode.py tests/evals/test_agent.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'evals.design.opencode'`

- [ ] **Step 3: Implement**

What the code relies on, checked with opencode 1.18.30: `opencode run --format json` writes one event per line (`step_start`, `tool_use` with `part.tool` and `part.state.{status,input,error}`, `step_finish` with `part.tokens` and `part.cost`, `text`, and `error` with `error.data.message`); a tool call a permission rule refuses ends with status `error` and an error saying "a rule which prevents you"; `skills.paths` in `opencode.json` offers a skill from another directory; opencode takes its working directory from `PWD`, not from the process: with `PWD` left at the repository, DeepSeek and GLM both wrote their designs there; and a step that hits the model's output limit ends with reason `length` and ends the run (GLM's free model did, before writing a design). That is the model's failure, not the harness's, so it stays a graded run, with `ended` saying why.

````bash
git apply <<'EOF'
diff --git a/evals/design/agent.py b/evals/design/agent.py
index a48f125..2d2e5ea 100644
--- a/evals/design/agent.py
+++ b/evals/design/agent.py
@@ -40,6 +40,27 @@ _RENDER = re.compile(_COMMAND.format("render"))
 _CHECKED = re.compile(
     _COMMAND.format("(?:validate|render)") + r"(?:\s+-[-\w]+)*\s+([^\s;&|]+\.nd)\b"
 )
+# Claude Code's model names; other LLMs run through opencode
+CLAUDE_MODELS = ("sonnet", "opus", "haiku")
+
+
+def is_claude(model: str) -> bool:
+    return model in CLAUDE_MODELS or model.startswith("claude-")
+
+
+def cli_calls(command: str) -> tuple[int, int, str | None]:
+    """The validate and render calls in a shell command, and the file name
+    of the last design one of them reads."""
+    checked = [Path(name.strip("'\"")).name for name in _CHECKED.findall(command)]
+    return (
+        len(_VALIDATE.findall(command)),
+        len(_RENDER.findall(command)),
+        checked[-1] if checked else None,
+    )
+
+
+def in_shared_tmp(text: str) -> bool:
+    return bool(_SHARED_TMP.search(text))
 
 
 # Set when the evaluation is stopped: running sessions are ended and no new
@@ -100,6 +121,9 @@ class Transcript(BaseModel, frozen=True):
     input_tokens: int
     """Tokens read, including those from the cache."""
     output_tokens: int
+    ended: str | None = None
+    """Why the agent's last step ended, when not with its answer: opencode's
+    "length" is the model's output limit."""
 
 
 def isolated_flags() -> list[str]:
@@ -171,7 +195,9 @@ def run_claude(
         process = subprocess.Popen(
             command,
             cwd=cwd,
-            env=env,
+            # opencode takes its working directory from PWD, not from the
+            # process: left at the repository, it had the agent write there
+            env={**env, "PWD": str(cwd)},
             stdin=subprocess.DEVNULL,
             stdout=out,
             stderr=err,
@@ -232,15 +258,13 @@ def read_transcript(lines: Iterable[str]) -> Transcript:
                 target = " ".join(
                     str(args.get(key, "")) for key in ("command", "file_path", "path")
                 )
-                shared_tmp += bool(_SHARED_TMP.search(target))
+                shared_tmp += in_shared_tmp(target)
                 if name == "Skill" and args.get("skill") == SKILL:
                     skill_used = True
                 elif name == "Bash":
-                    command = args.get("command", "")
-                    validates += len(_VALIDATE.findall(command))
-                    renders += len(_RENDER.findall(command))
-                    for checked in _CHECKED.findall(command):
-                        last_checked = Path(checked.strip("'\"")).name
+                    valid, drawn, checked = cli_calls(args.get("command", ""))
+                    validates, renders = validates + valid, renders + drawn
+                    last_checked = checked or last_checked
                 elif name == "Read" and args.get("file_path", "").endswith(".png"):
                     images_read += 1
         elif event.get("type") == "result":
diff --git a/evals/design/opencode.py b/evals/design/opencode.py
new file mode 100644
index 0000000..b23155a
--- /dev/null
+++ b/evals/design/opencode.py
@@ -0,0 +1,175 @@
+"""Run the design skill with opencode, for LLMs other than Claude's, and
+read back what the agent did."""
+
+import json
+import subprocess
+from collections.abc import Iterable
+from pathlib import Path
+
+from .agent import AgentFailed, Transcript, cli_calls, in_shared_tmp, run_claude
+
+# opencode's free models by short name. Its catalog changes, so the names
+# live here only
+MODELS = {
+    "deepseek": "opencode/deepseek-v4.1-flash-free",
+    "glm": "opencode/glm-5.3-flash-free",
+}
+# The skill's name in its SKILL.md: opencode gives it no plugin prefix
+SKILL = "design"
+# The commands the claude runs refuse, so that the tool makes no difference
+REFUSED_COMMANDS = (
+    "rm *",
+    "git *",
+    "curl *",
+    "wget *",
+    "ssh *",
+    "sudo *",
+    "uv tool *",
+    "pip *",
+)
+# What opencode answers a tool call that a permission rule refuses
+_DENIED = "rule which prevents"
+
+
+def uses_opencode(model: str) -> bool:
+    return model in MODELS or model.startswith(("opencode/", "opencode-go/"))
+
+
+def model_id(model: str) -> str:
+    return MODELS.get(model, model)
+
+
+def opencode_command(request: str, model: str) -> list[str]:
+    return [
+        "opencode",
+        "run",
+        "--format",
+        "json",
+        "--auto",
+        "-m",
+        model_id(model),
+        request,
+    ]
+
+
+def opencode_config(plugin: Path) -> dict:
+    """The run's opencode.json: the plugin's skills and the refusals."""
+    return {
+        "$schema": "https://opencode.ai/config.json",
+        "autoupdate": False,
+        "share": "disabled",
+        "skills": {"paths": [str(plugin / "skills")]},
+        "permission": {
+            # opencode applies the last matching rule: allow, then refuse
+            "bash": {"*": "allow", **dict.fromkeys(REFUSED_COMMANDS, "deny")},
+            "webfetch": "deny",
+            "websearch": "deny",
+        },
+    }
+
+
+def opencode_env(env: dict[str, str], home: Path) -> dict[str, str]:
+    """``env`` with opencode's settings and records under ``home``, apart
+    from the user's, and without the skills and CLAUDE.md under ~/.claude."""
+    return {
+        **env,
+        "XDG_CONFIG_HOME": str(home / "config"),
+        "XDG_DATA_HOME": str(home / "data"),
+        "OPENCODE_DISABLE_CLAUDE_CODE": "1",
+    }
+
+
+def read_opencode(lines: Iterable[str], model: str, tool: str) -> Transcript:
+    """Summarize ``opencode run --format json``'s record; raise
+    ``AgentFailed`` when it reports an error or stops before a step ends."""
+    events = [json.loads(line) for line in lines if line.strip()]
+    for event in events:
+        if event.get("type") == "error":
+            message = (event.get("error") or {}).get("data", {}).get("message", "")
+            raise AgentFailed("agent_error", f"opencode reported an error: {message}")
+    skill_used = False
+    validates = renders = images_read = denials = shared_tmp = 0
+    last_checked = None
+    for event in events:
+        part = event.get("part") or {}
+        if event.get("type") != "tool_use":
+            continue
+        state = part.get("state") or {}
+        args = state.get("input") or {}
+        target = " ".join(
+            str(args.get(key, "")) for key in ("command", "filePath", "path")
+        )
+        shared_tmp += in_shared_tmp(target)
+        if state.get("status") == "error":
+            denials += _DENIED in str(state.get("error", ""))
+            continue
+        if part.get("tool") == "skill" and args.get("name") == SKILL:
+            skill_used = True
+        elif part.get("tool") == "bash":
+            valid, drawn, checked = cli_calls(args.get("command", ""))
+            validates, renders = validates + valid, renders + drawn
+            last_checked = checked or last_checked
+        elif part.get("tool") == "read" and args.get("filePath", "").endswith(".png"):
+            images_read += 1
+    steps = [event["part"] for event in events if event.get("type") == "step_finish"]
+    if not steps:
+        raise AgentFailed("no_result", "opencode stopped before a step finished")
+    tokens = [step.get("tokens") or {} for step in steps]
+    read = sum(
+        t.get("input", 0)
+        + t.get("cache", {}).get("read", 0)
+        + t.get("cache", {}).get("write", 0)
+        for t in tokens
+    )
+    wrote = sum(t.get("output", 0) + t.get("reasoning", 0) for t in tokens)
+    return Transcript(
+        model=model,
+        skill_used=skill_used,
+        validates=validates,
+        renders=renders,
+        images_read=images_read,
+        denials=denials,
+        turns=len(steps),
+        duration_s=(events[-1]["timestamp"] - events[0]["timestamp"]) / 1000,
+        cost_usd=sum(step.get("cost") or 0.0 for step in steps),
+        usage={"input": read, "output": wrote},
+        shared_tmp=shared_tmp,
+        last_checked=last_checked,
+        tool=tool,
+        api_key_source=None,
+        input_tokens=read,
+        output_tokens=wrote,
+        ended=None if steps[-1].get("reason") == "stop" else steps[-1].get("reason"),
+    )
+
+
+def run_opencode(
+    request: str,
+    model: str,
+    plugin: Path,
+    env: dict[str, str],
+    workdir: Path,
+    timeout_s: float,
+) -> Transcript:
+    """Have the design skill of ``plugin`` answer ``request`` with opencode
+    in ``workdir``, in ``env`` (see ``agent_env``). opencode's settings and
+    records go beside ``workdir``, so the agent does not see them."""
+    home = workdir.parent / "opencode"
+    config = home / "config" / "opencode"
+    config.mkdir(parents=True, exist_ok=True)
+    (config / "opencode.json").write_text(
+        json.dumps(opencode_config(plugin), indent=2), encoding="utf-8"
+    )
+    env = opencode_env(env, home)
+    record = workdir / "run.jsonl"
+    code = run_claude(opencode_command(request, model), workdir, env, record, timeout_s)
+    version = subprocess.run(
+        ["opencode", "--version"], env=env, capture_output=True, text=True
+    ).stdout.strip()
+    lines = record.read_text(encoding="utf-8").splitlines()
+    try:
+        return read_opencode(lines, model_id(model), f"opencode {version}")
+    except AgentFailed:
+        raise
+    except Exception as e:
+        raise AgentFailed("bad_record", f"unreadable record ({e}); exit {code}") from e
EOF
````

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/evals/test_opencode.py tests/evals/test_agent.py -q`
Expected: 26 passed

- [ ] **Step 5: Commit**

```bash
make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log
[ $rc -eq 0 ] && git add evals tests/evals && git commit -m "feat: Run the design skill with opencode

opencode runs the same skill from the plugin copy with its settings and
records apart from the user's, refuses what the claude runs refuse, and
its JSON events become the same record. Every session's PWD is its
directory: opencode takes its own from PWD and wrote into the
repository otherwise."
```

---

### Task 4: Choosing the LLM

**Files:**
- Modify: `evals/design/run.py` (model check, the runner per model, the preflight, the run directory's name), `evals/design/report.py` (why an agent stopped early), `Makefile` (`MODEL`), `evals/design/README.md`
- Test: `tests/evals/test_run.py`

**Interfaces:**
- Consumes: Task 3's `uses_opencode`, `model_id`, `MODELS`, `opencode_env`, `run_opencode`; `agent.is_claude`, `agent.CLAUDE_MODELS`.
- Produces: `--model` takes the names of the Global Constraints, anything else returns 2 with the names it takes; `preflight(plugin, env, scratch, model: str | None) -> str | None` (`model` is None for `--self-check`); the default run directory `runs/<time>-<model with every character but letters, digits, _ . - as ->`; `make eval MODEL=...` and `make eval-full MODEL=...`; the report's line of a run whose agent stopped early ends with `; its last step ended with <reason>`.

- [ ] **Step 1: Write the failing tests**

````bash
git apply <<'EOF'
diff --git a/tests/evals/test_run.py b/tests/evals/test_run.py
index a81a518..1208606 100644
--- a/tests/evals/test_run.py
+++ b/tests/evals/test_run.py
@@ -117,7 +117,7 @@ def fake(monkeypatch, seen, tmp_path_factory):
         return Judgement(checks=checks, model="claude-opus-5", cost_usd=0.05, usage={})
 
     monkeypatch.setattr(run, "ENVIRONMENTS", tmp_path_factory.mktemp("envs"))
-    monkeypatch.setattr(run, "preflight", lambda plugin, env, scratch: None)
+    monkeypatch.setattr(run, "preflight", lambda plugin, env, scratch, model: None)
     monkeypatch.setattr(run, "run_agent", agent)
     monkeypatch.setattr(run, "judge", judge)
     monkeypatch.setattr(run, "_commit", lambda: "abc123")
@@ -187,7 +187,7 @@ def test_the_agent_works_outside_the_repository_on_a_copy_of_the_plugin(
 
 def test_a_failed_preflight_spends_nothing(fake, monkeypatch, tmp_path, capsys):
     monkeypatch.setattr(
-        run, "preflight", lambda plugin, env, scratch: "claude is not on PATH"
+        run, "preflight", lambda plugin, env, scratch, model: "claude is not on PATH"
     )
     assert run.main(["--cases", "side-table", "--out", str(tmp_path / "out")]) == 2
     assert "claude is not on PATH" in capsys.readouterr().err
@@ -203,13 +203,63 @@ def test_the_preflight_names_what_does_not_work(tmp_path):
     tools = tmp_path / "tools"
     tools.mkdir()
     env = {"PATH": f"{plugin / 'bin'}:{tools}"}
-    assert "claude is not on PATH" in run.preflight(plugin, env, tmp_path)
+    assert "claude is not on PATH" in run.preflight(plugin, env, tmp_path, "sonnet")
     (tools / "claude").write_text("#!/bin/sh\n")
     (tools / "claude").chmod(0o755)
-    wrong = run.preflight(plugin, env, tmp_path)
+    wrong = run.preflight(plugin, env, tmp_path, "sonnet")
     assert "could not validate" in wrong and "build123d is required" in wrong
 
 
+def _tool(directory: Path, name: str, script: str) -> None:
+    (directory / name).write_text("#!/bin/sh\n" + script)
+    (directory / name).chmod(0o755)
+
+
+def test_the_preflight_checks_opencode_and_its_model(tmp_path):
+    plugin = tmp_path / "plugin"
+    (plugin / "bin").mkdir(parents=True)
+    _tool(plugin / "bin", "nichiyou-daiku", "exit 0\n")
+    tools = tmp_path / "tools"
+    tools.mkdir()
+    _tool(tools, "claude", "")
+    env = {"PATH": f"{plugin / 'bin'}:{tools}"}
+    assert "opencode is not on PATH" in run.preflight(plugin, env, tmp_path, "deepseek")
+    # opencode models lists what it serves now, from its own settings
+    _tool(
+        tools,
+        "opencode",
+        f'echo "$XDG_CONFIG_HOME" > "{tmp_path}/config_home"\n'
+        "echo opencode/glm-5.3-flash-free\n",
+    )
+    wrong = run.preflight(plugin, env, tmp_path, "deepseek")
+    assert "opencode does not offer opencode/deepseek-v4.1-flash-free" in wrong
+    assert run.preflight(plugin, env, tmp_path, "glm") is None
+    assert (tmp_path / "config_home").read_text().strip() == str(
+        tmp_path / "opencode" / "config"
+    )
+    # A Claude model does not need opencode
+    assert run.preflight(plugin, env, tmp_path, "sonnet") is None
+
+
+def test_the_preflight_asks_opencode_again_once_its_cache_is_filled(tmp_path):
+    # On an empty cache opencode lists the catalog it ships with, and fetches
+    # the current one for the next call
+    plugin = tmp_path / "plugin"
+    (plugin / "bin").mkdir(parents=True)
+    _tool(plugin / "bin", "nichiyou-daiku", "exit 0\n")
+    tools = tmp_path / "tools"
+    tools.mkdir()
+    _tool(tools, "claude", "")
+    _tool(
+        tools,
+        "opencode",
+        f'if [ -e "{tmp_path}/filled" ]; then echo opencode/glm-5.3-flash-free; '
+        f'else : > "{tmp_path}/filled"; echo opencode/old-free; fi\n',
+    )
+    env = {"PATH": f"{plugin / 'bin'}:{tools}"}
+    assert run.preflight(plugin, env, tmp_path, "glm") is None
+
+
 def test_the_plugin_is_copied_without_git_too(tmp_path):
     # A copy of the repository without .git, as CI tests it
     repo = tmp_path / "repo"
@@ -241,7 +291,7 @@ def test_the_self_check_judges_outside_the_repository(monkeypatch, tmp_path):
 
     monkeypatch.setattr(run, "self_check", self_check)
     monkeypatch.setattr(run, "ENVIRONMENTS", tmp_path / "envs")
-    monkeypatch.setattr(run, "preflight", lambda plugin, env, scratch: None)
+    monkeypatch.setattr(run, "preflight", lambda plugin, env, scratch, model: None)
     checkout = tmp_path / "checkout"
     subprocess.run(["git", "init", "-q", str(checkout)], check=True)
     assert run.main(["--self-check", "--out", str(checkout / "check")]) == 0
@@ -335,6 +385,20 @@ def test_a_run_of_changed_code_keeps_the_changes(fake, monkeypatch, tmp_path):
     assert "- Commit: abc123-dirty (the changes are in commit.diff)" in report
 
 
+def test_the_report_says_why_an_agent_stopped_early():
+    row = {
+        "case": "bench",
+        "rep": 1,
+        "design": None,
+        "checks": {name: {"passed": False, "detail": ""} for name in CHECKS},
+        "judge": None,
+        "judge_cost_usd": 0.0,
+        **TRANSCRIPT.model_copy(update={"ended": "length"}).model_dump(),
+    }
+    report = report_markdown({"cases": ["bench"], "reps": 1}, [row], [])
+    assert "; its last step ended with length" in report
+
+
 def test_a_bar_in_a_reason_keeps_the_table(tmp_path):
     row = {
         "case": "bench",
@@ -496,6 +560,43 @@ def test_rows_from_before_a_check_existed_are_not_counted_for_it():
     assert counts[f"judge: {list(CRITERIA)[-1]}"] == (0, 0)
 
 
+def test_an_unknown_model_stops_before_anything_runs(fake, tmp_path, capsys):
+    assert run.main(["--model", "gpt-9", "--out", str(tmp_path)]) == 2
+    said = capsys.readouterr().err
+    assert "Unknown model gpt-9" in said and "deepseek" in said
+    assert fake == []
+
+
+def test_a_model_opencode_serves_runs_through_opencode(fake, monkeypatch, tmp_path):
+    asked = []
+
+    def opencode(request, model, plugin, env, workdir, timeout_s):
+        asked.append(model)
+        shutil.copy(EXAMPLE, workdir / "design.nd")
+        return TRANSCRIPT
+
+    monkeypatch.setattr(run, "run_opencode", opencode)
+    run.main(["--cases", "side-table", "--model", "glm", "--out", str(tmp_path)])
+    assert (asked, fake) == (["glm"], [])
+    assert [row["case"] for row in load_jsonl(tmp_path / "results.jsonl")] == [
+        "side-table"
+    ]
+
+
+def test_each_model_gets_its_own_run_directory(fake, monkeypatch, tmp_path):
+    # Runs of two models started in the same second must not mix
+    monkeypatch.setattr(run, "RUNS", tmp_path)
+    monkeypatch.setattr(run, "run_opencode", lambda *args: TRANSCRIPT)
+    run.main(["--cases", "side-table"])
+    run.main(["--cases", "side-table", "--model", "opencode/glm-5.3-flash-free"])
+    names = sorted(path.name for path in tmp_path.iterdir())
+    assert len(names) == 2
+    assert names[0].endswith("-opencode-glm-5.3-flash-free") or names[1].endswith(
+        "-opencode-glm-5.3-flash-free"
+    )
+    assert any(name.endswith("-sonnet") for name in names)
+
+
 def test_an_unknown_case_stops_before_anything_runs(fake, tmp_path, capsys):
     assert run.main(["--cases", "nope", "--out", str(tmp_path)]) == 2
     assert "Unknown case nope" in capsys.readouterr().err
EOF
````

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/evals/test_run.py -q`
Expected: 27 failed, 7 passed (the stubbed `preflight` takes the model now: `TypeError`, and the new tests' assertions)

- [ ] **Step 3: Implement**

On an empty cache opencode's first `opencode models` lists the catalog it ships with (no DeepSeek or GLM) and fetches the current one for the next call, and a run started on it does not find its skill: the preflight asks twice, and fills the cache the runs share.

````bash
git apply <<'EOF'
diff --git a/Makefile b/Makefile
index 0addbb5..72316ff 100644
--- a/Makefile
+++ b/Makefile
@@ -17,11 +17,15 @@ lint:  ## Run linting checks
 format:  ## Format code with black
 	uv run ruff format src/ tests/ evals/
 
-eval:  ## Check the design skill on the 5 core requests once, ~15 min (uses your Claude allowance)
-	uv run python -m evals.design.run --cases core --reps 1
+# The LLM that designs: sonnet, opus or haiku through Claude Code, deepseek or
+# glm (free) or an opencode/... name through opencode
+MODEL ?= sonnet
 
-eval-full:  ## Measure the design skill on all 10 requests 3 times, before merging skill changes (uses your Claude allowance)
-	uv run python -m evals.design.run --cases all --reps 3
+eval:  ## Check the design skill on the 5 core requests once, ~15 min (MODEL=sonnet; uses your Claude allowance)
+	uv run python -m evals.design.run --cases core --reps 1 --model $(MODEL)
+
+eval-full:  ## Measure the design skill on all 10 requests 3 times, before merging skill changes (MODEL=sonnet; uses your Claude allowance)
+	uv run python -m evals.design.run --cases all --reps 3 --model $(MODEL)
 
 ci-setup:  ## Install CI dependencies for local CI runs
 	uv sync --group ci --group dev --all-extras
diff --git a/evals/design/README.md b/evals/design/README.md
index 4e99d0e..9ea0082 100644
--- a/evals/design/README.md
+++ b/evals/design/README.md
@@ -7,6 +7,7 @@ Each run uses your Claude Code login and allowance: the agent designs for 1 to 3
 ```bash
 make eval        # the 5 core requests once (sonnet designs, opus judges)
 make eval-full   # all 10 requests 3 times
+make eval-full MODEL=deepseek   # the same with another LLM (below)
 uv run python -m evals.design.run --cases plant-stand,desk --reps 2 --model opus
 uv run python -m evals.design.run --resume evals/design/runs/<time>   # continue after a stop, as it started
 uv run python -m evals.design.run --compare evals/design/runs/<earlier>   # its pass rates on the cases both have, and the change
@@ -18,5 +19,6 @@ uv run python -m evals.design.run --self-check   # check the judge on known desi
 - Before any run, a preflight checks `claude` and has the plugin's CLI validate and draw the skill's example (about 10 seconds), so a broken setup stops before it spends allowance.
 - Machine checks (`checks.py`) read the design with nichiyou-daiku. The judge (`judge.py`) is a second `claude -p` that looks at the rendered picture (drawn in the run's `judge/` directory from a copy named `design.nd`, since the picture shows the file name) and answers three questions with a JSON schema.
 - Runs at the same time share `/tmp`, where agents like to keep scratch files (`/tmp/validate_out.json`), so one may read another's. Runs go rep by rep, so the same request's runs do not run together, and the report counts the runs that used `/tmp` outside their own directory; use `--jobs 1` when that count is not 0 and the numbers matter.
+- `--model` (`MODEL=` for make) picks the LLM that designs. `sonnet`, `opus`, `haiku` and `claude-...` names run with `claude -p`. `deepseek` and `glm` (opencode's free `opencode/deepseek-v4.1-flash-free` and `opencode/glm-5.3-flash-free`) and `opencode/...` or `opencode-go/...` names run with `opencode run`: the same skill, the same refused commands, with opencode's settings and records in a temporary directory and without the skills and CLAUDE.md under `~/.claude`. A free model's run uses no Claude allowance but the judge's (opus, about 0.1 USD a run); its endpoint is sometimes unavailable, which ends the attempt for `--resume` to retry. Each model's run directory carries its name, so runs of several models can go at the same time.
 - Ctrl-C (or SIGTERM) ends the running `claude` sessions, starts no more and writes the report; `--resume` continues.
 - `results.jsonl` holds one row per graded design, `errors.jsonl` the attempts that gave no result (timeouts, errors, usage limits); `--resume` retries those and keeps what the earlier attempt left in `<case>-<rep>.attempt-<n>/`. When only the judge failed, the run keeps its machine checks in `unjudged.json` and `--resume` judges it again without running the agent. `report.md` shows what ran (models, the agent's tool and its version, where Claude Code took its credentials from, the commit and, for uncommitted changes, `commit.diff`), the pass rates with their 95% intervals, a line per case, the time, usage and tokens, and each design's picture.
diff --git a/evals/design/report.py b/evals/design/report.py
index 63e4d42..c2a8c08 100644
--- a/evals/design/report.py
+++ b/evals/design/report.py
@@ -243,7 +243,10 @@ def report_markdown(
             f"- Design: {row.get('design') or 'none'}{_chosen(row)}; {row['duration_s'] / 60:.1f} min, {row['turns']} turns, "
             f"{row['cost_usd']:.2f} USD; skill {'used' if row['skill_used'] else 'NOT used'}, "
             f"validate ×{row['validates']}, render ×{row['renders']}, images read ×{row['images_read']}, "
-            f"refused ×{row['denials']}, shared /tmp ×{row.get('shared_tmp', 0)}",
+            f"refused ×{row['denials']}, shared /tmp ×{row.get('shared_tmp', 0)}"
+            + (
+                f"; its last step ended with {row['ended']}" if row.get("ended") else ""
+            ),
             "",
             "| Check | | Detail |",
             "|---|---|---|",
diff --git a/evals/design/run.py b/evals/design/run.py
index 1bde8f0..c6c1909 100644
--- a/evals/design/run.py
+++ b/evals/design/run.py
@@ -6,6 +6,7 @@ uv run python -m evals.design.run --cases core --reps 1
 import argparse
 import json
 import os
+import re
 import shutil
 import signal
 import subprocess
@@ -18,10 +19,19 @@ from contextlib import contextmanager
 from datetime import datetime
 from pathlib import Path
 
-from .agent import STOP, AgentFailed, agent_env, run_agent, stop_all
+from .agent import (
+    CLAUDE_MODELS,
+    STOP,
+    AgentFailed,
+    agent_env,
+    is_claude,
+    run_agent,
+    stop_all,
+)
 from .cases import Case, load_cases
 from .checks import assembles, check_design, find_design
 from .judge import judge, self_check
+from .opencode import MODELS, model_id, opencode_env, run_opencode, uses_opencode
 from .report import load_jsonl, report_markdown
 
 REPO = Path(__file__).resolve().parents[2]
@@ -186,7 +196,8 @@ def run_one(
     with outside_repo(keep) as workdir:
         if row is None:
             try:
-                transcript = run_agent(
+                design_with = run_opencode if uses_opencode(args.model) else run_agent
+                transcript = design_with(
                     case.request, args.model, plugin, env, workdir, timeout_s
                 )
             except AgentFailed as e:
@@ -281,20 +292,25 @@ def _conditions(args: argparse.Namespace) -> str | None:
         for name, default in CONDITIONS.items():
             if getattr(args, name) is None:
                 setattr(args, name, default)
-        return None
-    meta_path = args.resume / "meta.json"
-    if not meta_path.exists():
-        return f"{args.resume} has no meta.json; give --resume a directory an earlier run wrote"
-    given = [name for name in CONDITIONS if getattr(args, name) is not None]
-    if given:
+    else:
+        meta_path = args.resume / "meta.json"
+        if not meta_path.exists():
+            return f"{args.resume} has no meta.json; give --resume a directory an earlier run wrote"
+        if any(getattr(args, name) is not None for name in CONDITIONS):
+            return (
+                f"--resume continues {args.resume} with its own cases, repetitions and "
+                "models; leave out --cases, --reps, --model and --judge-model"
+            )
+        meta = json.loads(meta_path.read_text(encoding="utf-8"))
+        args.cases = ",".join(meta["cases"])
+        for name in ("reps", "model", "judge_model"):
+            setattr(args, name, meta[name])
+    if not (is_claude(args.model) or uses_opencode(args.model)):
         return (
-            f"--resume continues {args.resume} with its own cases, repetitions and "
-            "models; leave out --cases, --reps, --model and --judge-model"
+            f"Unknown model {args.model}; use {', '.join(CLAUDE_MODELS)} or a "
+            f"claude-... name for Claude Code, or {', '.join(MODELS)} or an "
+            "opencode/... or opencode-go/... name for opencode"
         )
-    meta = json.loads(meta_path.read_text(encoding="utf-8"))
-    args.cases = ",".join(meta["cases"])
-    for name in ("reps", "model", "judge_model"):
-        setattr(args, name, meta[name])
     return None
 
 
@@ -308,10 +324,13 @@ def _uv_cache() -> str:
     return found.stdout.strip()
 
 
-def preflight(plugin: Path, env: dict[str, str], scratch: Path) -> str | None:
+def preflight(
+    plugin: Path, env: dict[str, str], scratch: Path, model: str | None
+) -> str | None:
     """What would make every run fail, found before any allowance is spent:
-    claude, and the plugin's CLI validating and drawing the skill's example
-    (which builds its environments once for all the runs)."""
+    claude (the judge's), the plugin's CLI validating and drawing the skill's
+    example (which builds its environments once for all the runs), and for
+    an opencode ``model``, opencode serving it."""
     if shutil.which("claude", path=env["PATH"]) is None:
         return "claude is not on PATH; install Claude Code to run the evaluation"
     example = plugin / "skills" / "design" / "examples" / "side-table.nd"
@@ -329,7 +348,30 @@ def preflight(plugin: Path, env: dict[str, str], scratch: Path) -> str | None:
                 f"the plugin's CLI could not {command[0]} the skill's example "
                 f"({said}); check that bin/nichiyou-daiku runs with uv"
             )
-    return None
+    if model is None or not uses_opencode(model):
+        return None
+    if shutil.which("opencode", path=env["PATH"]) is None:
+        return "opencode is not on PATH; install it (https://opencode.ai) to run this model"
+    # This also fills opencode's cache, which the runs share: on an empty
+    # one, opencode lists the catalog it ships with and fetches the current
+    # one for the next call, and the first run starts before its skills are
+    # found
+    settings = opencode_env(env, scratch / "opencode")
+    listed = subprocess.run(
+        ["opencode", "models"], env=settings, capture_output=True, text=True
+    )
+    if model_id(model) not in listed.stdout.split():
+        listed = subprocess.run(
+            ["opencode", "models"], env=settings, capture_output=True, text=True
+        )
+    if model_id(model) in listed.stdout.split():
+        return None
+    said = (listed.stderr.strip().splitlines() or [""])[-1]
+    return (
+        f"opencode does not offer {model_id(model)} now"
+        + (f" ({said})" if said else "")
+        + "; pick a model from opencode models"
+    )
 
 
 def main(argv: list[str] | None = None) -> int:
@@ -351,7 +393,9 @@ def main(argv: list[str] | None = None) -> int:
     ):
         plugin = plugin_copy(REPO, Path(tmp) / "plugin")
         env = agent_env(plugin, Path(cache), _uv_cache(), REPO / ".venv")
-        if wrong := preflight(plugin, env, Path(tmp)):
+        if wrong := preflight(
+            plugin, env, Path(tmp), None if args.self_check else args.model
+        ):
             print(wrong, file=sys.stderr)
             return 2
         if args.self_check:
@@ -377,7 +421,9 @@ def _self_check(args: argparse.Namespace, plugin: Path, env: dict[str, str]) ->
 def _evaluate(
     args: argparse.Namespace, cases: list[Case], plugin: Path, env: dict[str, str]
 ) -> int:
-    out = args.resume or args.out or RUNS / f"{datetime.now():%Y%m%d-%H%M%S}"
+    # The model in the name: two started in the same second do not mix
+    named = f"{datetime.now():%Y%m%d-%H%M%S}-{re.sub(r'[^\w.-]+', '-', args.model)}"
+    out = args.resume or args.out or RUNS / named
     out.mkdir(parents=True, exist_ok=True)
     meta_path = out / "meta.json"
     if not meta_path.exists():
EOF
````

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/evals -q`
Expected: 90 passed

- [ ] **Step 5: Check with the real CLIs**

The self-check makes four short opus calls; each trial is one free-model design (10 to 30 minutes) and one opus judgement.

```bash
uv run python -m evals.design.run --self-check
uv run python -m evals.design.run --cases plant-stand --model deepseek
uv run python -m evals.design.run --cases plant-stand --model glm
git status --short
```

Expected: `The judge passes the example and fails the broken designs`; for each model `Graded 1 runs, 0 failed attempts: evals/design/runs/<time>-<model>/report.md`, a report whose Agent line reads `on opencode 1.18.30`, with the skill used, and either the design in `plant-stand-1/` or, for a run with no design, the reason its agent stopped (as `its last step ended with length`); `git status --short` prints nothing (the agents wrote nothing into the repository). Whether a free model's design passes is what the evaluation measures, not a condition of this step. A free endpoint's 503 shows as a failed attempt instead: run the same command with `--resume evals/design/runs/<time>-<model>` in place of `--cases` and `--model`.

- [ ] **Step 6: Commit**

```bash
make check > /tmp/ndk-check.log 2>&1; rc=$?; tail -3 /tmp/ndk-check.log
[ $rc -eq 0 ] && git add evals tests/evals Makefile && git commit -m "feat: Choose the LLM that designs in the evaluation

make eval MODEL=deepseek (or glm, or an opencode/... name) designs with
opencode, MODEL=sonnet (the default), opus or haiku with Claude Code.
The preflight checks opencode and the model, each model's run
directory carries its name so that runs can go at the same time, and
the report says why an agent stopped early."
```
