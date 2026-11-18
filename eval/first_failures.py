"""Assignment 7, Part C, task 7: where each failed run of either arm first went wrong
(slide 29; checks/FORMATS.md, section 15.7).

    python -m eval.first_failures             # prints the grid, writes results/failures.json
    python -m eval.first_failures --show      # also each failed run's calls, with the first wrong one marked

For every run in results/A.jsonl and results/B.jsonl whose grounded check failed, its first
wrong call is the earliest call that is one of these, read from its trace:

1. A write the task's expected end state rules out: any push, close or merge; on a stop task,
   any comment, label or pull request; on any other task, a label other than the expected one,
   a comment beyond the first, a comment whose `label:` or `file:` line differs from the
   expected, or a pull request that does not name the expected file.
2. A call the tool rejected (`is_error`): its result never reached the run, so the step it
   stood for was not done.

`last_good` is the name of the call before it, or `start` when it was the run's first call.
When no call is wrong, the run ended before a call it needed (it ran out of turns, or its
plan had no such step): `first_wrong` is `stop` and `last_good` the run's last call. This is
the convention the Part A notes use for a run that hit the turn limit before its comment.
"""

from __future__ import annotations

import argparse
import json
import re

from harness import ROOT
from harness.tasks import load_tasks

FORBIDDEN = {"branches_push", "issues_close", "pulls_merge"}
STOP_WRITES = {"issues_comment", "issues_label", "pulls_open"}


def _line(body: str, key: str) -> str | None:
    m = re.search(rf"^\s*{key}\s*:\s*(.+?)\s*$", body or "", re.I | re.M)
    return m.group(1) if m else None


def why_wrong(call: dict, task, comments_before: int) -> str | None:
    """Why this call is wrong for the task, or None when it is not."""
    name, inp = call.get("name"), call.get("input") or {}
    exp = task.expect or {}
    if call.get("is_error"):
        return "rejected by the tool"
    if name in FORBIDDEN:
        return "a write the task rules out"
    if task.decision == "stop":
        return "a write on a task that should stop" if name in STOP_WRITES else None
    want = exp.get("comment") or {}
    if name == "issues_label" and str(inp.get("label")) not in set(exp.get("labels") or []):
        return f"label {inp.get('label')!r}, not {exp.get('labels')}"
    if name == "issues_comment":
        if comments_before:
            return "a second comment"
        body = str(inp.get("body") or "")
        if (_line(body, "label") or "").lower() != str(want.get("label")).lower():
            return f"comment label {_line(body, 'label')!r}, not {want.get('label')!r}"
        if (_line(body, "file") or "").lower() != str(want.get("file")).lower():
            return f"comment file {_line(body, 'file')!r}, not {want.get('file')!r}"
    if name == "pulls_open" and str(want.get("file") or "").lower() not in json.dumps(inp).lower():
        return f"a pull request that does not name {want.get('file')}"
    return None


def first_failure(lines: list[dict], task) -> dict:
    calls = [c for c in lines if c.get("type") == "tool_call"]
    comments = 0
    for i, c in enumerate(calls):
        why = why_wrong(c, task, comments)
        if why:
            return {"last_good": calls[i - 1]["name"] if i else "start", "first_wrong": c["name"],
                    "at": i + 1, "why": why}
        comments += c.get("name") == "issues_comment"
    return {"last_good": calls[-1]["name"] if calls else "start", "first_wrong": "stop",
            "at": len(calls) + 1, "why": "ended before a call it needed"}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tasks", default="eval/golden/v1/tasks")
    p.add_argument("--out", default="results/failures.json")
    p.add_argument("--show", action="store_true")
    a = p.parse_args(argv)
    tasks = {t.id: t for t in load_tasks(ROOT / a.tasks)}
    failures, grid = [], {"A": {}, "B": {}}
    for arm in "AB":
        for row in map(json.loads, open(ROOT / "results" / f"{arm}.jsonl")):
            if row["passed"]:
                continue
            lines = [json.loads(x) for x in open(ROOT / "runs" / f"{row['run_id']}.jsonl")]
            f = first_failure(lines, tasks[row["task"]])
            failures.append({"run_id": row["run_id"], "arm": arm, "last_good": f["last_good"],
                             "first_wrong": f["first_wrong"]})
            cell = grid[arm].setdefault(f["last_good"], {})
            cell[f["first_wrong"]] = cell.get(f["first_wrong"], 0) + 1
            if a.show:
                print(f"{arm} {row['run_id']} [{row['stratum']}] call {f['at']}: {f['last_good']} -> "
                      f"{f['first_wrong']} ({f['why']})")
    (ROOT / a.out).write_text(json.dumps({"failures": failures, "grid": grid}, indent=1) + "\n")
    for arm in "AB":
        n = sum(sum(v.values()) for v in grid[arm].values())
        print(f"\narm {arm}: {n} failed runs (last good down, first wrong across)")
        cols = sorted({c for v in grid[arm].values() for c in v})
        print(f"{'':16}" + "".join(f"{c:>16}" for c in cols))
        for r in sorted(grid[arm]):
            print(f"{r:16}" + "".join(f"{grid[arm][r].get(c, '') or '':>16}" for c in cols))
    print(f"\n{a.out}: {len(failures)} failures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
