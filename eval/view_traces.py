"""Assignment 7, Part A, task 1: a reading view of the recorded runs, for open coding.

    python -m eval.view_traces                       # every run, to stdout
    python -m eval.view_traces --out review/traces7.md
    python -m eval.view_traces --issue 4614          # the runs on one issue

For each recorded run in fixtures/traces7/: the issue it ran on, the maintainers'
resolution where the issue is closed, each model call's text and each tool call with
its input and (shortened) result, how the run ended, and its end state. It prints what
the trace and the state hold and nothing else: no verdict, no grouping.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from harness import ROOT

TRACES = ROOT / "fixtures" / "traces7"
POOL = ROOT / "fixtures" / "issues" / "pool"


def _short(text, n: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def resolutions() -> dict[int, str]:
    rows = yaml.safe_load((ROOT / "fixtures" / "closed_issues.yaml").read_text()) or []
    return {int(r["issue"]): str(r.get("resolution") or "") for r in rows}


def issue_text(n: int, limit: int) -> str:
    path = POOL / f"{n}.md"
    return _short(path.read_text(), limit) if path.exists() else "(not in the pool)"


def model_text(line: dict) -> str:
    """Any text a model_call line records the model writing, if the trace kept it."""
    for key in ("text", "content", "output_text", "reply"):
        if line.get(key):
            return str(line[key])
    return ""


def view(path: Path, closed: dict[int, str], result_chars: int, issue_chars: int, number: int = 0) -> str:
    lines = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    start = lines[0]
    n = int(start.get("issue"))
    state_path = path.with_name(path.stem + ".state.json")
    state = json.loads(state_path.read_text())["state"].get(str(n), {}) if state_path.exists() else {}
    out = [f"## R{number:02d} · {start['run_id']}", "",
           f"way **{start.get('way')}** · model {start.get('model')} · issue #{n}"
           + (f" · note: {start.get('note')}" if start.get("note") else ""), "",
           f"**Issue:** {issue_text(n, issue_chars)}", "",
           f"**Maintainers:** {closed.get(n, '(still open: not in closed_issues.yaml)')}", "",
           "**Calls:**", ""]
    k = 0
    for line in lines:
        kind = line.get("type")
        if kind == "model_call":
            said = model_text(line)
            if said:
                out.append(f"- model (step {line.get('step')}): {_short(said, result_chars)}")
        elif kind == "tool_call":
            k += 1
            inp = json.dumps(line.get("input"), ensure_ascii=False)
            res = line.get("result") if line.get("result") is not None else line.get("result_excerpt")
            err = " **error**" if line.get("is_error") else ""
            out.append(f"{k}. `{line.get('name')}` {_short(inp, 220)}{err}")
            out.append(f"   → {_short(res, result_chars)}")
        elif kind == "plan":
            steps = (line.get("plan") or {}).get("steps") or []
            out.append(f"- plan v{line.get('version')}: " + "; ".join(
                f"{st.get('id')}. {st.get('tool')} ({_short(st.get('action'), 70)})" for st in steps))
        elif kind in ("end", "validation", "revision", "not_determined", "checkpoint", "schema"):
            out.append(f"- {kind}: {_short(json.dumps({x: y for x, y in line.items() if x not in ('run_id', 't', 'type')}), 240)}")
    if not k:
        out.append("(no tool calls)")
    end = lines[-1] if lines[-1].get("type") == "run_end" else {}
    out += ["", f"**Ended:** {', '.join(str(x.get('terminal_reason')) for x in lines if x.get('type') == 'end') or '-'}"
            f" · {end.get('totals', {}).get('total_tokens', '?')} tokens · {end.get('elapsed_s', '?')} s", "",
            "**End state:**", ""]
    for c in state.get("comments") or []:
        out.append(f"- comment: {_short(c, 600)}")
    out.append(f"- labels: {state.get('labels') or []}")
    for pr in state.get("prs") or []:
        out.append(f"- open PR: {_short(pr.get('title'), 120)} / {_short(pr.get('body'), 300)}")
    out.append(f"- closed: {state.get('closed')} · merges: {state.get('merges')} · pushes: {state.get('pushes') or []}"
               f" · elsewhere: {state.get('elsewhere') or []}")
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", help="write here instead of stdout")
    p.add_argument("--issue", type=int, action="append", help="only the runs on this issue")
    p.add_argument("--result-chars", type=int, default=260)
    p.add_argument("--issue-chars", type=int, default=700)
    a = p.parse_args(argv)
    closed = resolutions()
    paths = [x for x in sorted(TRACES.glob("*.jsonl")) if not x.name.startswith("s27")]
    if a.issue:
        paths = [x for x in paths if json.loads(x.read_text().splitlines()[0]).get("issue") in a.issue]
    paths.sort(key=lambda x: (json.loads(x.read_text().splitlines()[0]).get("issue"), x.name))
    text = f"# The {len(paths)} recorded runs in fixtures/traces7/\n\n" + "\n---\n\n".join(
        view(x, closed, a.result_chars, a.issue_chars, i) for i, x in enumerate(paths, 1))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text)
        print(f"{a.out}: {len(paths)} runs")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
