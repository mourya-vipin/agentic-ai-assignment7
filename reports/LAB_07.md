# Assignment 7 · The evaluation harness, and a judge you have checked

Model: Google Gemini, `gemini-3.5-flash-lite` (OpenAI-compatible endpoint), the same for every run and for the judge.

## Part A · A golden set from traces

**The kinds of failure** you found by reading the recorded runs (slide 12), until no new kind appeared.

I wrote an open-coding note for each of the 60 recorded runs, in [reports/part_a/notes.txt](part_a/notes.txt): its first wrong step (or "went right") and the decision it made. 31 of the 60 failed. The first version of the notes is [notes.v1.txt](part_a/notes.v1.txt), and my grouping of them is [kinds.md](part_a/kinds.md). R01–R60 number the runs in the order `python -m eval.view_traces` lists them, and [run_ids.txt](part_a/run_ids.txt) maps each number to its trace in `fixtures/traces7/`.

| Kind of failure | Runs | One run that shows it, and its first wrong step |
|---|---|---|
| 1. Ran out of turns | R01, R04, R16, R20, R29, R41, R44, R50 (8) | R16: hit the 4-model-call turn limit after labelling bug and opening the PR on src/api/reports.ts, before the comment |
| 2. Didn't stop when the thread said to | R11, R21, R33, R43, R54, R60 (6) | R60: understood the reporter had withdrawn it (its own comment says so), yet searched the code and triaged it |
| 3. The way lacks a write the task needs | R22, R55 (no stop exit); R25, R32, R35, R38, R47, R59 (no label or PR) (8) | R22: commented on an issue the thread shows was already fixed and closed; the workflow has no way to stop. R25: right label and file in the comment, but the workflow way applied no label and opened no draft PR, which the task expects |
| 4. Named the wrong file | R17, R18, R40, R51 (4) | R17: named src/ingest/schema.ts, which only reports the error; the parsing that rejects .75 is in src/util/money.ts |
| 5. Called by-design behaviour a bug or a docs gap | R06, R07, R09 (3) | R06: read the dedupe rule in src/ingest/dedupe.ts and still called by-design behaviour a bug; it is a question, file none |
| 6. One run each | R12, R27 (2) | R12: the model rightly found no search terms, but the workflow then searched the code for the literal text "[]" |

- **Runs read, and when no new kind appeared:** all 60. The last new kind first appeared at R27, and none appeared in the 33 runs after it. I revised the notes once, after testing the grounded check against them. Six workflow and direct runs (R25, R32, R35, R38, R47, R59) had left out a label or PR the task expects, so I re-noted them as failed and widened kind 3 to cover them. I also re-noted R23 as went right.

