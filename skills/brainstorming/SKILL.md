---
name: brainstorming
description: "Use before any creative work — a new feature, component, behavior change, or vague request — to turn intent into an approved design. Triggers: new feature, let's build, idea, design, spec, vague request, what should we build, scope, architecture, kickoff."
---

# Brainstorming into a design

Turn an idea into an agreed design before code exists. Ask one question at
a time. The artifact scales to the change — a few sentences in chat, or a
written spec — but every path ends with approval before implementation.

## Classify first

Say the classification out loud before the first question, so the user can
override it:

- **Spike** — a feasibility question ("can we...") whose output is an
  *answer*, not kept code. Present the question and what you will try in
  2–3 sentences, get a nod, investigate as cheaply as correctness allows,
  report a recommendation. Anything built stays throwaway.
- **Bounded** — a well-scoped change to a flow that already exists in this
  repo. Ask the questions that matter, present a short design in chat (a
  few sentences to a few paragraphs), then STOP.
- **Architectural** — a new project, new subsystem, or a change to
  interfaces others depend on. Follow the full path below.

When in doubt, take the heavier path. Hidden complexity upgrades the path
mid-task — stop, say so, step up. Nothing downgrades.

## HARD GATE

Before any implementation action — writing code, scaffolding, installing
dependencies, invoking an implementation skill — the selected path's
prerequisites must be complete:

- Spike: the user approved the question and probe.
- Bounded: the user approved the short design. Presenting the design and
  starting in the same breath is skipping the gate.
- Architectural: the user reviewed and approved the written spec, then the
  plan and its execution method.

Approval of one stage does not approve the next. Read-only exploration is
allowed while prerequisites are incomplete.

## The architectural path

1. **Explore context** — files, docs, recent commits, `specs/`.
2. **Ask clarifying questions** — one at a time; purpose, constraints,
   success criteria. Prefer multiple choice.
3. **Propose 2–3 approaches** — trade-offs and a recommendation, YAGNI
   ruthlessly.
4. **Present the design in sections** — scale each to its complexity (a
   few sentences, up to 200–300 words), and ask after each section
   whether it looks right.
5. **Write the spec** — `specs/<feature>/briefing.md` (and `prd.md`,
   `architecture.md` as the pipeline requires). Commit it.
6. **Self-review the spec** — placeholders, contradictions, ambiguity,
   scope. Fix inline.
7. **User reviews the written spec** — wait. Then `writing-plans`.

Design units with one purpose and a clear interface: what it does, how you
use it, what it depends on. If you cannot answer those without reading the
internals, the boundary needs work.

## Red flags

| Thought | Reality |
|---|---|
| "Too simple to need a design" | A bounded change still gets a short design and a yes. |
| "I'll call it bounded to skip the spec" | Reaching for a label to skip work is the doubt — take the heavier path. |
| "The design is obvious, I'll start while they read" | The gate is the approval, not the design's length. |
| "I understand this kind of app, so it's bounded" | Bounded measures the repo, not your familiarity. |
| "It grew, but I'm almost done" | Hidden complexity upgrades the path. Stop and say so. |
| "They approved the spike, so the change is approved" | Each task gets its own classification and approval. |

Bounded implementation proceeds through the normal workflow — TDD applies.
Spike code never graduates without being re-classified as a new request.
