---
name: subagent-driven-development
description: "Use when executing an implementation plan or story set with independent tasks — dispatch a fresh implementer per task and a fresh review after each. Triggers: execute the plan, build the stories, orchestrate subagents, task by task, controller, delegation loop, run the pipeline."
---

# Subagent-driven development

Execute a plan by dispatching a fresh implementer per task, a task review
after each, and one broad review at the end. Fresh context per task is the
point: the implementer sees exactly what it needs, and your context stays
clean for coordination.

In pipa: controller = the session that owns the plan; implementer =
`@dev` via `task`; reviewer = `@qa` via `task`. `@dev` may not spawn
subagents (its permissions deny `task`), and neither should you ask it to —
review arrives from you, after the report.

## Setup

1. **Read the spec and the story set once.** The spec is the binding
   authority; the plan is its argument. Note global constraints.
2. **Ledger.** Conversation memory does not survive compaction; a ledger
   does. Write it to `.pipa/state/sdd/<plan-stem>.md` (project overlay), or
   beside the stories when the project has no `.pipa/`. First line:
   `# SDD ledger — plan: <path>`. Append a line per event below. After
   compaction, trust the ledger and `git log` over your recollection —
   controllers without one have re-dispatched entire completed sequences.
3. **Pre-flight conflict scan.** One row per pair of tasks sharing a file
   or interface: what one produces vs what the other consumes. One row per
   task: does its own text agree with itself? Write the table to the
   ledger. Rule on conflicts before execution starts: `Ruling: <what> —
   <why> — <cost if wrong>`. The per-task review is the net for what only
   surfaces in implementation.

## Per task

1. Record `BASE` (`git rev-parse HEAD`).
2. Dispatch `@dev` with: where the task fits (one line), the story path
   ("read this first — its values are exact"), interfaces from earlier
   tasks, your resolution of ambiguity, and the report contract. Never
   paste accumulated history into a dispatch; a fresh agent needs its task,
   its interfaces, and the constraints.
3. Handle the report status: `done` → review; `partial` → read the note,
   resolve scope/correctness questions before review; `blocked` → missing
   context gets supplied, too-large gets split, a plan defect gets a ruling
   and a corrected dispatch; `failed` → do not silently retry the same
   model. Never mark done on an unverified claim.
4. Review with `@qa`, two stages in order: **spec compliance** (every
   acceptance criterion, `file:line` evidence) then **quality** (tests
   assert real behavior, minimal diff, no YAGNI, no drive-by changes).
   Hand the reviewer the story path, the report, the diff (as a file or
   `git diff BASE..HEAD`), and the binding constraints. Never tell a
   reviewer what not to flag.
5. **Fix loop, max 3 rounds.** Send open findings verbatim to the same
   `@dev` (resume its session when the harness allows; otherwise a fresh
   dispatch with the story and report paths). Each round ends with a
   scoped re-review of the fix diff only, marking each finding ADDRESSED /
   NOT ADDRESSED and flagging new breakage in the changed hunks. New
   findings on untouched code go to the ledger, not the loop.
6. **Rulings, not stalls.** A running plan does not wait on a human.
   Conflicts, ambiguities, plan defects — decide, ledger the ruling, keep
   going. Four things stop you, and only these: an irreversible or
   destructive operation; a security-sensitive action; a side effect
   outside the workspace norms say to ask about (merge, push to a shared
   branch, publish); a plan so broken every path forward is a guess.
7. **Breaker.** When round 3 still leaves findings open, adjudicate each
   one yourself — you hold the cross-task context the reviewer lacks.
   Park with a ruling, or rule on the smallest change that unblocks
   dependents and carry it into the next dispatch. Every adjudication is a
   ledger entry; a silent discard is forbidden.

Ledger lines:

```
Task 3: complete (commits a1b2c3d..d4e5f6a, review clean)
Task 3: fix round 1/3 (2 addressed, 0 open; commits d4e5f6a..b7c8d9e)
Task 3: parked — <finding> — Ruling: <why the code stands>
Task 3: minor (deferred): <one-liner>
```

## Final review

One whole-branch review on the most capable tier the task warrants, pointed
at the ledger's deferred-minor and parked lines so it can triage. If it
returns findings, dispatch ONE fix subagent with the complete list — not
one per finding — then one scoped re-review. Adjudicate residuals like the
breaker; there is no second fix wave. Collect every `Ruling:` line into
your final message under "Rulings I made" — that list is the only place
decisions made on the user's behalf reach them.

## Efficiency rules

- **Model tiers:** cheapest tier for transcription-style tasks whose plan
  text contains the code; mid tier for prose-described implementation and
  reviewers; most capable for final review and architecture. Specify the
  tier per dispatch — never inherit the session default silently. Turn
  count beats token price: a cheap model taking 2–3× the turns costs more.
- **Batch same-shape work:** several one-line edits of the same kind are
  one dispatch to one agent, reviewed as one unit.
- **Artifacts as files:** reports, diffs, and briefs travel as paths.
  Anything pasted into a dispatch stays resident in your context forever.
- **Never two writers in parallel.** Read-only exploration may run in
  parallel; implementations may not.
- **Never fix findings yourself in the controller.** Your context stays
  clean, and controller fixes skip review.

## Rationalizations

| Excuse | Reality |
|---|---|
| "Close enough on spec" | A spec gap is not done. Fix it or hit the cap and adjudicate. |
| "I'll fix it myself, dispatching is overhead" | Controller fixes skip review and pollute coordination context. |
| "One more round will converge" | Past the cap, failures are structural. Adjudicate and route. |
| "The fix was small, skip the re-review" | Unreviewed fixes are how regressions land. |
| "The reviewer is obviously wrong, I'll drop it" | You adjudicate only at the cap; silent discards are forbidden. |
| "Ledger bookkeeping is overhead" | The ledger is what survives compaction. |
| "The worker spawned its own reviewer" | A duplicate review seat, not rigor. The task review is the gate. |
