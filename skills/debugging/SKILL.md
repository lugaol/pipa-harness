---
name: debugging
description: "Systematic bug triage and root-cause analysis. Triggers: bug, error, crash, exception, stacktrace, broken, not working, fails, fails. Reproduce, isolate, hypothesize, fix."
---
# Debugging workflow

Triage bugs methodically. Never guess-and-patch.

## Step 1 — Reproduce
- Identify the exact steps or input that triggers the bug.
- If not reproducible from the report, ask the user for the exact command/input/log.
- Capture the error message, stack trace, and exit code verbatim.

## Step 2 — Isolate
- Use graphify/grep to find where the error originates (`file:line`).
- Read only the relevant function + its callers — don't dump whole files.
- Check git blame/log for recent changes to the suspect lines: `git log -L :func:file`

## Step 3 — Hypothesize
- State the likely root cause in one sentence before touching code.
- List 1-3 candidate causes ranked by probability.

## Step 4 — Fix
- Make the smallest change that addresses the root cause (not just the symptom).
- Add or update a regression test that fails without the fix and passes with it.
- Run the project's build/test command to verify.

## Step 5 — Verify
- "Done" = the reproduction case no longer triggers + tests pass. Never "looks like it works".
