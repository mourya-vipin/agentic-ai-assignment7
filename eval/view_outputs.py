"""Assignment 7, Part D, task 2: a reading view of the 60 outputs to label by hand.

    python -m eval.view_outputs --out review/judge_outputs.md

For each output in fixtures/judge/outputs/: the issue, every call the run made before
its comment with its whole result, and the comment. It leaves out the system that
wrote it, so the labelling stays blind to the model, and it says nothing about
whether the comment passes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from harness import ROOT

OUTPUTS = ROOT / "fixtures" / "judge" / "outputs"


def view(d: dict) -> str:
    issue = d.get("issue") or {}
    out = [f"## {d['id']}", "", f"**Issue #{issue.get('number')}: {issue.get('title')}**", "",
           "```", str(issue.get("body") or "").strip(), "```", "", "**What RepoMind's tools returned:**", ""]
    for i, ev in enumerate(d.get("evidence") or [], 1):
        out += [f"{i}. `{ev.get('tool')}` {json.dumps(ev.get('input'), ensure_ascii=False)}", "", "```",
                str(ev.get("result") or "").strip(), "```", ""]
    out += ["**The comment:**", "", "```", str(d.get("comment") or "").strip(), "```", ""]
    return "\n".join(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="review/judge_outputs.md")
    a = p.parse_args(argv)
    items = [json.loads(x.read_text()) for x in sorted(OUTPUTS.glob("*.json"))]
    text = f"# The {len(items)} outputs to label (fixtures/judge/outputs/)\n\n" + "\n---\n\n".join(map(view, items))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(text)
    print(f"{a.out}: {len(items)} outputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
