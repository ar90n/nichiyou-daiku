# Design skill evaluation

Runs the design skill (`skills/design/`) on a fixed set of furniture requests with `claude -p`, grades every design and writes a report, so that a change to the skill or the CLI can be checked against the last run. The decisions behind it are in `docs/superpowers/specs/2026-10-18-design-eval-design.md`.

Each run uses your Claude Code login and allowance: the agent designs for 5 to 30 minutes per request. Run it when a change could affect the designs, not on every commit.

```bash
make eval        # the 5 core requests once (sonnet designs, opus judges)
make eval-full   # all 10 requests 3 times
uv run python -m evals.design.run --cases plant-stand,desk --reps 2 --model opus
uv run python -m evals.design.run --resume evals/design/runs/<time>   # continue after a stop, as it started
uv run python -m evals.design.run --compare evals/design/runs/<earlier>
uv run python -m evals.design.run --self-check   # check the judge on known designs
```

- `cases/*.toml`: the requests and what a sound design must meet (size, lumber, legs, shelf heights, levels, fasteners). `core = true` marks the 5 of `make eval`.
- Every run works in a temporary directory outside the repository, copied to `runs/<time>/<case>-<rep>/` (not in git) when it ends, with `claude -p`, no MCP servers and no user settings or skills. The plugin is loaded from a copy of this repository without `evals/`, `.claude/` and `CLAUDE.md`: inside the repository Claude Code would load the developer's CLAUDE.md, settings and memory, and the agent could read the requirements and earlier designs. The repository's `.venv/bin` comes first on `PATH`, so the plugin runs today's CLI.
- Machine checks (`checks.py`) read the design with nichiyou-daiku. The judge (`judge.py`) is a second `claude -p` that looks at the rendered picture (drawn in the run's `judge/` directory from a copy named `design.nd`, since the picture shows the file name) and answers three questions with a JSON schema.
- Runs at the same time share `/tmp`, where agents like to keep scratch files (`/tmp/validate_out.json`), so one may read another's. Runs go rep by rep, so the same request's runs do not run together, and the report counts the runs that used `/tmp` outside their own directory; use `--jobs 1` when that count is not 0 and the numbers matter.
- Ctrl-C (or SIGTERM) ends the running `claude` sessions, starts no more and writes the report; `--resume` continues.
- `results.jsonl` holds one row per graded design, `errors.jsonl` the attempts that gave no result (timeouts, errors, usage limits); `--resume` retries those. When only the judge failed, the run keeps its machine checks in `unjudged.json` and `--resume` judges it again without running the agent. `report.md` shows the pass rates with their 95% intervals, the time and usage, and each design's picture.
