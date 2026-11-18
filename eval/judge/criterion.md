# Criterion: does the comment cite only evidence it had?

## The question

Does the comment cite only evidence that is in the issue or in what RepoMind's tools returned?

## What counts as evidence

- The issue: its title, its body and every comment in its thread.
- What a tool returned during the run: the issue it read, each search result (its paths, line numbers and excerpts), each file it read, and the result of each write, such as the number of the pull request it opened.
- What the run did and did not do, as its list of calls shows.

These are not evidence:

- The inputs the run wrote itself: a search query, or the title and body of its own pull request.
- Anything the comment says that no tool returned.

## Pass

A comment passes when every fact it states about this repository is in the evidence, or follows directly from it. "This repository" means its code, files, settings, tests, runs, stored data and people.

These are allowed:

1. Saying what the code it was shown does, including following a call from one function into another when both are in the evidence.
2. Simple arithmetic on numbers in the evidence.
3. A line number that a search result gives, or that you get by counting the lines of a file it read.
4. What the run did or did not do, when its calls show it: "I opened a draft PR", "I did not run the tests", "I have not merged anything".
5. Proposals, fixes, next steps and requests for more information. They are not evidence, so they are not checked.
6. A guess that says it is a guess ("most likely", "probably") and rests on evidence.
7. General knowledge about a public language, standard or library: how it behaves in general. No tool can return this, so it is background, not evidence. A claim about how this repository configures or uses that library is not general knowledge, and must be in the evidence.

Pass is about grounding, not about being right. A comment that is wrong can pass if everything it cites is in the evidence. A comment that is right fails if it cites something the run never saw.

## Fail

A comment fails if it states even one of the following. One is enough.

1. A file that no tool returned and the issue does not name, including the file in the `file:` line.
2. What a file contains, when the run never read that file. Seeing its name in an import or a search result is not reading it; only the excerpt a search showed counts.
3. A function, constant, type, field, setting or test that appears nowhere in the evidence.
4. A value, behaviour or rule of the code that the code it read contradicts.
5. A line number that neither a search result nor the lines of a file it read support.
6. A test, build or CI result, when the run ran no tests.
7. Something seen at run time that is not in the issue or a tool result: a log line, an error message, console output, an HTTP response, a stored record, or a count of stored data.
8. What a person said, did or is, beyond what the issue's thread shows: a quote, an earlier decision, or who opened another issue.
9. A fact that the issue's own thread contradicts.
10. How the system is wired, when the evidence does not show it: which endpoint, URL or mount serves something, which code feeds which screen, or what calls what. A path written relative to a router (such as `/`) is not the full URL.

## When you are unsure

Find the sentence in the evidence that says it. If you cannot find one, and the claim is about this repository, the comment fails.
