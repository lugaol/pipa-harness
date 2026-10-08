---
as_of: 2026-10-04
valid_until: 2026-11-04
status: active
---
<meta awareness="low">
# Research — What pipa adopted from obra/superpowers

- **Question:** What in https://github.com/obra/superpowers is worth
  extracting into pipa_harness, given the earlier finding that repository
  overviews are inert and only *non-standard practice* benefits from
  context files? What was rejected and why?

## Adopted (where it lives now)

| Superpowers practice | pipa artifact |
|---|---|
| Skills are TDD for process docs; iron law "no skill without a failing test first"; baseline pressure scenario before writing | `skills/writing-skills/SKILL.md` |
| Description = triggering conditions only, never a workflow summary (tested: a workflow-summarizing description collapsed a two-review process to one) | `skills/writing-skills/SKILL.md` + enforced name/dir/trigger gates in `bin/pipa-check skills` |
| Match the form to the failure: prohibition + rationalization table for discipline; positive recipe for output shape; no nuance/exemption clauses | `skills/writing-skills/SKILL.md` |
| Micro-test wording: no-guidance control, 5+ reps, read every flagged match, variance is a metric | `skills/writing-skills/SKILL.md` |
| RED-GREEN-REFACTOR with "delete code written before its test" | `skills/test-driven-development/SKILL.md`, `agents/dev.md` |
| "Evidence before claims"; agent success reports verified against the diff | `skills/verification-before-completion/SKILL.md`, `agents/dev.md` (`verified:true` = ran it this session) |
| Four-phase root-cause process; instrumentation at component boundaries; 3+ failed fixes = question the architecture; defense-in-depth; condition-based waiting | `skills/debugging/SKILL.md` (upgraded) |
| Spike / bounded / architectural classification with a hard approval gate | `skills/brainstorming/SKILL.md` |
| Bite-sized steps with exact values, interfaces block, review-focus, plan self-review ("a plan longer than the code it describes has written the code") | `skills/writing-plans/SKILL.md`, `agents/sm.md` story quality bar |
| Fresh subagent per task, durable ledger across compaction, task review = spec compliance then quality, scoped re-review of the fix diff, 3-round cap then adjudicate, **rulings not stalls**, one fix wave at final review, four stop conditions | `skills/subagent-driven-development/SKILL.md`, `agents/qa.md` |
| Receiving review with technical rigor, not performative agreement | `skills/code-review/SKILL.md` |
| The eval-lab idea: measure workflow compliance against a no-skill control arm, three-valued verdict | already present as `tools/evals/run.py` + pipa's three-valued `pipa-check`; no new lab built |

## Rejected

- **The full ceremony** (brainstorm gate on every action, worktrees per
  change, one subagent per same-shape task): process tax the earlier
  research does not support. Adopted only the non-standard discipline.
- **Vendoring the skills themselves** (15 skills × 15 harness plugins):
  duplicates pipa's own; the *method* was extracted, not the text.
- **Live eval lab (quorum)**: Docker + `--dangerously-skip-permissions` +
  two LLMs per run — not worth replicating here.
- **Default-on telemetry**: rejected; pipa stores nothing implicit.
- **GitHub-star count as evidence**: superpowers-evals exists precisely
  because skill behavior needs measuring.

## Sources

- https://github.com/obra/superpowers (README, 295k★, MIT, 2026-10-04)
- `skills/writing-skills/SKILL.md`, `skills/test-driven-development/SKILL.md`,
  `skills/systematic-debugging/SKILL.md`, `skills/brainstorming/SKILL.md`,
  `skills/writing-plans/SKILL.md`, `skills/subagent-driven-development/SKILL.md`,
  `skills/verification-before-completion/SKILL.md`,
  `skills/receiving-code-review/SKILL.md`
- https://github.com/prime-radiant-inc/superpowers-evals (quorum eval lab)
- Vault: `2026-10-03-ai-agent-context-generators.md` (why overviews are inert)
