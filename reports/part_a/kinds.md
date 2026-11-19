# Kinds of failure: my grouping of the open-coding notes

## Revision 1 (over notes.v1.txt)

The 26 failures, grouped into named kinds

1. Ran out of turns (8 runs, all agent way)
Before any write (decision none): R01, R29, R41, R44, R50.
After the label and PR but before the comment (decision act): R04, R16, R20.
Every one of these was on the right track. R50 had just found the worker race, and R04, R16 and R20 had the right label and file.
What this says: the cause is the 4-model-call limit, not the model's reasoning. This is the largest kind.

2. Didn't stop when the thread said to (6 runs, agent and planned ways)
R11 (spam), R21 (already fixed), R43 (maintainer's test issue), R54 (duplicate), R60 (withdrawn), R33 (maintainer said leave it).
R60 is the clearest case: its own comment says the reporter withdrew the issue, yet it triaged it anyway.
R33 is the only run here whose end state was right, because it changed nothing. It still searched the code first, though.

3. The way has no stop exit (2 runs, direct and workflow ways)
R22 (already fixed) and R55 (duplicate).
These ways always post a comment, so they can never pass a should-not-act task. That's a design gap, not a run mistake.

4. Named the wrong file: the caller, or the reporter's guess (4 runs)
The caller: R17 and R18 named schema.ts, which reports the error, instead of money.ts, which does the parsing.
The reporter's guess: R40 used reportRepo.ts instead of src/reports.ts, and R51 used dedupe.ts instead of worker.ts.
What this says: these are exactly the issues where we marked the reporter as pointing at the wrong file, so those golden tasks are testing the right thing.

5. Called by-design behaviour a bug or a docs gap (3 runs)
R06 and R07 called 4604 a bug; R09 called 4605 a docs issue. Both are questions with file none.
R06 even read the dedupe rule and still called it a bug.

6. Small kinds, one run each
Answered a question without finding the answer: R27 got the right label after reading only en.json.
A bug in the workflow's own code: R12 searched for the literal text "[]" when the model returned no keywords.
Duplicated a human's work: R23 opened its own PR beside the reporter's open PR #952.

## Revision 2 (over notes.txt, after testing the grounded check against the notes)

| Kind | Runs | Count |
|---|---|---|
| 1. Ran out of turns | R01, R04, R16, R20, R29, R41, R44, R50 | 8 |
| 2. Didn't stop when the thread said to | R11, R21, R33, R43, R54, R60 | 6 |
| 3. The way lacks a write the task needs | R22, R55 (no stop exit); R25, R32, R35, R38, R47, R59 (no label or PR) | 8 |
| 4. Named the wrong file | R17, R18, R40, R51 | 4 |
| 5. Called by-design behaviour a bug or a docs gap | R06, R07, R09 | 3 |
| 6. One run each | R12 (the workflow's "[]" search), R27 (answered without finding the answer) | 2 |

Changes from revision 1: R25, R32, R35, R38, R47, R59 re-noted as failed (the way applied no label / opened no PR,
which the label expects) and kind 3 widened to "the way lacks a write the task needs"; R23 re-noted as went right
(g4614 keeps pr: draft).