**How you chose the tasks** (slide 12's table): every kind of task, the failures, each path, no copies.

I labelled all 40 issues (4601–4640) by hand: stratum, decision, label and file. For the open issues, the file comes from the source I named. From these 40, Claude Code proposed a 30-task set, which I approved. By my notes, 24 of the 30 have at least one failed recorded run; the other 6 pass every run and guard against regressions. All four labels appear, and the set covers:
- both no-PR paths (file `none`, and `stop`);
- both approval-path issues (4606, 4621);
- all five wrong-file traps;
- the duplicate pair (4601 and its duplicate 4636);
- 15 different code and doc files.

Each path has tasks: a pull request (every `act` task with a file, such as 4601 and 4610), a question with no file (4604, 4617), a documentation fix (4612, 4632) and a refusal (the five adversarial tasks). Every kind of failure has its issues in the set, all of them, since none has more than eight:

| Kind | Its issues, all in the set |
|---|---|
| 1. Ran out of turns | 4601, 4603, 4610, 4612, 4618, 4626, 4629, 4633 |
| 2. Didn't stop when the thread said to | 4607, 4613, 4621, 4628, 4636, 4640 |
| 3. The way lacks a write the task needs | 4613, 4615, 4620, 4622, 4625, 4631, 4636, 4639 |
| 4. Named the wrong file | 4611, 4626, 4633 |
| 5. Called by-design behaviour a bug or a docs gap | 4604, 4605 |
| 6. One run each | 4607, 4617 |

I left out ten issues as near-copies of tasks I kept. None of them has a failed recorded run:
- 4602 and 4635: unusual issues; 4610 already covers 4635's file;
- 4608 and 4619: features like those kept;
- 4609: `parser.ts`, which 4601 already covers;
- 4637: a second open-issue feature beside 4630;
- 4616, 4624 and 4634: bugs like those kept;
- 4627: a question like 4604.

The set is versioned as [eval/golden/v1/](../eval/golden/v1/manifest.yaml).

| Stratum | Tasks | Decisions (act, refuse, stop) |
|---|---|---|
| routine | 11 | 11, 0, 0 |
| unusual | 8 | 8, 0, 0 |
| adversarial | 5 | 0, 5, 0 |
| should-not-act | 6 | 0, 0, 6 |

- **The grounded check against my notes:** [eval/grounded.py:53](../eval/grounded.py#L53), run on the end states of the 50 recorded runs on issues in the set (`fixtures/traces7/*.state.json`), agrees with my note on 48. The two it passes and I failed are R27 and R33. Both went wrong in their route, but left the right end state: R27 got the right label after reading only en.json, and R33 searched the code but changed nothing. An end-state check cannot see a wrong route that ends in the right place (slide 25). Part B's trajectory metrics are there for that.
- **The thinnest stratum, and the smallest fall it can show:** adversarial has 5 tasks. One task changing moves that stratum's score by 20 points, so a fall smaller than 20 points cannot show there.

## Part B · The harness

- **How a run becomes a line in `results/`, and what reads the end state:**
  - [eval/results_07.py:49](../eval/results_07.py#L49) `finished_runs` picks every finished run of a way with the given switches from `runs/*.jsonl`. It leaves out scripted runs, runs with no `run_end`, and runs that ended on quota or a rate limit.
  - [results_07.py:124](../eval/results_07.py#L124) `result_line` rebuilds the run's end state from the tracker with [harness/tasks.py:211](../harness/tasks.py#L211) `end_state`. That covers comments, labels, open PRs, closes, merges, pushes and writes elsewhere.
  - [eval/grounded.py:53](../eval/grounded.py#L53) `check` compares that end state with the task's `expect`, fact by fact. `passed` and `facts` come from it, `metrics` from [eval/metrics.py:97](../eval/metrics.py#L97), and `measure` from the claim (repeats, for `plan`).
  - The model never sees the end state; only the check reads it.
- **One table from your Part C results, as the harness reports it (runs, spread, pass@k and pass^k with *k*):** from `python -m eval.report_07`, with *k* = 3. Each spread is the SD over the five sweep values.

| Arm | Runs | Repeats per run: mean (SD over sweeps) | Score: mean (SD) | pass@3 | pass^3 |
|---|---|---|---|---|---|
| A, planned | 40 | 0.700 (0.190) | 22.5 (13.7) | 0.400 | 0.063 |
| B, agent | 40 | 0.125 (0.088) | 30.0 (6.8) | 0.450 | 0.150 |

## Part C · Settle one claim

- **The claim, its two arms, the measure and the sign of the gain:** the claim is `plan`, that planning first cuts repeated calls. Arm A is the planned way and arm B the agent way, both with every switch at its default. The measure is repeats: the calls whose name and input match an earlier call's. The gain is B − A, so it is positive when the plan repeats less.
- **The first three sweeps: each arm's *s*, and the cost of one sweep:** the sweep values were 0.875, 0.75, 0.875 for A and 0.125, 0.125, 0 for B, so *s*_A = *s*_B = 0.0722. Three sweeps give only a rough *s*, so the sizing below is rough too. One sweep of 8 tasks cost $0.058 for A and $0.074 for B, a mean of $0.0661 per sweep over both arms.
- ***δ*, the sweeps it needs, and the price (slide 55):** *δ* = 0.25 repeats per run. n = ⌈(0.0722² + 0.0722²)(2.80/0.25)²⌉ = 2 sweeps per arm, and the price is 2 × 2 × $0.0661 = $0.26. I ran the five sweeps the claim names, more than the two it needs.
- **The bar and the group rule, as committed, and the commit:**
  - The bar is 0.0: the interval's low end must be above 0.
  - The group floor is −0.5: no stratum's gain may be below it.
  - Both are in [eval/thresholds/claim.yaml](../eval/thresholds/claim.yaml), commit `cfb793c`, made at 2026-11-17 23:25:06 CST after sweeps 1–3 and pushed before any fourth sweep. The first sweep-4 run started 37 seconds later (05:25:43Z).
  - My prediction, in the same file: arm A, by 0.05, largest on unusual. Why: "The plan runs each step once, so I expect slightly fewer repeats, but neither way repeated a call in 60 recorded runs, so the gap should be small, about 0.05, and largest on the unusual issues, where a wrong file sends the agent searching longest."

**The results**, from `results/`.

| Arm | Runs | Measure: mean (SD) | Score: mean (SD) | pass@k | pass^k | Facts right | Cost per run |
|---|---|---|---|---|---|---|---|
| A | 40 | 0.700 (0.190) | 22.5 (13.7) | 0.400 | 0.063 | 0.758 | $0.0070 |
| B | 40 | 0.125 (0.088) | 30.0 (6.8) | 0.450 | 0.150 | 0.774 | $0.0094 |

Each arm on each stratum (2 tasks × 5 sweeps = 10 runs; the SDs are over the five sweep values):

| Arm | Stratum | Runs | Repeats: mean (SD) | Score: mean (SD) | pass@3 | pass^3 | Facts right |
|---|---|---|---|---|---|---|---|
| A | routine | 10 | 0.10 (0.22) | 40 (22.4) | 0.50 | 0.20 | 0.75 |
| A | unusual | 10 | 0.90 (0.89) | 20 (27.4) | 0.60 | 0.00 | 0.76 |
| A | adversarial | 10 | 1.30 (0.76) | 30 (27.4) | 0.50 | 0.05 | 0.74 |
| A | should-not-act | 10 | 0.50 (0.50) | 0 (0.0) | 0.00 | 0.00 | 0.79 |
| B | routine | 10 | 0.40 (0.42) | 10 (22.4) | 0.30 | 0.00 | 0.68 |
| B | unusual | 10 | 0.00 (0.00) | 30 (27.4) | 0.50 | 0.05 | 0.67 |
| B | adversarial | 10 | 0.10 (0.22) | 80 (27.4) | 1.00 | 0.55 | 0.94 |
| B | should-not-act | 10 | 0.00 (0.00) | 0 (0.0) | 0.00 | 0.00 | 0.81 |

Neither arm passed a should-not-act run: each one wrote something (a label or a comment) on an issue where the right move was to change nothing.

| Stratum | Gain | 95% interval |
|---|---|---|
| All tasks | −0.575 | [−0.758, −0.392] |
| routine | +0.300 | [−0.116, 0.716] |
| unusual | −0.900 | [−1.684, −0.116] |
| adversarial | −1.200 | [−1.893, −0.507] |
| should-not-act | −0.500 | [−0.938, −0.062] |

- **The verdict, by your bar, and why:** **fails.** The whole interval, [−0.758, −0.392], is below the bar of 0: on these tasks the plan repeats *more* calls than the agent, not fewer. The group rule fails too: unusual (−0.9) and adversarial (−1.2) are below the floor of −0.5. Should-not-act sits exactly on it (−0.5), and only routine favours the plan (+0.3, an interval that includes 0).
- **Cost beside the score (slide 54):**
  - The agent costs 35% more per run ($0.0094 against $0.0070), and passes 7.5 points more (30.0 against 22.5).
  - Per passed run they cost the same: A spent $0.279 for 9 passes ($0.031 each), and B $0.376 for 12 ($0.031 each).
  - The agent is also steadier: its score's SD over sweeps is 6.8 points, against the plan's 13.7, and its pass^3 is 0.150, against 0.063.
- **Each part of your prediction that missed, and the run that shows why:**
  - **The arm** (A predicted; B repeated less). [planned-g4614-s04-8934eb](../runs/planned-g4614-s04-8934eb.jsonl) shows why. Its planner wrote every step's `args_json` escaped twice (`{\"issue\": \"issue-4614\"}`). [agent/diff.py:23-26](../agent/diff.py#L23-L26) turns an `args_json` it cannot parse into `{}` without an error, so `issues_read {}` and `code_search {}` were rejected. The reviser rebuilt the plan after the first search, and the same empty calls ran again: `issues_read {}` twice and `code_search {}` three times, which is 3 repeats.
    - 15 of A's 40 runs started from a plan escaped twice. They average 1.73 repeats against 0.08 for A's other 25 runs, and none of them passed.
    - My reasoning held for the plans that parsed: those 25 runs repeated less than B's 0.125 per run, though on a different mix of tasks. It missed because the 60 recorded runs never showed a plan escaped twice.
  - **The size** (0.05 predicted; 0.575 the other way). Almost all of it comes from those 15 runs: they hold 26 of A's 28 repeats.
  - **The stratum** (unusual predicted, adversarial largest at −1.2; unusual came second at −0.9).
    - [planned-g4614-s04-8934eb](../runs/planned-g4614-s04-8934eb.jsonl) is again the run: adversarial task g4614 got a plan escaped twice in 4 of its 5 sweeps.
    - The agent's long search on an unusual issue made new calls, not repeats. For example, [agent-g4610-s01-fe9216](../runs/agent-g4610-s01-fe9216.jsonl) made 12 calls with different queries and hit the step limit with 0 repeats. So "searching longest" did not turn into repeats.

**Where the failed runs first went wrong** (slide 29), last good step down the side, first wrong step across.

A failed run's first wrong call is the earliest call the tool rejected, or the earliest write the task's expected end state rules out, whichever comes first: a push, close or merge; any write on a stop task; a wrong label; a second comment; or a PR or comment naming the wrong file. When no call was wrong, the run ended before a call it needed, marked `stop`. That is how my Part A notes treat a run that hit the turn limit. The rule is [eval/first_failures.py:41](../eval/first_failures.py#L41), and `python -m eval.first_failures --show` prints each run's mark with its reason.

```
Arm A, planned (31 failed runs): last good down, first wrong across
                  code_read_file     code_search    issues_label     issues_read      pulls_open
start                                                                         15                
issues_read                                    2                                                
code_search                    4               2                                                
code_read_file                                                 6                                
issues_label                                                                                   2

Arm B, agent (28 failed runs): last good down, first wrong across
                   branches_push  issues_comment    issues_label            stop
issues_read                                    5               5                
code_search                    1                                              10
code_read_file                 4                                               1
pulls_open                                                                     2
```

- **The biggest count, and whether its cause is local, upstream or structural:**
  - The biggest count is A's `start → issues_read`: 15 runs whose very first call went out empty and was rejected. The cause is **upstream**. The call did exactly what the plan said; the plan, written before any call, was wrong.
    - The planner encoded `args_json` twice.
    - The validator passed it, because it checks the plan's shape but not that `args_json` parses.
    - The executor turned it into `{}` without an error.
    - The 15 runs in this cell are exactly the 15 whose plan was escaped twice.
  - B's biggest count, `code_search → stop` (10), is **structural**. All 13 of B's `stop` runs used all 12 of the agent's steps (`agent/bounds.yaml`), and 6 of them had already labelled the issue and opened the PR, then spent their remaining steps re-reading files and searching for tests. The comment, which must come last, never came. The other 7 were still searching when the limit hit.
- **How a replay from Assignment 4's checkpoints would confirm it:**
  1. Run issue 4614 the planned way with `--die-after-step 3`, outside the measured sweeps; 15 of 40 runs got a plan escaped twice, so it may take a few tries. The first checkpoint is saved at step 3, the file read, even when the read is rejected. It holds the plan, each step's status and every completed call, but never the conversation.
  2. If the checkpointed plan's `args_json` is escaped twice, the fault was in the plan before any call.
  3. Then `python run.py --resume <run_id>`. The resumed run rebuilds the executor from the checkpoint without calling the planner. If it sends the same `{}` calls, the plan alone causes them, not anything the model did at the step.
  4. Resume once more, from a copy of the checkpoint whose `args_json` is escaped once. If the same steps then go through, the cause is upstream and nowhere later.
- **Runs that called no tool:** none, in either arm (0 of 40 each).
- **Why only a check outside the run catches an early stop (slide 31):** 28 of the planned way's 31 failed runs ended `completed`, and nothing inside them disagreed. In [planned-g4601-s01-6194ab](../runs/planned-g4601-s01-6194ab.jsonl), for example, the comment step was rejected for its empty input, and the run still finished as completed, with no comment and no PR. Only the grounded check, reading the tracker, failed it.

## Part D · Validate a judge

The criterion is [eval/judge/criterion.md](../eval/judge/criterion.md), and my account of how its lines came about is [eval/judge/criterion_history.md](../eval/judge/criterion_history.md). Both are in my own words. My 60 labels, each with a one-line reason, are [eval/labels/labels.csv](../eval/labels/labels.csv): 36 pass and 24 fail.

- **The criterion's lines, and what labelling added to them:**
  - My first working list came from a quick scan of every comment for names, files and numbers that weren't in the evidence. It held fail lines 1 (a file no tool returned), 3 (a name that appears nowhere), 5 (an unsupported line number), 6 (a test or CI result), 7 (a run-time observation) and 8 (a person's words or actions), plus an open question about general library knowledge.
  - Labelling added fail 2 (the contents of an unread file, from j01), fail 4 (a code fact the code contradicts, from j22, j23 and j47), fail 9 (a fact the thread contradicts, from j18) and fail 10 (wiring the evidence doesn't show, from j20).
  - It also added pass lines 3 (counting a file's lines), 4 (what the run did), 6 (a marked guess) and 7 (general library knowledge, which settled the open question), and the sentence "pass is about grounding, not correctness" (from j11).
  - Only one label changed: j20, which I first leaned towards passing, then failed under line 10. For the others I had already decided fail, and wrote the line to cover that decision.
  - Against my Part A notes, only fail lines 1 and 9 match recorded runs: R07, R17, R32, R38 and R55 for line 1, and R40 for line 9. The other eight lines rest on the judge outputs alone.
- **The split, and when it was committed:**
  - [eval/labels/split.yaml](../eval/labels/split.yaml), stratified by system and label (seed 7): 8 examples, 26 tuning and 26 test, with 17 passes and 9 fails in the test set.
  - Commit `369ed23` at 2026-11-18 00:23:09 CST, before the first change to `eval/judge.py` or `prompts/judge.md` (`24a21b8`, 00:25:35).
- **The judge: its model and version, and its TPR and TNR on the test set:**
  - The judge is `gemini-3.5-flash-lite`, with prompt [prompts/judge.md](../prompts/judge.md) at digest `be02682d823b`. The prompt holds:
    - my criterion, verbatim;
    - three examples from the examples set: j44 pass, j49 fail and j20 fail, each with a reply whose reasoning starts from my label's reason;
    - a JSON reply format.
  - It was tuned on the examples and tuning sets only, over four rounds ([eval/judge/tuning/](../eval/judge/tuning/)):

    | Round | Examples (TPR, TNR) | Tuning (TPR, TNR) |
    |---|---|---|
    | 1 | 1.00, 0.50 | 1.00, 0.82 |
    | 2 | 1.00, 0.75 | 1.00, 0.91 |
    | 3 | 1.00, 1.00 | 0.93, 1.00 |
    | 4 | 0.75, 1.00 | 0.93, 0.91 |

  - What changed between rounds:
    - Round 2 told the judge to check the detail a claim attaches to a name (what a function does, a line number, where a route is mounted).
    - Round 3 numbered the lines of each file read and added j20 as an example.
    - Round 4 added one sentence (on SQL's default sort order) and did worse, so the prompt was frozen at round 3's before the test set ran.
  - On the test set (run 1): **TPR 1.000 (17/17), TNR 0.889 (8/9).** The one miss is j18, whose comment the thread contradicts (my fail line 9); the judge passed it.
- **Its pass rate on the recorded runs, corrected, with its interval:**
  - The judge passed all 20 of the agent way's recorded comments, so p = 1.00. Corrected, (p + TNR − 1)/(TPR + TNR − 1) = **1.00**, and the bootstrap interval (2,000 resamples of the test set, seed 0) is **[1.00, 1.00]**. Not a coin: TPR + TNR − 1 = 0.89.
  - The interval has no width because TPR is 1 in every resample, and with p = 1 the correction then gives 1 whatever TNR is. It carries the test set's uncertainty, not the uncertainty of p from only 20 comments. 20 of 20 alone has a 95% lower bound of 0.83.
  - It is also too high by my own notes. R40 (agent-issue-4626) is one of the 20. My Part A notes record that its comment told the reporter their diagnosis held, although the thread had moved the problem to the dashboard list. That is fail line 9, the same kind the judge missed on j18. With p = 19/20, the corrected rate would be 0.94.
- **Its flip rate, and whether a majority of three was kept:**
  - The flip rate is **0.077**: 2 of the 26 test items (j03 and j53) changed verdict across the three runs. They are listed for a person in [eval/judge/for_a_person.txt](../eval/judge/for_a_person.txt).
  - A majority of three was **not kept**. Its TPR is 1.000, but its TNR is 0.778, worse than run 1's 0.889, because j03 passed in runs 2 and 3.
- **What moved on the reformatted and lengthened versions:**
  - 2 of 26 items moved from run 1's verdict, a moved share of **0.077**.
  - j03: its `long` version passed. j03 also flips between runs, so this is more likely the judge's noise than the format.
  - j22: its `long` version passed, although the `list` version and the original fail it on 07:00 UTC against `RUN_HOUR_UTC = 6`. The longer text hid the one wrong number from the judge.
  - Nothing moved on the `list` versions alone.
  - What I would change: the prompt already tells the judge to ignore format and length. For length I would add a line telling it to check every number in a comment against the evidence, however long the comment is. That change makes a new judge, which would need validating again on the test set: new TPR, TNR and flip rate.
- **Its rates on each system:**
  - On Claude Haiku 5.5 outputs (12 test items): TPR 1.00, TNR 0.80 (4 of 5 fails caught).
  - On Claude Sonnet 5.5 outputs (14 items): TPR 1.00, TNR 1.00 (4 of 4).
  - The one miss (j18) is a Haiku output. With only 4 or 5 fails per system, the gap between the systems is that one item.
- **What validating the judge still needs:**
  - More failing items in the test set. TNR rests on 9 fails, so one item moves it by 11 points.
  - An interval that also resamples the recorded comments, so that p's own uncertainty shows.
  - A person reading the 20 recorded comments the judge passed. At least one, R40, fails by my notes, and it is the kind of failure (fail line 9, a fact the thread contradicts) the judge also missed on j18. Thread contradictions are its weak spot.
  - Its long-comment blind spot (j22) checked on more items.
  - A recheck whenever the model, the prompt or RepoMind's comment style changes: the digest pins this prompt, and the rates hold for it alone.

## AI assistance

Tool: Claude (Claude Code, Anthropic).

**What I did myself.** I wrote by hand every label and every judgement the assignment asks for: the stratum, decision, label and file for the 40 issues behind the golden set; the open-coding notes on all 60 recorded runs, and the kinds of failure; δ, the bar, the group rule and the prediction; the judge's criterion and its history; and the 60 judge labels with their reasons. No assistant wrote or suggested a label.

**What Claude wrote.** Claude wrote the code:
- `eval/grounded.py`, `eval/stats.py`, `eval/metrics.py`, `eval/results_07.py` and `tests/test_eval.py`;
- `eval/judge.py` and the judge prompt. The prompt embeds my criterion verbatim; its three examples come from the examples set, and each reply's reasoning starts from my label's reason;
- `eval/first_failures.py` and `eval/report_07.py`;
- reading views for the runs and outputs (`eval/view_traces.py`, `eval/view_outputs.py`) and an evidence search (`eval/find_evidence.py`). These only search; they never say whether an output passes.

**What Claude proposed or ran.** It proposed the 30-task golden set from my labels and the 8-task claim subset, and I approved both. It marked the first failures in Part C by the rule stated there. It tuned the judge prompt over four rounds on the examples and tuning sets, and froze it before the test set ran. It also drafted the report's prose.

**What I checked:**
- my labels and notes with a format-only check, and the reasons I was unsure of against the evidence with `find_evidence`;
- the grounded check against my Part A notes and against the checker's altered end states;
- every Part C number against `results/`, the traces and the `run_end` lines;
- each first failure against the failed run's `tool_call` lines (`python -m eval.first_failures --show`), including the planned runs' `args_json` escaped twice;
- the judge's tuning disagreements against my label reasons, the frozen prompt's digest before the test set ran, and its pass on R40 against my notes;
- `make test` and `make check-07`.
