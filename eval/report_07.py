"""Assignment 7: reports/LAB_07.json, built from the files it summarizes (checks/FORMATS.md,
section 15.8), so that no number in it is typed by hand.

    python -m eval.report_07            # writes reports/LAB_07.json and prints the Part C tables

It reads the golden set (eval/golden/v1/), the bar (eval/thresholds/claim.yaml), both arms'
results (results/A.jsonl, results/B.jsonl), the first failures (results/failures.json, from
eval.first_failures) and the judge's numbers (eval/judge/summary.json, from eval.judge summary).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict

import yaml

from eval.stats import interval, over_tasks, spread
from harness import ROOT
from harness.tasks import load_tasks

STRATA = ("routine", "unusual", "adversarial", "should_not_act")


def sweep_values(rows: list[dict]) -> tuple[list[float], list[float]]:
    """Each sweep's value (the measure's mean over its runs) and score (100 x passes / tasks)."""
    by = defaultdict(list)
    for r in rows:
        by[r["sweep"]].append(r)
    values = [sum(r["measure"] for r in v) / len(v) for _, v in sorted(by.items())]
    scores = [100 * sum(r["passed"] for r in v) / len(v) for _, v in sorted(by.items())]
    return values, scores


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def passes(rows: list[dict], k: int) -> tuple[float, float]:
    counts = defaultdict(lambda: [0, 0])
    for r in rows:
        counts[r["task"]][0] += 1
        counts[r["task"]][1] += bool(r["passed"])
    return over_tasks({t: (n, c) for t, (n, c) in counts.items()}, k)


def arm_block(arm: dict, rows: list[dict], k: int) -> dict:
    values, scores = sweep_values(rows)
    at, hat = passes(rows, k)
    by_stratum = {}
    for s in STRATA:
        mine = [r for r in rows if r["stratum"] == s]
        if not mine:
            continue
        v, sc = sweep_values(mine)
        a, h = passes(mine, k)
        by_stratum[s] = {"runs": len(mine), "measure": round(mean(v), 4), "score": round(mean(sc), 4),
                         "pass_at_k": round(a, 4), "pass_hat_k": round(h, 4)}
    return {"way": arm["way"], "switches": arm.get("switches") or {}, "runs": len(rows),
            "measure": {"mean": round(mean(values), 4), "sd": round(spread(values), 4)},
            "score": {"mean": round(mean(scores), 4), "sd": round(spread(scores), 4)},
            "pass_at_k": round(at, 4), "pass_hat_k": round(hat, 4),
            "facts_share": round(sum(r["facts"]["present"] for r in rows) / sum(r["facts"]["total"] for r in rows), 4),
            "cost_per_run_usd": round(mean([r["cost_usd"] for r in rows]), 6),
            "no_tools": sum(bool(r["metrics"]["no_tools"]) for r in rows),
            "by_stratum": by_stratum}


def difference(claim: dict, a_rows: list[dict], b_rows: list[dict]) -> tuple[float, list[float]]:
    va, _ = sweep_values(a_rows)
    vb, _ = sweep_values(b_rows)
    first, second = (vb, va) if claim["gain"].replace(" ", "") == "B-A" else (va, vb)
    gain, lo, hi = interval(first, second)
    return round(gain, 4), [round(lo, 4), round(hi, 4)]


def verdict(claim: dict, iv: list[float], by_stratum: dict) -> str:
    if iv[0] > claim["bar"] and all(v["difference"] >= claim["group_floor"] for v in by_stratum.values()):
        return "holds"
    if iv[1] < claim["bar"]:
        return "fails"
    return "cannot_settle"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="reports/LAB_07.json")
    a = p.parse_args(argv)
    manifest = yaml.safe_load(open(ROOT / "eval/golden/v1/manifest.yaml"))
    tasks = [t for t in load_tasks(ROOT / "eval/golden/v1/tasks") if t.id in set(manifest["tasks"])]
    strata = Counter(t.stratum for t in tasks)
    golden = {"version": manifest["version"], "tasks": len(tasks),
              "strata": {s: strata.get(s, 0) for s in STRATA},
              "decisions": {d: sum(t.decision == d for t in tasks) for d in ("act", "refuse", "stop")},
              "thinnest": min(STRATA, key=lambda s: strata.get(s, 0))}

    claim = yaml.safe_load(open(ROOT / "eval/thresholds/claim.yaml"))
    rows = {arm: [json.loads(x) for x in open(ROOT / "results" / f"{arm}.jsonl")] for arm in "AB"}
    k = int(claim["k"])
    by_stratum = {}
    for s in STRATA:
        d, iv = difference(claim, [r for r in rows["A"] if r["stratum"] == s], [r for r in rows["B"] if r["stratum"] == s])
        by_stratum[s] = {"difference": d, "interval": iv}
    d, iv = difference(claim, rows["A"], rows["B"])
    claim_block = {key: claim[key] for key in ("claim", "measure", "gain", "k", "sweeps", "s_a", "s_b",
                                                "delta", "n_needed", "price_usd")}
    claim_block.update({"difference": d, "interval": iv, "by_stratum": by_stratum,
                        "verdict": verdict(claim, iv, by_stratum)})

    ff = json.load(open(ROOT / "results/failures.json"))
    judge_path = ROOT / "eval/judge/summary.json"
    j = json.load(open(judge_path)) if judge_path.exists() else {}
    keep = ("split", "model", "tpr", "tnr", "p", "corrected", "interval", "coin", "flip_rate", "majority",
            "moved_share", "by_system")
    judge = {key: j.get(key) for key in keep}
    if judge.get("by_system"):
        judge["by_system"] = {s: {"tpr": v["tpr"], "tnr": v["tnr"]} for s, v in judge["by_system"].items()}

    report = {"golden": golden, "claim": claim_block,
              "arms": {"A": arm_block(claim["arm_a"], rows["A"], k), "B": arm_block(claim["arm_b"], rows["B"], k)},
              "failures": ff["failures"], "grid": ff["grid"], "judge": judge}
    (ROOT / a.out).write_text(json.dumps(report, indent=2) + "\n")

    print(f"golden: {golden}")
    print(f"gain ({claim['gain']}): {d} {iv} -> {claim_block['verdict']}")
    for s, v in by_stratum.items():
        print(f"  {s:15} {v['difference']:+.3f} {v['interval']}")
    for arm in "AB":
        b = report["arms"][arm]
        print(f"arm {arm} {b['way']}: runs {b['runs']}, measure {b['measure']}, score {b['score']}, "
              f"pass@{k} {b['pass_at_k']}, pass^{k} {b['pass_hat_k']}, facts {b['facts_share']}, "
              f"cost/run ${b['cost_per_run_usd']}, no_tools {b['no_tools']}")
        for s, v in b["by_stratum"].items():
            print(f"    {s:15} {v}")
    print(f"{a.out} written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
