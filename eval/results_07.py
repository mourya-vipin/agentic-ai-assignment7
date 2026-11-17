"""Assignment 7, Part B, task 1: one line per run, in results/<arm>.jsonl
(checks/FORMATS.md, section 15.4).

    python -m eval.results_07 --arm A --way planned --claim plan
    python -m eval.results_07 --arm B --way planned --switch TOOL_EXAMPLES=off --claim examples

Reads the arm's finished runs on your subset's golden tasks in runs/, checks each with your
grounded check, computes Part C's measure and the five metrics, and writes one line
per run. The helpers below find the runs and read them; the rest is yours.

A line (section 15.4):

    {"arm": "A", "way": "planned", "switches": {...}, "run_id": "...", "task": "g07",
     "stratum": "routine", "sweep": 1, "passed": true, "facts": {"present": 6, "total": 6},
     "measure": 0, "tokens": 31234, "cost_usd": 0.0412, "wall_clock_s": 18.2,
     "metrics": {"step_count": 2, "precision": 1.0, "recall": 1.0, "repeats": 0,
                 "orphans": 1, "no_tools": false, "cost_usd": 0.0412, "latency_s": 18.2}}

Part C's measure, per run, by claim (section 15.4): tokens, the run_end line's
totals.total_tokens; plan, the run's repeats; examples, its wasted calls: the lines of
its call record (runs/<run_id>.calls.jsonl) whose outcome is "rejected", "error" or
"protocol", plus the search calls whose result has "count": 0; checkpoint, its duplicate
writes: the comments beyond one, plus the open pull requests beyond one, on its issue
in its end state; split, 100 when the run passed and 0 when it did not.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import re

from eval.grounded import check
from eval.metrics import metrics
from harness import LAB, ROOT
from harness import switches as switch_board
from harness.formats import UNFINISHED
from harness.tasks import end_state, load_tasks, read_subset
from harness.trace import read_trace
from harness.tracker import Tracker

WASTED_OUTCOMES = ("rejected", "error", "protocol")
SEARCH_EMPTY = re.compile(r'"count":\s*0\b')
FLAGS = ("flaky_writes", "readback_fail")


def finished_runs(way: str, switches: dict | None = None, root: Path = ROOT,
                  scripted: bool = False) -> list[list[dict]]:
    """Every finished Assignment 7 run of `way` with these switches (unset ones at their
    defaults), on a real model, as its trace's lines: one list per run. A run is finished
    when its last line is run_end and it did not end quota or rate_limited. With
    scripted=True, the runs on a scripted model instead, to test your code for free."""
    want = {**switch_board.DEFAULTS, **(switches or {})}
    out = []
    for path in sorted((root / "runs").glob("*.jsonl")):
        if path.name.startswith("_") or path.name.count(".") > 1:
            continue
        lines = read_trace(path)
        start = lines[0] if lines else {}
        if start.get("type") != "run_start" or start.get("lab") != LAB or start.get("way") != way:
            continue
        if {**switch_board.DEFAULTS, **(start.get("switches") or {})} != want:
            continue
        free = str(start.get("backend", "")).startswith("harness.scripted:") or start.get("backend") == "never-stops"
        if free != scripted:
            continue
        ends = [r.get("terminal_reason") for r in lines if r.get("type") == "end"]
        if lines[-1].get("type") != "run_end" or set(ends) & set(UNFINISHED):
            continue
        out.append(lines)
    return out


def call_record(run_id: str, root: Path = ROOT) -> list[dict]:
    """A run's call record, runs/<run_id>.calls.jsonl, one dict per line."""
    path = root / "runs" / f"{run_id}.calls.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def parse_switches(pairs: list[str]) -> dict:
    """--switch NAME=VALUE pairs as the run_start line records them."""
    out = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"--switch {pair!r}: write NAME=VALUE")
        name, value = (x.strip() for x in pair.split("=", 1))
        name, value = name.lower(), value.lower()
        if name not in switch_board.DEFAULTS:
            raise SystemExit(f"--switch {name}: one of {sorted(switch_board.DEFAULTS)}")
        out[name] = value in ("1", "on", "true", "yes") if name in FLAGS else value
    return out


