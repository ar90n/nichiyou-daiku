# Design skill evaluation

Runs the design skill (`skills/design/`) on a fixed set of furniture requests with `claude -p`, grades every design and writes a report, so that a change to the skill or the CLI can be checked against the last run. The decisions behind it are in `docs/superpowers/specs/2026-10-18-design-eval-design.md`.

Each run uses your Claude Code login and allowance: the agent designs for 1 to 30 minutes per request. Run `make eval-full` before merging work that changes the skill or the CLI it uses, and at the end of a milestone. `make eval` only checks that nothing is broken: in the baseline (2026-10-18, about 14 minutes and 4 USD at API prices) all 5 core requests passed every check, so it cannot show a design getting better or worse.

```bash
make eval        # the 5 core requests once (sonnet designs, opus judges)
make eval-full   # all 10 requests 3 times
make eval-full MODEL=deepseek   # the same with another LLM (below)
uv run python -m evals.design.run --cases plant-stand,desk --reps 2 --model opus
uv run python -m evals.design.run --resume evals/design/runs/<time>   # continue after a stop, as it started
uv run python -m evals.design.run --compare evals/design/runs/<earlier>   # its pass rates on the cases both have, and the change
uv run python -m evals.design.run --self-check   # check the judge on known designs
```

- `cases/*.toml`: the requests and what a sound design must meet (size, lumber, legs, shelf heights, levels, fasteners). `core = true` marks the 5 of `make eval`.
- Every run works in a temporary directory outside the repository, copied to `runs/<time>/<case>-<rep>/` (not in git) when it ends, with `claude -p`, no MCP servers and no user settings or skills. The plugin is loaded from a copy of this repository without `evals/`, `docs/superpowers/`, `tests/evals/`, `.claude/` and `CLAUDE.md`: inside the repository Claude Code would load the developer's CLAUDE.md, settings and memory, and the agent could read the requirements and earlier designs. The agent uses the plugin's own launcher, as a person who installed the plugin does: it builds the CLI from the copy (today's working tree, fixed for the whole evaluation) into an environment under `~/.cache/nichiyou-daiku-eval/`, removed afterwards; the developer's `.venv` is not on its `PATH`.
- Before any run, a preflight checks `claude` and has the plugin's CLI validate and draw the skill's example (about 10 seconds), so a broken setup stops before it spends allowance.
- Machine checks (`checks.py`) read the design with nichiyou-daiku. The judge (`judge.py`) is a second `claude -p` that looks at the rendered picture (drawn in the run's `judge/` directory from a copy named `design.nd`, since the picture shows the file name) and answers three questions with a JSON schema.
- Runs at the same time share `/tmp`, where agents like to keep scratch files (`/tmp/validate_out.json`), so one may read another's. Runs go rep by rep, so the same request's runs do not run together, and the report counts the runs that used `/tmp` outside their own directory; use `--jobs 1` when that count is not 0 and the numbers matter.
- `--model` (`MODEL=` for make) picks the LLM that designs. `sonnet`, `opus`, `haiku` and `claude-...` names run with `claude -p`. `deepseek` and `glm` (opencode's free `opencode/deepseek-v4.1-flash-free` and `opencode/glm-5.3-flash-free`) and `opencode/...` or `opencode-go/...` names run with `opencode run`: the same skill, the same refused commands, with opencode's settings, records, scratch space (`TMPDIR`) and locks in temporary directories, without the skills under `~/.claude` and `~/.agents` or the developer's `OPENCODE_*` settings, and without subagents, whose work the record would not show. A free model's run uses no Claude allowance but the judge's (opus, about 0.1 USD a run); its endpoint is sometimes unavailable, which ends the attempt for `--resume` to retry. Each model's run directory carries its name, so runs of several models can go at the same time.
- Ctrl-C (or SIGTERM) ends the running `claude` sessions, starts no more and writes the report; `--resume` continues.
- `results.jsonl` holds one row per graded design, `errors.jsonl` the attempts that gave no result (timeouts, errors, usage limits); `--resume` retries those and keeps what the earlier attempt left in `<case>-<rep>.attempt-<n>/`. When only the judge failed, the run keeps its machine checks in `unjudged.json` and `--resume` judges it again without running the agent. `report.md` shows what ran (models, the agent's tool and its version, where Claude Code took its credentials from, the commit and, for uncommitted changes, `commit.diff`), the pass rates with their 95% intervals, a line per case, the time, usage and tokens, and each design's picture.
