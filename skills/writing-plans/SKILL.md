---
name: writing-plans
description: "Use when a spec or requirements exists for a multi-step task — before touching code — to produce the story/plan a fresh worker executes without conversation. Triggers: write a plan, break down the work, stories, tasks, implementation plan, handoff to dev, spec is ready."
---

# Writing plans

Write for a worker who has not seen this codebase or this conversation.
They write idiomatic code once they know the exact interface, the exact
test, and the exact values. Give them those. A plan is the set of decisions
the implementer cannot make alone; a plan longer than the code it describes
has written the code instead.

In pipa the plan artifact is the story file: `specs/<feature>/stories/NN-*.md`
from `specs/STORY_TEMPLATE.md`. The spec is the binding authority; the plan
argues from it.

## File structure first

Before defining tasks, map which files are created or modified and what
each is responsible for. Files that change together live together; split by
responsibility, not by layer. Follow the existing repo structure — do not
unilaterally restructure.

## Task right-sizing

A task is the smallest unit that carries its own test cycle and is worth a
fresh reviewer's gate. Fold setup, config, scaffolding, and docs into the
task whose deliverable needs them. Split only where a reviewer could reject
one task while approving its neighbor. Each task ends with an independently
testable deliverable.

## Steps are one action with a checkable result

- "Write the failing test" — step
- "Run it and watch it fail" — step
- "Implement the minimal code" — step
- "Run the tests and make them pass" — step
- "Commit" — step

Each step must let the worker write exactly one reasonable thing. A step
carries what makes it unambiguous, nothing more:

- **Test step:** the test's name and assertions as code, with the spec's
  exact values.
- **Code step:** the exact signature (name, parameters, return type), the
  file, and the spec's pinned values. The body appears only for an
  algorithm the signature and tests do not determine.
- **Verification step:** the command to run and the output that means pass.
- **Reference to another task:** point at its Interfaces block; do not
  repeat its code.

Lines that decide nothing — "TBD", "handle edge cases", "add appropriate
validation", a function no task defines — are the opposite failure.

## Header every plan needs

- **Goal** — one sentence.
- **Interfaces** per task: what it consumes from earlier tasks and produces
  for later ones (exact names, signatures, types). This is how neighboring
  tasks agree.
- **Global constraints** — version floors, dependency limits, naming and
  copy rules — copied verbatim from the spec, one line each. Every task
  implicitly includes them.
- **Review focus** — the input classes or failure modes the spec implies
  but no test exercises, most likely first. The spec's silence on an input
  is not permission for that input to break the program. Add the pinning
  test to the task that owns the code.

## Self-review before handoff

Run this yourself; do not delegate it:

1. **Spec coverage:** every requirement points at a task. List gaps.
2. **Step scan:** every step is unambiguous; no transcript of code the
   signature and tests already determine.
3. **Type consistency:** names and signatures match across tasks — a
   function called `clearLayers()` in Task 3 and `clearFullLayers()` in
   Task 7 is a bug.
4. **Review focus:** each listed failure mode has a pinning test.
5. **Proportion:** a plan several times longer than its spec is a
   transcript, not a plan.

Fix issues inline. Then hand off: `@sm` writes stories, `@dev` executes them
with `subagent-driven-development`.