def wasted(run_id: str, root: Path = ROOT) -> int:
    """Claim 3's measure: refused, failed or toolless calls, plus searches that found nothing."""
    out = 0
    for line in call_record(run_id, root):
        if line.get("outcome") in WASTED_OUTCOMES:
            out += 1
        elif line.get("role") == "search" and SEARCH_EMPTY.search(str(line.get("result") or "")):
            out += 1
    return out


def measure(claim: str, lines: list[dict], task, state: dict, passed: bool, root: Path = ROOT):
    """Part C's measure for one run, by claim (section 15.4)."""
    end = lines[-1]
    if claim == "tokens":
        return int((end.get("totals") or {}).get("total_tokens") or 0)
    if claim == "plan":
        return metrics(lines, task)["repeats"]
    if claim == "examples":
        return wasted(lines[0]["run_id"], root)
    if claim == "checkpoint":
        mine = state.get(task.issues[0]) or {}
        return max(0, len(mine.get("comments", [])) - 1) + max(0, len(mine.get("prs", [])) - 1)
    if claim == "split":
        return 100 if passed else 0
    raise SystemExit(f"claim {claim!r}: not one of tokens, plan, examples, checkpoint, split")


def result_line(arm: str, lines: list[dict], task, claim: str, tracker: Tracker, root: Path = ROOT) -> dict:
    start, end = lines[0], lines[-1]
    run_id = start["run_id"]
    state = end_state(tracker, run_id, task)
    got = check(task, state)
    facts = got["facts"]
    totals = end.get("totals") or {}
    return {"arm": arm, "way": start.get("way"),
            "switches": {**switch_board.DEFAULTS, **(start.get("switches") or {})},
            "run_id": run_id, "task": task.id, "stratum": task.stratum, "sweep": start.get("sweep"),
            "passed": bool(got["passed"]),
            "facts": {"present": sum(1 for v in facts.values() if v == "present"), "total": len(facts)},
            "measure": measure(claim, lines, task, state, bool(got["passed"]), root),
            "tokens": int(totals.get("total_tokens") or 0),
            "cost_usd": float(totals.get("cost_usd") or 0.0),
            "wall_clock_s": float(end.get("elapsed_s") or 0.0),
            "metrics": metrics(lines, task)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--arm", required=True, choices=["A", "B"])
    p.add_argument("--way", required=True)
    p.add_argument("--switch", action="append", default=[], metavar="NAME=VALUE")
    p.add_argument("--claim", required=True, choices=["tokens", "plan", "examples", "checkpoint", "split"])
    p.add_argument("--tasks", default="eval/golden/v1/tasks")
    p.add_argument("--subset", default="eval/subsets/claim.txt", help="only these task IDs (Part C)")
    p.add_argument("--scripted", action="store_true",
                   help="the runs on a scripted model, to test this script for free: writes "
                        "results/scripted_<arm>.jsonl, which the checker never reads")
    a = p.parse_args(argv)
    tasks = {t.id: t for t in load_tasks(ROOT / a.tasks)}
    subset = set(read_subset(ROOT / a.subset)) if a.subset else set(tasks)
    missing = sorted(subset - set(tasks))
    if missing:
        raise SystemExit(f"{a.subset}: no golden task {', '.join(missing)} in {a.tasks}")
    tracker = Tracker(flaky=False, readback_fail=False)
    out = []
    for lines in finished_runs(a.way, parse_switches(a.switch), scripted=a.scripted):
        tid = lines[0].get("task")
        if tid in subset:
            out.append(result_line(a.arm, lines, tasks[tid], a.claim, tracker))
    out.sort(key=lambda r: (r["sweep"] or 0, r["task"], r["run_id"]))
    path = ROOT / "results" / (f"scripted_{a.arm}.jsonl" if a.scripted else f"{a.arm}.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in out))
    passed = sum(r["passed"] for r in out)
    mean = sum(r["measure"] for r in out) / len(out) if out else 0.0
    print(f"{path.relative_to(ROOT)}: {len(out)} runs, {passed} passed, mean measure {mean:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
