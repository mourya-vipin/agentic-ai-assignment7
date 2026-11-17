"""Assignment 7, Part B, task 4: five trajectory metrics, by counting (slide 26;
checks/FORMATS.md, section 15.5).

    from eval.metrics import metrics
    metrics(lines, task)
    # {"step_count": 3, "precision": 0.8, "recall": 1.0, "repeats": 1, "orphans": 1,
    #  "no_tools": False, "cost_usd": 0.0412, "latency_s": 18.2}

`lines` is one run's trace, as a list of dicts (one per JSON line of
runs/<run_id>.jsonl, or of a recorded run in fixtures/traces7/); `task` is its golden
task, whose `reference` holds the calls and tools a good run makes. The definitions,
exactly; the checker counts the same way on the recorded runs:

- A **call** is a `tool_call` line, in order, whatever it returned. A resumed run's
  calls are every `tool_call` line, before its `resume` line and after.
- **step_count**: the run's calls, minus the task's reference count,
  `task.reference["calls"]`.
- **precision**: of the distinct tool names the run called, the share that are in the
  task's reference tools, `task.reference["tools"]`; None when it called none.
- **recall**: of the reference tools, the share the run called at least once.
- **repeats**: the calls whose name and input are identical to an earlier call's,
  each extra call counted once. Compare inputs in canonical form, keys sorted and no
  whitespace, as `canonical` below writes them.
- **orphans**: the reads whose output no later step uses. A read is a call whose
  name is not in WRITES. Its identifiers are the paths it returned (its `paths`), or,
  when it returned none, the values in its input as text: every value that is not
  null and not an object, a list's items one by one, numbers and booleans written as
  Python's str() writes them. A read is used when one of
  its identifiers appears, ignoring case, in the canonical input of a later call or
  in the run's final comment, the `body` of its last call in COMMENT_WRITES; a path
  also appears when its file name alone does (`exportUtils.ts` for
  `src/exportUtils.ts`). Only identifiers of three characters or more count.
- **no_tools**: True when the run made no call at all (slide 28).
- **cost_usd** and **latency_s**: the last `run_end` line's `totals.cost_usd` and
  `elapsed_s`.

Slide 27's trace, fixtures/traces7/s27.jsonl with fixtures/traces7/s27.task.yaml,
gives 3, 0.8, 1.0, 1 and 1.
"""

from __future__ import annotations

import json

# Writes, by role name and by RepoMind's tool names: their output is what they changed,
# so none is ever an orphan.
WRITES = frozenset({
    "post_comment", "open_pr", "apply_label", "close_issue", "push_commit", "merge_pr",
    "issues_comment", "pulls_open", "issues_label", "issues_close", "branches_push", "pulls_merge",
})
COMMENT_WRITES = frozenset({"post_comment", "issues_comment"})


def canonical(value) -> str:
    """A tool input in one standard form: keys sorted, no whitespace."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _reference(task) -> dict:
    """The task's reference, from a golden task (an object with .reference) or a dict."""
    ref = task.get("reference") if isinstance(task, dict) else getattr(task, "reference", None)
    if not ref or "calls" not in ref or "tools" not in ref:
        raise ValueError("the task has no reference {calls, tools}")
    return ref


def _identifiers(call: dict) -> list[str]:
    """A read's identifiers: the paths it returned, or else the plain values in its input."""
    paths = [str(p) for p in call.get("paths") or [] if p]
    if paths:
        return paths
    out = []
    for value in (call.get("input") or {}).values():
        if isinstance(value, (list, tuple)):
            out.extend(str(v) for v in value if v is not None)
        elif value is not None and not isinstance(value, dict):
            out.append(str(value))
    return out


def _appears(identifier: str, text: str) -> bool:
    """Whether an identifier of three characters or more appears in text, ignoring case;
    a path also appears when its file name alone does."""
    identifier, text = identifier.lower(), text.lower()
    if len(identifier) < 3:
        return False
    if identifier in text:
        return True
    name = identifier.rsplit("/", 1)[-1]
    return "/" in identifier and len(name) >= 3 and name in text


def metrics(lines: list[dict], task) -> dict:
    ref = _reference(task)
    calls = [line for line in lines if line.get("type") == "tool_call"]
    expected = set(ref["tools"])
    used = {c["name"] for c in calls}

    seen, repeats = set(), 0
    for c in calls:
        key = (c["name"], canonical(c.get("input")))
        repeats += key in seen
        seen.add(key)

    comments = [c for c in calls if c["name"] in COMMENT_WRITES]
    final = str((comments[-1].get("input") or {}).get("body") or "") if comments else ""
    orphans = 0
    for i, c in enumerate(calls):
        if c["name"] in WRITES:
            continue
        later = " ".join(canonical(d.get("input")) for d in calls[i + 1:]) + " " + final
        orphans += not any(_appears(x, later) for x in _identifiers(c))

    ends = [line for line in lines if line.get("type") == "run_end"]
    end = ends[-1] if ends else {}
    return {
        "step_count": len(calls) - int(ref["calls"]),
        "precision": len(used & expected) / len(used) if used else None,
        "recall": len(used & expected) / len(expected) if expected else 1.0,
        "repeats": repeats,
        "orphans": orphans,
        "no_tools": not calls,
        "cost_usd": float((end.get("totals") or {}).get("cost_usd") or 0.0),
        "latency_s": float(end.get("elapsed_s") or 0.0),
    }
