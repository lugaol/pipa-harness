---
name: debugging
description: "Use when encountering any bug, error, crash, test failure, or unexpected behavior — before proposing fixes. Triggers: bug, error, crash, exception, stacktrace, broken, not working, fails, flaky, regression, root cause, debug."
---

# Systematic debugging

Triage bugs methodically. Never guess-and-patch.

**Core principle:** Find the root cause before attempting fixes. Symptom
fixes are failure. **Violating the letter of this process is violating the
spirit of it.**

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

## Phase 1 — Root cause investigation

1. **Read the error completely.** Stack trace, line numbers, error codes,
   exit code. They often contain the answer.
2. **Reproduce consistently.** Exact steps or input, every time. Not
   reproducible → gather more data, do not guess.
3. **Check recent changes.** `git diff`, recent commits, new dependencies,
   config or environment drift. `git log -L :func:file` for suspect lines.
4. **Multi-component systems: instrument the boundaries first.** Before
   hypothesizing, log what enters and exits each layer (CI → build → sign;
   API → service → DB). Run once to see *where* it breaks, then investigate
   that component — not all of them.
5. **Trace the bad value backward.** Where did it originate? What called
   this with it? Keep going up until you find the source. Fix at the source,
   not at the symptom.

## Phase 2 — Pattern analysis

Find similar working code in the repo and compare against it. List every
difference, however small — do not assume "that cannot matter". Read the
reference implementation completely; partial understanding guarantees bugs.

## Phase 3 — Hypothesis

State it in one sentence: "X is the root cause because Y." Test with the
smallest possible change, one variable at a time. If it did not work, form
a new hypothesis — do not stack fixes on top.

## Phase 4 — Fix

1. Write a failing test that reproduces the bug first (load
   `test-driven-development`).
2. Make one change that addresses the root cause. No "while I'm here".
3. Verify the reproduction passes and the suite is green (load
   `verification-before-completion`).
4. **Count failed attempts.** Fewer than 3 → return to Phase 1 with the new
   information. At 3 → stop fixing and question the architecture: each fix
   revealing a new problem in a different place is a design problem, not a
   failed hypothesis. Escalate to `@architect` or the user.

## Rationalizations

| Excuse | Reality |
|---|---|
| "Issue is simple" | Simple issues have root causes too. |
| "Emergency, no time for process" | Systematic is faster than guess-and-check thrashing. |
| "Just try this first, then investigate" | The first fix sets the pattern. |
| "Multiple fixes at once saves time" | You cannot isolate what worked; it causes new bugs. |
| "I see the problem, let me fix it" | Seeing symptoms ≠ understanding the cause. |
| "One more fix attempt" (after 2 failures) | Three failures means architecture. Stop. |

## Red flags — STOP, return to Phase 1

- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- Proposing fixes before tracing the data flow
- Each fix reveals a new problem in a different place
- "I do not fully understand but this might work"

## After the root cause

- **Defense in depth:** add validation at the layer that should have caught
  the input, not only where it finally crashed.
- **Condition-based waiting:** in flaky async paths, poll for the condition
  instead of sleeping a fixed time.
- If investigation shows the issue is truly environmental or external,
  document what you checked, handle it (retry, timeout, clear error), and
  add logging for next time — but treat "no root cause" as an incomplete
  investigation until proven otherwise.
