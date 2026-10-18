"""The Markdown report of an evaluation run."""

import json
import math
from pathlib import Path
from statistics import median

from .checks import CHECKS
from .judge import CRITERIA

ALL_CHECKS = "all checks"


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def wilson(passed: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """The 95% interval of a pass rate; (0, 1) when nothing was counted."""
    if total == 0:
        return 0.0, 1.0
    p = passed / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = (
        z
        * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
        / (1 + z * z / total)
    )
    return max(0.0, centre - half), min(1.0, centre + half)


def all_passed(row: dict) -> bool:
    """Whether every check the case asks for passed."""
    return all(
        check["passed"]
        for check in row["checks"].values()
        if check["passed"] is not None
    )


def rates(rows: list[dict]) -> dict[str, tuple[int, int]]:
    """(passed, counted) per metric: all checks first, then each check and
    each judge criterion. A check the case does not ask for is not counted,
    nor is a judge criterion of a run the judge could not grade."""
    counts = {ALL_CHECKS: (sum(all_passed(row) for row in rows), len(rows))}
    for name in CHECKS:
        asked = [
            row["checks"][name]["passed"]
            for row in rows
            if row["checks"][name]["passed"] is not None
        ]
        counts[name] = (sum(asked), len(asked))
    for name in CRITERIA:
        judged = [row["judge"][name]["passed"] for row in rows if row.get("judge")]
        counts[f"judge: {name}"] = (sum(judged), len(judged))
    return counts


def _percent(passed: int, total: int) -> str:
    return f"{100 * passed / total:.0f}%" if total else "-"


def _spread(values: list[float], unit: str) -> str:
    if not values:
        return "-"
    return f"{median(values):.1f} {unit} ({min(values):.1f} – {max(values):.1f})"


def _failed_usage(errors: list[dict]) -> str:
    known = [e["cost_usd"] for e in errors if e.get("cost_usd") is not None]
    line = f"- Failed attempts: {len(errors)}, {sum(known):.2f} USD"
    if unknown := len(errors) - len(known):
        line += f" and {unknown} without a usage record (timed out or stopped)"
    return line


def _total_usage(rows: list[dict], errors: list[dict]) -> float:
    graded = sum(row["cost_usd"] + row["judge_cost_usd"] for row in rows)
    return graded + sum(e.get("cost_usd") or 0.0 for e in errors)


def _mark(passed: bool | None) -> str:
    return {True: "✓", False: "✗", None: "–"}[passed]


def report_markdown(
    meta: dict, rows: list[dict], errors: list[dict], previous: list[dict] | None = None
) -> str:
    """The report: conditions, pass rates with their 95% intervals, the
    spend, the failed attempts, then each run with its picture."""
    graded = {(row["case"], row["rep"]) for row in rows}
    asked = {
        (case, rep)
        for case in meta.get("cases", [])
        for rep in range(1, meta.get("reps", 0) + 1)
    }
    pending = len(asked - graded)
    lines = [
        f"# Design skill evaluation {meta.get('started', '')}",
        "",
        f"- Cases: {', '.join(meta.get('cases', []))}",
        f"- Repetitions: {meta.get('reps')}; model: {meta.get('model')}; judge: {meta.get('judge_model')}",
        f"- Commit: {meta.get('commit')}",
        f"- Graded runs: {len(rows)}; failed attempts: {len(errors)} ({pending} not graded yet)",
        "",
        "## Pass rates",
        "",
        "| Metric | Passed | Rate | 95% interval |"
        + (" Previous |" if previous is not None else ""),
        "|---|---|---|---|" + ("---|" if previous is not None else ""),
    ]
    earlier = rates(previous) if previous is not None else {}
    for name, (passed, total) in rates(rows).items():
        low, high = wilson(passed, total)
        line = f"| {name} | {passed}/{total} | {_percent(passed, total)} | {100 * low:.0f}–{100 * high:.0f}% |"
        if previous is not None:
            line += f" {_percent(*earlier.get(name, (0, 0)))} |"
        lines.append(line)
    lines += [
        "",
        "## Spend per run (median, range)",
        "",
        f"- Time: {_spread([row['duration_s'] / 60 for row in rows], 'min')}",
        f"- Turns: {_spread([float(row['turns']) for row in rows], '')}",
        f"- Agent usage: {_spread([row['cost_usd'] for row in rows], 'USD')}",
        f"- Judge usage: {_spread([row['judge_cost_usd'] for row in rows if row.get('judge')], 'USD')}",
        _failed_usage(errors),
        f"- Total usage: {_total_usage(rows, errors):.2f} USD",
        "",
    ]
    if errors:
        lines += ["## Failed attempts", ""]
        lines += [
            f"- {error['case']}-{error['rep']}: {error['kind']}: {error['message']}"
            + (
                " (graded on a later attempt)"
                if (error["case"], error["rep"]) in graded
                else ""
            )
            for error in errors
        ]
        lines.append("")
    lines += ["## Runs", ""]
    for row in sorted(rows, key=lambda r: (r["case"], r["rep"])):
        run = f"{row['case']}-{row['rep']}"
        lines += [
            f"### {run}",
            "",
            f"- Design: {row.get('design') or 'none'}; {row['duration_s'] / 60:.1f} min, {row['turns']} turns, "
            f"{row['cost_usd']:.2f} USD; skill {'used' if row['skill_used'] else 'NOT used'}, "
            f"validate ×{row['validates']}, render ×{row['renders']}, images read ×{row['images_read']}, "
            f"refused ×{row['denials']}",
            "",
            "| Check | | Detail |",
            "|---|---|---|",
        ]
        lines += [
            f"| {name} | {_mark(check['passed'])} | {check['detail']} |"
            for name, check in row["checks"].items()
            if check["passed"] is not None
        ]
        for name, verdict in (row.get("judge") or {}).items():
            lines.append(
                f"| judge: {name} | {_mark(verdict['passed'])} | {verdict['detail']} |"
            )
        if row.get("judge"):
            lines += ["", f"![{run}]({run}/render.png)"]
        lines.append("")
    return "\n".join(lines)
