---
name: writing-skills
description: "Use when creating, editing, or verifying a skill in skills/ — before deploying it. Triggers: new skill, write a skill, edit SKILL.md, skill not triggering, skill ignored, improve a skill, skill authoring."
---

# Writing skills

**Writing skills is TDD applied to process documentation.** If you did not
watch an agent fail without the skill, you do not know the skill teaches
the right thing.

## The Iron Law

```
NO SKILL WITHOUT A FAILING TEST FIRST
```

Applies to new skills and edits alike. Write the skill before testing?
Delete it and start over — same as production code.

## RED-GREEN-REFACTOR

- **RED** — Run a pressure scenario against a fresh subagent *without* the
  skill. Record what it did wrong and the exact rationalizations it used,
  verbatim. If the baseline does not fail, there is nothing to fix — stop.
- **GREEN** — Write the minimal skill that addresses those specific
  failures. Run the same scenario with the skill present; the agent must
  now comply.
- **REFACTOR** — Find the next rationalization, add an explicit counter,
  re-test. Repeat until bulletproof.

For technique, pattern, and reference skills, the test is application:
can an agent use the skill correctly on a new scenario, find the right
reference, handle edge cases? For discipline skills (rules under
pressure), the test is compliance under combined pressure (time, sunk
cost, exhaustion).

## Micro-test the wording first

Full pressure runs are slow. Before them:

1. One fresh-context sample per call; the system prompt should be the
   realistic context the guidance will live in, not the sentence alone.
2. **Always include a no-guidance control.** If the control does not
   exhibit the failure, do not author the guidance.
3. 5+ reps per variant — single samples lie.
4. Read every flagged match manually; automated counts overstate both
   failure and success.
5. Variance is a metric: five interpretations across five reps means the
   wording is not binding — tighten the form before adding words.

## Description = when to use, never what it does

The description is the only thing the agent reads to decide whether to
load the skill. It answers "should I read this right now?"

```yaml
# bad: summarizes the workflow — agents follow this and skip the body
description: Executes plans by dispatching a subagent per task with review between tasks

# bad: first person, no trigger
description: I can help you with async tests

# good: triggering conditions only
description: "Use when executing implementation plans with independent tasks. Triggers: execute the plan, task by task, orchestration."
```

This was found empirically: a description summarizing "code review between
tasks" made agents do ONE review even though the body's flow showed two
(spec compliance, then quality). Workflow summaries become shortcuts the
agent takes; the body becomes documentation nobody reads.

Use concrete triggers, symptoms, error strings, synonyms, and tool names.
Third person. Keep it under 1024 chars; aim for under 500. `pipa-check
skills` enforces name/directory match and the presence of trigger words —
it cannot judge this rule. That judgment is yours.

## Match the form to the failure

The form that bulletproofs one failure type backfires on another:

| Baseline failure | Right form | Wrong form |
|---|---|---|
| Skips a rule under pressure (knows better) | Prohibition + rationalization table + red flags | Soft guidance ("prefer", "consider") |
| Output has the wrong shape | Positive recipe: state what the output IS, its parts, in order | Prohibition list ("don't restate", "never narrate") |
| Omits a required element | Structural: a REQUIRED slot in the template they fill in | Prose reminders beside the template |
| Behavior depends on a condition | Conditional keyed to an observable predicate | Unconditional rule + exemption clauses |

**Prohibitions backfire on shaping problems.** Under a competing incentive,
agents negotiate with "don't X"; a recipe leaves nothing to negotiate.
Wording tests on dispatch-prompt guidance: the prohibition arm produced
more unwanted content than even the no-guidance control. Micro-test your
own case rather than assuming, but never reach for the prohibition by
default.

- **No nuance clauses.** "Don't X unless it matters" reopens the
  negotiation. A real exception is its own conditional on an observable
  predicate.
- **Exemption clauses don't scope.** "This limit does not apply to code
  blocks" still suppresses code blocks. Restructure so the rule cannot
  reach the exempt output.

## Bulletproofing discipline skills

Close every loophole explicitly. Do not merely state the rule — forbid the
specific workarounds:

```
Write code before test? Delete it. Start over.

No exceptions:
- Don't keep it as "reference"
- Don't "adapt" it while writing tests
- Don't look at it
```

Build the rationalization table from actual baseline transcripts (every
excuse observed goes in). Add a red-flags list so the agent can self-check
mid-rationalization. Add "violating the letter is violating the spirit" to
cut off the whole "spirit not letter" class.

## Token economy

- Metadata is loaded every session: keep it ~100 tokens.
- Body under ~500 lines / 5k tokens; references one level deep.
- Move details behind `--help` or reference files; cross-reference other
  skills by name instead of repeating them. Never use `@`-style force
  links — they burn context before the skill is needed.
- One excellent runnable example beats five mediocre ones. No
  multi-language dilution.
- **If a constraint is mechanically checkable, automate it instead**
  (`bin/pipa-check`) and keep the skill for judgment calls. This skill is
  the judgment half; `pipa-check skills` is the mechanical half.

## Checklist

RED:
- [ ] Pressure/application scenario run without the skill; failures and
  rationalizations recorded verbatim
- [ ] No-guidance control exhibited the failure

GREEN:
- [ ] `name` matches the directory, `[a-z0-9-]`, ≤64 chars
- [ ] `description` is triggers only (no workflow summary), third person
- [ ] Addresses the specific baseline failures
- [ ] Form matches the failure type (table above)
- [ ] Wording micro-tested where the guidance shapes behavior
- [ ] Scenario re-run with the skill: agent complies

REFACTOR:
- [ ] New rationalizations countered; table and red flags updated
- [ ] `bin/pipa-check skills` passes
