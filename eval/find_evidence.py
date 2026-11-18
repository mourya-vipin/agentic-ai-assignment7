"""Assignment 7, Part D: find where a word appears in one output's evidence, to check a
label's reason by hand. It searches; it never says whether an output passes.

    python -m eval.find_evidence j02                 # the calls the run made, and the files it read
    python -m eval.find_evidence j02 DAY_FIRST       # every line holding DAY_FIRST, in the issue,
                                                     #   each tool result, and the comment
    python -m eval.find_evidence j02 DAY_FIRST --context 2

A line number shown for a file read is the line's position in the text the read
returned, counted from the file's first line (the line after the read's header).
"""

from __future__ import annotations

import argparse
import json
import re

from harness import ROOT

OUTPUTS = ROOT / "fixtures" / "judge" / "outputs"
HEADER = re.compile(r"^\S+ \([\d,]+ characters\)\s*$")


def sources(d: dict) -> list[tuple[str, list[str], int]]:
    """(name, lines, number of the first line) for the issue, each tool result and the comment."""
    issue = d.get("issue") or {}
    out = [(f"issue #{issue.get('number')}", f"{issue.get('title')}\n{issue.get('body') or ''}".splitlines(), 1)]
    for i, ev in enumerate(d.get("evidence") or [], 1):
        lines = str(ev.get("result") or "").splitlines()
        first = 1
        if ev.get("tool") == "code_read_file" and lines and HEADER.match(lines[0]):
            lines, first = lines[1:], 1
        out.append((f"call {i} {ev.get('tool')} {json.dumps(ev.get('input'), ensure_ascii=False)}", lines, first))
    out.append(("the comment", str(d.get("comment") or "").splitlines(), 1))
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("id")
    p.add_argument("word", nargs="?")
    p.add_argument("--context", type=int, default=0)
    p.add_argument("--case", action="store_true", help="match case exactly")
    a = p.parse_args(argv)
    d = json.loads((OUTPUTS / f"{a.id}.json").read_text())
    if not a.word:
        for name, lines, _ in sources(d)[1:-1]:
            print(f"{name}  ({len(lines)} lines)")
        return 0
    flags = 0 if a.case else re.I
    pat = re.compile(re.escape(a.word), flags)
    hits = 0
    for name, lines, first in sources(d):
        found = [i for i, line in enumerate(lines) if pat.search(line)]
        if not found:
            continue
        print(f"== {name}")
        for i in found:
            for j in range(max(0, i - a.context), min(len(lines), i + a.context + 1)):
                mark = ">" if j == i else " "
                print(f"  {mark} {j + first:4}: {lines[j]}")
            hits += 1
    if not hits:
        print(f"'{a.word}' appears nowhere in {a.id}'s issue, tool results or comment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
