---
name: code-review
description: "Review code changes for quality, security, and correctness. Triggers: review, PR, pull request, diff, code review, before merge, check my changes."
---
# Code review

Review changes (staged, unstaged, or a branch diff) against the rules in `rules/`.

## Method
1. Get the diff: `git diff` (unstaged), `git diff --cached` (staged), or `git diff main...HEAD` (branch).
2. For each changed hunk, check:
   - **Correctness**: logic errors, off-by-one, null/undefined, race conditions.
   - **Security**: secrets, injection, unvalidated input (see `rules/security.md`).
   - **Convention**: matches surrounding style, naming, patterns.
   - **Tests**: new behavior tested? Bug fix has a regression test?
   - **Scope**: is the change minimal? Any unrelated drive-by edits?
3. Use Context7 MCP to verify library API usage if the diff touches an external API.

## Output
- Group findings by severity: **Block** / **Should fix** / **Nit**.
- Cite `file:line` for every finding.
- If nothing blocks, say "No blockers" and list nits only.
- Never approve your own changes — a review is an independent pass.
