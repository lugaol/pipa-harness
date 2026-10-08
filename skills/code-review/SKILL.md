---
name: code-review
description: "Use when reviewing code changes, and when receiving review feedback. Triggers: review, PR, pull request, diff, code review, before merge, check my changes, review comments, feedback on my code."
---
# Code review

Review changes (staged, unstaged, or a branch diff) against the map in
`AGENTS.md` and the skills that the diff actually implicates.

## Reviewing

1. Get the diff: `git diff` (unstaged), `git diff --cached` (staged), or
   `git diff main...HEAD` (branch).
2. Two stages, in order:
   - **Spec compliance**: every acceptance criterion met, `file:line`
     evidence. Nothing extra beyond the story.
   - **Quality**: correctness, security (load `security-hardening`),
     convention, tests that assert real behavior, minimal diff, no
     drive-by edits.
3. Use Context7 MCP to verify library API usage if the diff touches an
   external API.

## Output
- Group findings by severity: **Block** / **Should fix** / **Nit**.
- Cite `file:line` for every finding, and say which stage it came from.
- If nothing blocks, say "No blockers" and list nits only.
- Never approve your own changes — a review is an independent pass.
- Never pre-judge: do not drop a finding because the plan mandated the
  code or because you think the author will disagree.

## Receiving review

Code review requires technical evaluation, not emotional performance.

1. **Read** all feedback without reacting.
2. **Restate** the requirement in your own words, or ask.
3. **Verify** it against the codebase before changing anything.
4. **Evaluate** whether it is technically sound for this codebase.
5. **Respond** with a technical acknowledgment or a reasoned pushback.
6. **Implement** one item at a time, testing each.

- Never: "You're absolutely right!", "Great point!", "Let me implement
  that now" before verifying. No performative agreement, no gratitude —
  state the fix or just fix it.
- Unclear on any item? Stop and ask about all unclear items before
  implementing any. Items are often related; partial understanding means
  wrong implementation.
- Push back with evidence when the suggestion breaks existing behavior,
  conflicts with prior decisions, or is YAGNI. If you pushed back and were
  wrong, state the correction factually and move on — no long apology.

