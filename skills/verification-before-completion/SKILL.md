---
name: verification-before-completion
description: "Use when about to claim work is complete, fixed, or passing — before reporting done, committing, or handing off. Triggers: done, complete, fixed, passing, works now, ready, before commit, handoff, success report, verified."
---

# Verification before completion

**Core principle:** Evidence before claims, always.

**Violating the letter of this rule is violating the spirit of this rule.**

## The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

If you did not run the command **in this session**, you cannot claim it
passes. A previous run is history, not evidence.

## The gate

Before any status claim or expression of satisfaction:

1. **Identify** the command that proves the claim.
2. **Run** the full command — fresh, complete.
3. **Read** the output: exit code, failure count, warnings.
4. **Verify** the output actually confirms the claim. If not, report the
   actual state with its evidence.
5. **Only then** make the claim — with the evidence attached.

Skipping a step is not verifying. It is claiming with extra steps.

## What each claim requires

| Claim | Requires | Not sufficient |
|---|---|---|
| Tests pass | Test output: 0 failures | A previous run, "should pass" |
| Linter clean | Linter output: 0 errors | Partial check, extrapolation |
| Build succeeds | Build command exit 0 | "the linter passed" |
| Bug fixed | Original symptom re-tested | Code changed, assumed fixed |
| Regression test works | Watched it fail, then pass | It passes once |
| Agent completed | VCS diff matches the report | The agent said "success" |
| Requirements met | Line-by-line checklist | Green tests alone |

## Rationalizations

| Excuse | Reality |
|---|---|
| "Should work now" | Run the verification. |
| "I'm confident" | Confidence is not evidence. |
| "Just this once" | No exceptions. |
| "The linter passed" | Linter ≠ compiler. |
| "The agent said success" | Verify independently — check the diff. |
| "I'm tired / out of time" | A wrong claim costs more than the run. |
| "Partial check is enough" | Partial proves nothing. |

## Red flags — STOP

- "should", "probably", "seems to", "looks like"
- Satisfaction before verification ("Great", "Perfect", "Done")
- About to commit, report, or hand off without a fresh run
- Trusting a subagent's success report without checking its diff
- "Different words so the rule does not apply" — it still applies

## pipa contract

`verified: true` in the reporting line means exactly this gate was passed,
this session. Claim `done` only with fresh evidence; `blocked` with a note
is the honest alternative to guessing. `pipa contract` lists
`verified:false` results separately — that field is what separates a
verified result from a hopeful one.
