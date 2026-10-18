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
    nor is a judge criterion of a run the judge could not grade, nor what
    a row from before the check existed lacks."""
    counts = {ALL_CHECKS: (sum(all_passed(row) for row in rows), len(rows))}
    for name in CHECKS:
        asked = [
            check["passed"]
            for row in rows
            if (check := row["checks"].get(name)) and check["passed"] is not None
        ]
        counts[name] = (sum(asked), len(asked))
    for name in CRITERIA:
        judged = [
            verdict["passed"]
            for row in rows
            if (verdict := (row.get("judge") or {}).get(name))
        ]
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


def _chosen(row: dict) -> str:
    found = row.get("designs", 1)
    return f" (chosen of {found} .nd files)" if found > 1 else ""


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _values(rows: list[dict], key: str) -> str:
    return ", ".join(sorted({str(row.get(key)) for row in rows})) or "-"


def _case_line(case: str, rows: list[dict]) -> str:
    runs = [row for row in rows if row["case"] == case]
    if not runs:
        return f"| {case} | 0 | - | - | - | - |"
    judged = [row for row in runs if row.get("judge")]
    judge_passed = sum(
        all(verdict["passed"] for verdict in row["judge"].values()) for row in judged
    )
    judge = f"{judge_passed}/{len(judged)}" if judged else "-"
    minutes = median(row["duration_s"] / 60 for row in runs)
    usage = median(row["cost_usd"] for row in runs)
    return (
        f"| {case} | {len(runs)} | {sum(all_passed(row) for row in runs)}/{len(runs)} "
        f"| {judge} | {minutes:.1f} min | {usage:.2f} USD |"
    )


def _mark(passed: bool | None) -> str:
    return {True: "✓", False: "✗", None: "–"}[passed]


def _change(now: tuple[int, int], before: tuple[int, int]) -> str:
    if not now[1] or not before[1]:
        return "-"
    points = round(100 * (now[0] / now[1] - before[0] / before[1]))
    return f"{points:+d} pt" if points else "±0 pt"


def report_markdown(
    meta: dict,
    rows: list[dict],
    errors: list[dict],
    previous: tuple[dict, list[dict]] | None = None,
) -> str:
    """The report: conditions, pass rates with their 95% intervals, the
    spend, the failed attempts, then each run with its picture. With
    ``previous`` (an earlier run's meta and rows), its pass rates on the
    cases both runs have stand beside."""
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
        f"- Commit: {meta.get('commit')}"
        + (f" (the changes are in {meta['diff']})" if meta.get("diff") else ""),
        f"- Agent: {_values(rows, 'model')} on Claude Code "
        f"{_values(rows, 'claude_code_version')}, API key: "
        f"{_values(rows, 'api_key_source')}; judge: "
        f"{_values([row for row in rows if row.get('judge')], 'judge_model')}",
        f"- Graded runs: {len(rows)}; failed attempts: {len(errors)} ({pending} not graded yet)",
        f"- Runs that used /tmp outside their own directory: "
        f"{sum(1 for row in rows if row.get('shared_tmp'))} of {len(rows)}",
    ]
    earlier = {}
    if previous is not None:
        before, before_rows = previous
        common = sorted(set(meta.get("cases", [])) & set(before.get("cases", [])))
        earlier = rates([row for row in before_rows if row["case"] in common])
        lines.append(
            f"- Compared with the run of {before.get('started', '?')} "
            f"({before.get('commit', '?')}), on the cases both ran: "
            + (", ".join(common) or "none")
        )
    lines += [
        "",
        "## Pass rates",
        "",
        "| Metric | Passed | Rate | 95% interval |"
        + (" Previous | Change |" if previous is not None else ""),
        "|---|---|---|---|" + ("---|---|" if previous is not None else ""),
    ]
    for name, (passed, total) in rates(rows).items():
        low, high = wilson(passed, total)
        line = f"| {name} | {passed}/{total} | {_percent(passed, total)} | {100 * low:.0f}–{100 * high:.0f}% |"
        if previous is not None:
            was = earlier.get(name, (0, 0))
            shown = f"{_percent(*was)} ({was[0]}/{was[1]})" if was[1] else "-"
            line += f" {shown} | {_change((passed, total), was)} |"
        lines.append(line)
    lines += [
        "",
        "## Cases",
        "",
        "| Case | Graded | All checks | Judge | Time | Usage |",
        "|---|---|---|---|---|---|",
        *(_case_line(case, rows) for case in meta.get("cases", [])),
    ]
    lines += [
        "",
        "## Spend per run (median, range)",
        "",
        "USD is what a run would cost at API prices; on a Claude plan it is "
        "the share of the allowance it used.",
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
            f"- Design: {row.get('design') or 'none'}{_chosen(row)}; {row['duration_s'] / 60:.1f} min, {row['turns']} turns, "
            f"{row['cost_usd']:.2f} USD; skill {'used' if row['skill_used'] else 'NOT used'}, "
            f"validate ×{row['validates']}, render ×{row['renders']}, images read ×{row['images_read']}, "
            f"refused ×{row['denials']}, shared /tmp ×{row.get('shared_tmp', 0)}",
            "",
            "| Check | | Detail |",
            "|---|---|---|",
        ]
        lines += [
            f"| {name} | {_mark(check['passed'])} | {_cell(check['detail'])} |"
            for name, check in row["checks"].items()
            if check["passed"] is not None
        ]
        for name, verdict in (row.get("judge") or {}).items():
            lines.append(
                f"| judge: {name} | {_mark(verdict['passed'])} | {_cell(verdict['detail'])} |"
            )
        if row.get("judge"):
            lines += ["", f"![{run}]({run}/judge/render.png)"]
        lines.append("")
    return "\n".join(lines)
