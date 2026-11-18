"""Assignment 7, Part D: the judge, its rates and its correction (checks/FORMATS.md,
section 15.10).

    python -m eval.judge test 1        # run 1 on the test set: eval/judge/verdicts/test_1.jsonl
    python -m eval.judge versions      # the test items' list and long versions: versions.jsonl
    python -m eval.judge recorded      # the agent way's recorded comments: recorded.jsonl
    python -m eval.judge tune --round 1  # examples + tuning sets only, to refine the prompt
    python -m eval.judge summary       # the numbers: eval/judge/summary.json, for_a_person.txt

Your judge reads one output, its issue and what RepoMind's tools returned, and
answers with slide 36's fixed reply: JSON with a one-line "reasoning", then an
"answer", "Pass" or "Fail". Every call goes through a metered judge session, so its
tokens and cost are recorded and priced, and count against lab_token_ceiling:

    from harness.meter import judge_session
    with judge_session("test-1") as session:
        response = session.client.create(system=prompt, messages=[{"role": "user", "content": text}])
        session.trace.model_call(0, response, purpose="judge")

Write session.id on every verdict line. To test the plumbing for nothing, pass
backend="harness.scripted:PassEverything", a judge that passes everything: a coin.

The checker calls `correct`, `rates` and `bootstrap` on cases of its own, and
`correct` on a coin, so keep their names, arguments and returns.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
from pathlib import Path

import yaml

from harness import ROOT
from harness.backends import DailyQuotaReached, RateLimited
from harness.meter import judge_session

OUTPUTS = ROOT / "fixtures" / "judge" / "outputs"
VERDICTS = ROOT / "eval" / "judge" / "verdicts"
PROMPT = ROOT / "prompts" / "judge.md"
LABELS = ROOT / "eval" / "labels" / "labels.csv"
SPLIT = ROOT / "eval" / "labels" / "split.yaml"
TRACES = ROOT / "fixtures" / "traces7"
POOL = ROOT / "fixtures" / "issues" / "pool"
COMMENT_WRITES = ("issues_comment", "post_comment")
RESAMPLES = 2000


class CoinJudge(ValueError):
    """TPR + TNR is within 0.1 of 1: the judge is no better than a coin. Fix it, do not
    correct it (slide 44)."""


def correct(p: float, tpr: float, tnr: float) -> float:
    """The share you would pass, labelling by hand, from the judge's pass rate p on
    outputs nobody labelled: (p + TNR - 1) / (TPR + TNR - 1) (slide 44), clipped to
    0 to 1. Raises CoinJudge when TPR + TNR is within 0.1 of 1."""
    youden = tpr + tnr - 1
    if abs(youden) <= 0.1:
        raise CoinJudge(f"TPR + TNR = {tpr + tnr:.3f}, within 0.1 of 1: the judge is no better than a coin; "
                        "fix it, do not correct it")
    return min(1.0, max(0.0, (p + tnr - 1) / youden))


def rates(verdicts: dict[str, str], labels: dict[str, str]) -> tuple[float, float]:
    """(TPR, TNR) of the judge's verdicts against your labels, each "pass" or "fail",
    on the items both cover (slide 43): TPR is the share of the labelled passes the
    judge passed, TNR the share of the labelled fails it failed."""
    passes = [i for i in labels if labels[i] == "pass" and i in verdicts]
    fails = [i for i in labels if labels[i] == "fail" and i in verdicts]
    tpr = sum(verdicts[i] == "pass" for i in passes) / len(passes) if passes else 0.0
    tnr = sum(verdicts[i] == "fail" for i in fails) / len(fails) if fails else 0.0
    return tpr, tnr


def bootstrap(verdicts: dict[str, str], labels: dict[str, str], p: float,
              resamples: int = 2000, seed: int = 0) -> tuple[float, float]:
    """The middle 95% of the corrected rate over resamples of the test items, drawn
    with replacement, as many as there are, each time recomputing TPR and TNR
    (slide 44). A resample on which the judge is a coin is left out."""
    items = [i for i in labels if i in verdicts]
    rng = random.Random(seed)
    got = []
    for _ in range(resamples):
        draw = [rng.choice(items) for _ in items]
        n_pass = sum(labels[i] == "pass" for i in draw)
        n_fail = len(draw) - n_pass
        if not n_pass or not n_fail:
            continue                      # TPR or TNR undefined on this resample
        tpr = sum(labels[i] == "pass" and verdicts[i] == "pass" for i in draw) / n_pass
        tnr = sum(labels[i] == "fail" and verdicts[i] == "fail" for i in draw) / n_fail
        try:
            got.append(correct(p, tpr, tnr))
        except CoinJudge:
            continue
    if not got:
        return (None, None)
    got.sort()
    return got[int(0.025 * (len(got) - 1))], got[int(0.975 * (len(got) - 1))]


def load_outputs(root: Path = ROOT) -> dict[str, dict]:
    """The 60 outputs to label, by ID (section 15.9)."""
    return {p.stem: json.loads(p.read_text()) for p in sorted((root / "fixtures" / "judge" / "outputs").glob("*.json"))}


def load_labels(path: Path = LABELS) -> dict[str, str]:
    with path.open(newline="") as fh:
        return {r["id"].strip(): r["label"].strip().lower() for r in csv.DictReader(fh)}


def load_split(path: Path = SPLIT) -> dict[str, list[str]]:
    data = yaml.safe_load(path.read_text()) or {}
    return {k: list(data.get(k) or []) for k in ("examples", "tuning", "test")}


# -- what the judge reads -------------------------------------------------------------------------

def _issue_from_pool(n: int) -> dict:
    """An issue as the outputs hold it: number, title, and the body below its front matter."""
    text = (POOL / f"{n}.md").read_text()
    title = ""
    if text.startswith("---"):
        front, _, text = text[3:].partition("\n---")
        meta = yaml.safe_load(front) or {}
        title = str(meta.get("title") or "")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()
    return {"number": n, "title": title, "body": text}


def recorded_items(root: Path = ROOT) -> dict[str, dict]:
    """Every recorded run of the agent way that posted a comment, as an output to judge:
    its issue, every call before its last comment with its result, and that comment."""
    out = {}
    for path in sorted((root / "fixtures" / "traces7").glob("*.jsonl")):
        if path.name.startswith("s27"):
            continue
        lines = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
        if not lines or lines[0].get("way") != "agent":
            continue
        calls = [x for x in lines if x.get("type") == "tool_call"]
        posts = [k for k, c in enumerate(calls) if c.get("name") in COMMENT_WRITES and not c.get("is_error")]
        if not posts:
            continue
        last = posts[-1]
        out[lines[0]["run_id"]] = {
            "id": lines[0]["run_id"], "issue": _issue_from_pool(int(lines[0]["issue"])),
            "evidence": [{"tool": c.get("name"), "input": c.get("input"), "result": c.get("result")}
                         for c in calls[:last]],
            "comment": str((calls[last].get("input") or {}).get("body") or "")}
    return out


FILE_HEADER = re.compile(r"^\S+ \([\d,]+ characters\)\s*$")


def numbered(ev: dict) -> str:
    """A tool result as the judge sees it. A file read gets its line numbers at the left,
    counted from the file's first line, the line after the read's header (the same count
    eval/find_evidence.py shows), so that a line number in a comment can be checked
    without counting by hand (the criterion's pass line 3, fail line 5)."""
    text = str(ev.get("result") or "").strip()
    lines = text.splitlines()
    if ev.get("tool") != "code_read_file" or not lines or not FILE_HEADER.match(lines[0]):
        return text
    return "\n".join([lines[0]] + [f"{n:4}| {line}" for n, line in enumerate(lines[1:], 1)])


def render(item: dict, comment: str | None = None) -> str:
    """The judge's user message: the issue, the calls and what they returned, the comment."""
    issue = item.get("issue") or {}
    parts = [f"# The issue: #{issue.get('number')} {issue.get('title')}", "", str(issue.get("body") or "").strip(),
             "", "# The tool calls the run made before the comment, in order, with what each returned", ""]
    for k, ev in enumerate(item.get("evidence") or [], 1):
        parts += [f"## Call {k}: {ev.get('tool')} {json.dumps(ev.get('input'), ensure_ascii=False)}", "",
                  numbered(ev), ""]
    if not item.get("evidence"):
        parts += ["(no tool calls)", ""]
    parts += ["# The comment", "", (comment if comment is not None else str(item.get("comment") or "")).strip(), "",
              "Judge the comment. Reply with the JSON line only."]
    return "\n".join(parts)


REPLY = re.compile(r"\{.*\}", re.S)
ANSWER = re.compile(r'"answer"\s*:\s*"(pass|fail)"', re.I)


def parse(text: str) -> tuple[str | None, str]:
    """(answer, reasoning) from the fixed reply; answer None when the reply has none."""
    m = REPLY.search(text or "")
    if m:
        try:
            data = json.loads(m.group(0))
            ans = str(data.get("answer") or "").strip().lower()
            if ans in ("pass", "fail"):
                return ans, " ".join(str(data.get("reasoning") or "").split())
        except (ValueError, AttributeError):
            pass
    m = ANSWER.search(text or "")
    return (m.group(1).lower(), " ".join((text or "").split())[:300]) if m else (None, (text or "")[:300])


def prompt_digest() -> str:
    return hashlib.sha256(PROMPT.read_bytes()).hexdigest()[:12]


def judge_all(name: str, jobs: list[tuple[str, str, dict]], out_path: Path, backend: str | None = None,
              extra=lambda key: {}) -> int:
    """Judge each (key, text, line) in jobs in one metered session, appending one verdict
    line each to out_path. Keys already in out_path are skipped, so a run the daily quota
    stopped picks up where it left off. Returns the number judged now."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            if line.strip():
                v = json.loads(line)
                done.add((v.get("id"), v.get("version")))
    todo = [j for j in jobs if (j[2]["id"], j[2].get("version")) not in done]
    if not todo:
        print(f"{out_path.relative_to(ROOT)}: nothing left to judge")
        return 0
    system = PROMPT.read_text()
    digest = prompt_digest()
    made = 0
    with judge_session(name, backend) as session:
        for key, text, line in todo:
            answer, reasoning = None, ""
            for _ in range(2):                      # one retry for a reply with no answer
                try:
                    response = session.client.create(system=system, messages=[{"role": "user", "content": text}])
                except (DailyQuotaReached, RateLimited) as exc:
                    print(f"stopped: {type(exc).__name__}: {exc}; run the same command again to finish")
                    return made
                session.trace.model_call(0, response, purpose="judge")
                answer, reasoning = parse(response.text)
                if answer:
                    break
            row = {**line, "answer": answer or "fail", "reasoning": reasoning or "no answer in the reply",
                   "session": session.id, "model": session.model, "prompt": digest}
            with out_path.open("a") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            made += 1
            print(f"  {key:32} {row['answer']:4}  {reasoning[:90]}")
    print(f"{out_path.relative_to(ROOT)}: {made} judged now")
    return made


def read_verdicts(name: str) -> list[dict]:
    path = VERDICTS / f"{name}.jsonl"
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []


# -- the numbers -------------------------------------------------------------------------------------

def summary() -> dict:
    """Section 15.8's judge block, from the verdict files and your labels."""
    labels, split, outputs = load_labels(), load_split(), load_outputs()
    test = split["test"]
    on_test = {i: labels[i] for i in test}
    runs = [{v["id"]: v["answer"] for v in read_verdicts(f"test_{k}")} for k in (1, 2, 3)]
    v1 = runs[0]
    tpr, tnr = rates(v1, on_test)
    recorded = read_verdicts("recorded")
    p = sum(v["answer"] == "pass" for v in recorded) / len(recorded) if recorded else None
    coin = abs(tpr + tnr - 1) <= 0.1
    corrected, interval, raw = None, [None, None], None
    if p is not None and not coin:
        corrected = correct(p, tpr, tnr)
        raw = (p + tnr - 1) / (tpr + tnr - 1)
        interval = list(bootstrap(v1, on_test, p, RESAMPLES, 0))
    have_all = all(sorted(r) == sorted(test) for r in runs)
    flips = [i for i in test if have_all and len({r[i] for r in runs}) > 1]
    maj = {i: "pass" if sum(r.get(i) == "pass" for r in runs) >= 2 else "fail" for i in test} if have_all else {}
    m_tpr, m_tnr = rates(maj, on_test) if maj else (None, None)
    versions = read_verdicts("versions")
    moved = sorted({v["id"] for v in versions if v["answer"] != v1.get(v["id"])})
    by_system = {}
    for s in sorted({o["system"] for o in outputs.values()}):
        mine = {i: on_test[i] for i in test if outputs[i]["system"] == s}
        st, sn = rates(v1, mine)
        by_system[s] = {"tpr": st, "tnr": sn, "items": len(mine),
                        "passes": sum(x == "pass" for x in mine.values()),
                        "fails": sum(x == "fail" for x in mine.values())}
    one = (tpr + tnr) / 2
    return {"split": {k: len(v) for k, v in split.items()},
            "model": (recorded or read_verdicts("test_1") or [{}])[0].get("model"),
            "tpr": tpr, "tnr": tnr, "p": p, "corrected": corrected, "raw_corrected": raw,
            "interval": interval, "coin": coin, "flip_rate": len(flips) / len(test) if have_all else None,
            "flips": flips,
            "majority": {"tpr": m_tpr, "tnr": m_tnr,
                         "kept": bool(maj) and (m_tpr + m_tnr) / 2 > one},
            "moved_share": len(moved) / len(test) if versions else None, "moved": moved,
            "by_system": by_system,
            "test_counts": {"passes": sum(x == "pass" for x in on_test.values()),
                            "fails": sum(x == "fail" for x in on_test.values())},
            "recorded": len(recorded), "prompt": prompt_digest()}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--backend", help="harness.scripted:PassEverything tests the plumbing for nothing")
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("test", help="run N on the test set: eval/judge/verdicts/test_N.jsonl")
    t.add_argument("n", type=int, choices=[1, 2, 3])
    sub.add_parser("versions", help="the test items' list and long versions: versions.jsonl")
    sub.add_parser("recorded", help="the agent way's recorded comments: recorded.jsonl")
    tu = sub.add_parser("tune", help="the examples and tuning sets, to refine the prompt: eval/judge/tuning/")
    tu.add_argument("--round", default="1")
    sub.add_parser("summary", help="the judge's numbers, from the verdict files: eval/judge/summary.json")
    a = p.parse_args(argv)
    outputs, split = load_outputs(), load_split()
    where = VERDICTS if not a.backend else ROOT / "eval" / "judge" / "scripted"
    if a.cmd == "test":
        jobs = [(i, render(outputs[i]), {"id": i}) for i in split["test"]]
        judge_all(f"test-{a.n}", jobs, where / f"test_{a.n}.jsonl", a.backend)
    elif a.cmd == "versions":
        jobs = [(f"{i}/{v}", render(outputs[i], outputs[i]["versions"][v]), {"id": i, "version": v})
                for i in split["test"] for v in ("list", "long")]
        judge_all("versions", jobs, where / "versions.jsonl", a.backend)
    elif a.cmd == "recorded":
        items = recorded_items()
        jobs = [(rid, render(item), {"id": rid}) for rid, item in items.items()]
        judge_all("recorded", jobs, where / "recorded.jsonl", a.backend)
    elif a.cmd == "tune":
        labels = load_labels()
        ids = split["examples"] + split["tuning"]
        path = ROOT / "eval" / "judge" / "tuning" / f"round_{a.round}.jsonl"
        judge_all(f"tune-{a.round}", [(i, render(outputs[i]), {"id": i}) for i in ids], path, a.backend)
        got = {json.loads(x)["id"]: json.loads(x)["answer"] for x in path.read_text().splitlines() if x.strip()}
        for name in ("examples", "tuning"):
            tpr, tnr = rates(got, {i: labels[i] for i in split[name]})
            print(f"  {name}: TPR {tpr:.3f}, TNR {tnr:.3f}")
        wrong = [i for i in ids if i in got and got[i] != labels[i]]
        print(f"  disagreements with your labels: {', '.join(wrong) or 'none'}")
    elif a.cmd == "summary":
        out = summary()
        (ROOT / "eval" / "judge" / "summary.json").write_text(json.dumps(out, indent=2) + "\n")
        (ROOT / "eval" / "judge" / "for_a_person.txt").write_text("".join(f"{i}\n" for i in out["flips"]))
        print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
