# How the criterion's lines came about (the user's own account, recorded verbatim)

## Lines on my first working list

I made this list from a quick scan of every comment for names, files and numbers that weren't in the evidence:

- Fail 1: a file no tool returned
- Fail 3: a name that appears nowhere
- Fail 5: an unsupported line number
- Fail 6: a test or CI result
- Fail 7: a run-time observation
- Fail 8: a person's words or actions
- An open question about general library knowledge, settled later as pass rule 7

## Lines that came from labelling

| Line | The output that showed it was needed | Labels it decided |
|---|---|---|
| Fail 2, contents of an unread file | j01 (described errors.ts without reading it) | j01, j25, j31 → fail |
| Fail 4, a code fact the code contradicts | j22, then j23 and j47 | j22, j23, j47 → fail |
| Fail 9, a fact the thread contradicts | j18 | j18 → fail |
| Fail 10, wiring the evidence doesn't show | j20 | j20: pass → fail |
| Pass 3, count the lines of a file it read | j02 and j34, to set fail 5's boundary | none on its own |
| Pass 4, what the run did or didn't do | j04, j21, j29, j53 | none on its own; it keeps "I haven't merged" from failing |
| Pass 6, a guess marked as a guess | j11 and j51 | j11, j51 stay pass |
| Pass 7, general library knowledge | j06, j10, j26, j42, j60 | those five stay pass |
| The "grounding, not correctness" sentence | j11 ("in your time zone" rests on a call it read, though the real function ignores the zone) | j11 stays pass |

## The only label that actually changed

j20 is the only label that flipped. I first leaned pass, then added fail 10 and failed it.
For j01, j18, j22, j23, j25, j31 and j47, I had already decided "fail" when I read each one. I then wrote the line to cover that decision.

Line 10 decides only j20 on its own.
j18 also shows unseen wiring, but line 9 already fails it.
j37's GET /api/v1/health is also wiring it never saw, but line 7 (the 401 response) already fails it.

## Judgement calls

- Pass rule 7, general library knowledge: "multer decodes names as latin1" or "Zod files pathless errors under formErrors" is treated as background knowledge, because no tool could return it. Strict alternative: j06, j10, j26, j42 and j60 flip to fail (29 fail, 31 pass). The cost of this choice: an invented library fact would pass.
- j20: "the root of the API" fails under line 10, since health.ts only shows a route relative to its router. Read as fair, it would pass, and line 10 would have no output of its own left.
