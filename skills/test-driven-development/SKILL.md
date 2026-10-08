---
name: test-driven-development
description: "Use when implementing any feature, bugfix, or behavior change — before writing implementation code. Triggers: new feature, bug fix, refactor, add behavior, write a test, test first, RED-GREEN-REFACTOR, TDD."
---

# Test-driven development

**Core principle:** If you did not watch the test fail, you do not know it
tests the right thing.

**Violating the letter of the rules is violating the spirit of the rules.**

## The Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Wrote code before its test? Delete it. Start over. No exceptions:

- Don't keep it as "reference"
- Don't adapt it while writing tests
- Don't look at it. Delete means delete.

## The cycle

1. **RED** — Write one minimal test showing what should happen. One
   behavior, clear name, real code (mocks only when unavoidable).
2. **Verify RED** — Run it. Confirm it fails for the expected reason
   (behavior missing, not a typo). A test that passes immediately tests
   existing behavior — fix the test.
3. **GREEN** — Write the simplest code that passes. No extra features, no
   speculative options, no drive-by refactoring.
4. **Verify GREEN** — Run it, then run the *project's* suite (bare
   `pytest`, `npm test`, whatever the repo uses), not just your file. A
   green file is not a green suite. Any failure that run shows — including
   one you did not cause — goes in your report by name. A red test you
   watched scroll past and did not mention is a report falsified by
   omission.
5. **REFACTOR** — Clean up while staying green. No new behavior.

Then the next failing test for the next behavior.

## Bug fixes

A bug fix starts with a test that reproduces the bug. Watch it fail against
the unfixed code, then fix. No fix without a reproducing test.

Regression test proof: write → run (pass) → revert the fix → run (MUST
fail) → restore → run (pass). A test that only ever passed proves nothing.

## Rationalizations

| Excuse | Reality |
|---|---|
| "Too simple to test" | Simple code breaks. The test takes 30 seconds. |
| "I'll test after" | Tests written after pass immediately — that proves nothing. |
| "Tests after achieve the same goal" | Tests-first answer "what should this do"; tests-after answer "what does this do". |
| "Already manually tested" | Ad-hoc, no record, re-run by hand on every change. |
| "Deleting hours of work is wasteful" | Sunk cost. Untrusted code is the waste. |
| "Keep it as reference" | You will adapt it. That is testing after. Delete. |
| "TDD slows me down" | Debugging in production is slower. |
| "This is different because..." | No, it is not. |

## Red flags — STOP and start over

- Code before test; tests added "later"; "just this once"
- Test passes immediately, or you cannot explain why it failed
- "I already manually tested it"; "spirit not ritual"; "keep as reference"

## When stuck

Hard to test means hard to use — simplify the interface. Mocking everything
means too much coupling — inject the dependency. Unknown framework: read the
repo's existing tests and mirror them. Never skip the test because the
design is awkward; let the test drive the design.

## Done means

Every new behavior has a test that was watched failing first, the full
suite is green, and the output is pristine (no new warnings). Before
claiming done, load `verification-before-completion`.
