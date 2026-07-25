# pipa_harness — Workflow Reference
<meta awareness="low">
All markdown files, organized by layer and pattern. This is the single map
for understanding the harness.

---

## Pattern A: Layered loading (progressive disclosure)

Only `AGENTS.md` is always-loaded. Every other file loads on demand.

```
LAYER 0   AGENTS.md              → always-loaded router
LAYER 1   rules/*.md             → path-scoped rules (git, testing, security, code-review)
LAYER 2   skills/*/SKILL.md      → trigger-loaded by keyword
LAYER 3   specs/<feature>/       → phase-driven: plan → story → build
LAYER 4   graphify-out/ + vault/ → queried memory (MCP + files)
LAYER 5   agents/*.md            → subagent definitions
LAYER 6   .harness_extension/    → project-local overrides
```

| Layer | Trigger | Example |
|-------|---------|---------|
| 0 | Always | OpenCode reads AGENTS.md first |
| 1 | Path glob touched | `git status` → rules/git-workflow.md |
| 2 | Keyword in message | "bug" → skills/debugging/SKILL.md |
| 3 | Phase invocation | @analyst → agents/analyst.md + specs/ |
| 4 | Question + graphify exists | graphify query "Auth" → graphify-out/ |
| 5 | @name mention | @dev → agents/dev.md |
| 6 | .harness_extension/ present | Project-specific rules/skills |

---

## Pattern B: Two-phase workflow

```
PHASE 1 — PLAN
  @analyst   → briefing.md
  @pm        → prd.md
  @architect → architecture.md
  @qa        → critique (loop)
PHASE 1.5 — BRIDGE
  @sm        → stories/NN-*.md
PHASE 2 — BUILD
  @dev       → implement + test
  @qa        → verify (PASS/FAIL)
```

Decision rule: Complex/multi-step → full two-phase. Trivial/single-file → skip to `@dev`.

Key invariant: Every artifact is a file. Agents hand off via `specs/` files, not chat history.

---

## Pattern C: Subagent roles

Each agent has: frontmatter (`description`, `mode`, `model`, `permission`), method (ordered steps), output (exact path + format).

| Agent | Model | Permission | Output |
|-------|-------|------------|--------|
| @analyst | deep | edit + graphify + webfetch | `specs/<feature>/briefing.md` |
| @pm | deep | edit + graphify + ls/cat | `specs/<feature>/prd.md` |
| @architect | deep | edit + graphify + grep | `specs/<feature>/architecture.md` |
| @sm | deep | edit + ls/cat + graphify | `specs/<feature>/stories/NN-*.md` |
| @dev | primary | edit + bash (ask) | implemented story + test result |
| @qa | fast | bash + git diff/status | PASS or FAIL + file:line |
| @explorer | explore | read-only grep/find | ≤50 lines, file:line refs |
| @researcher | deep | edit + webfetch | vault note + ≤5-line summary |

---

## Pattern D: Story file (self-contained build unit)

Template: `specs/STORY_TEMPLATE.md`

```markdown
# NN — <short-name>
## Context
<2-3 lines>
## Goal
<One sentence linking to feature goal>
## Acceptance criteria
- [ ] <binary, testable>
## Implementation
1. Modify `path/to/file.ts:42` — <what>
2. Create `path/to/new-file.ts` — <what>
## Test plan
- [ ] <regression test>
## Handoff packet
```yaml
task: implement
goal: <from SESSION.md>
context:
  - file:path:line
acceptance_criteria:
  - <from above>
fallback: if blocked, escalate to @architect or ask user
```
## Refs
- Architecture: `specs/<feature>/architecture.md`
- PRD: `specs/<feature>/prd.md`
- Goal: `state/SESSION.md`
```

Rule: Dev opens ONE story file and has everything. No conversation history needed.

---

## Pattern E: Rules (hard vs soft)

| Tag | Meaning | Enforcement |
|-----|---------|-------------|
| HARD | Blocking — never bypass | Agents must refuse if violated |
| SOFT | Guideline — prefer | Agents should follow, can deviate with reason |

Current rules: `rules/security.md`, `rules/code-review.md`, `rules/testing.md`, `rules/git-workflow.md`.

---

## Pattern F: Skills (trigger-loaded workflow)

| Skill | Trigger keywords | Pattern |
|-------|-----------------|---------|
| code-review | review, PR, diff | Measure (diff) → Check → Verdict |
| debugging | bug, error, crash | Reproduce → Isolate → Hypothesize → Fix → Verify |
| graphify | architecture, how does X work | Graph first → Grep second → Read sparingly |
| performance | slow, latency, optimize | Measure first → Isolate → Optimize → Verify |
| release | release, version, tag | Version bump → Update files → Verify → Tag |
| ui-ux-pro-max | design, UI, style | Design system → Domain search → Stack guidelines |

All skills follow: measure/understand → act → verify.

---

## Pattern G: Memory (two tiers)

<details>
<summary>Active (high awareness) — read at session start</summary>

- `state/SESSION.md` — current goal, active work, blockers (≤30 lines)
- `state/PLAN.md` — in-session task ledger + goal hierarchy + active loops
</details>

<details>
<summary>Passive (low awareness) — apply only when relevant</summary>

- `vault/decisions/NNN-*.md` — architectural decisions with `as_of`/`valid_until`
- `vault/research/NNN-*.md` — external findings with `as_of`/`valid_until`
- `vault/architecture/` — architecture notes
- `graphify-out/` — queryable codebase graph
</details>

Rule: Never inject passive memory wholesale. Check `as_of`/`valid_until`; expired → flag, don't apply.

---

## Pattern H: Knowledge graph (query before grep)

```
graphify query "<question>"    → BFS traversal, broad context
graphify path "A" "B"          → shortest path between two concepts
graphify explain "<Node>"      → plain-language explanation
graphify-out/GRAPH_REPORT.md   → broad review
```

Rule: For architecture questions, always try graphify first. Fall back to grep only when the graph can't answer.

---

## Pattern I: Model orchestration

All calls go through LiteLLM aliases (`config/litellm.yaml`). Never call providers directly.

| Alias | Use for |
|-------|---------|
| fast | Triage, titles, summaries, QA |
| primary | Implementation, dev agent, supervisor |
| deep | Research, planning, architect |
| explore | Read-only codebase Q&A |
| kilo-free | Free Kilo Code models |

Override via env: `LITELLM_MODEL_FAST`, `LITELLM_MODEL_PRIMARY`, etc.

---

## Pattern J: Extension model (project-local customization)

New model: `.harness_extension/` in each project (replaces deprecated `squads/`).

```
.harness_extension/
├── AGENTS.md            → project-specific router (symlinked)
├── rules/               → project-scoped rules
├── skills/              → project-specific skills
├── agents/              → project-specific subagents
├── state/               → SESSION.md + PLAN.md
└── vault/               → decisions/ + research/ + architecture/
```

Conflict priority: turn instruction > AGENTS.md > project extension > base rules/ > skills/ > vault

---

## Pattern K: Stop governor

- One tool round solves it → stop.
- 3 search rounds without progress → ask the user.
- "Done" = green build + tests pass, never "looks good".

## Pattern K.2: Handoff packet

Every agent-to-agent handoff uses this structured format:

```yaml
task: <type: explore|implement|verify|research|plan>
goal: <from SESSION.md, one sentence>
context:
  - file:path:line
  - previous_output: <2-line summary>
acceptance_criteria:
  - <binary check 1>
  - <binary check 2>
fallback: <if blocked: escalate to X, retry with Y, or ask user>
```

Why: Eliminates context loss. The receiving agent never needs chat history.

## Pattern K.3: Replan loop

When `@dev` reports an architecture blocker:
```
@dev reports BLOCKED
  ↓
@architect → update architecture.md
  ↓
@sm → update affected stories
  ↓
@qa → re-critique
  ↓
@dev → retry with new story
```

If blocker changes scope → escalate to `@pm` for scope decision.

## Pattern K.4: Parallel execution

Independent tasks run concurrently via `task` tool:
```
User: "Add blow detection + fix latency bug"
  ↓
Supervisor splits:
  Task A: @researcher → blow detection paper (task_id: research-01)
  Task B: @explorer   → latency code paths  (task_id: explore-02)
  ↓
Both run in parallel
  ↓
Supervisor aggregates → @dev implements
```

Guard: Parallel agents MUST NOT edit the same file. Check `git status` before launching.

## Pattern K.5: Harness transparency

Every agent that delegates, coordinates, or produces a final result MUST end
its output with a transparency block:

```markdown
## Harness usage
- Agents used: @explorer, @dev, @qa
- Skills loaded: debugging, code-review
- Rules applied: audio-ndk (HARD), testing (HARD)
- Tools used: graphify query, grep, git diff
- Orchestration: sequential (explorer → dev → qa), 1 parallel task
- Model routing: explore (cheapest) for search, primary for implementation, fast for verification
```

---

## Pattern L: Scratch and artifacts

- Deliverables are written in place, at their final path.
- Scratch/intermediate files go to `state/scratch/` (gitignored).
- Never leave scratch files in the repo root.

---

## Master workflow sequence (end-to-end)

```
1. User asks for something
   ↓
2. Check trivial vs complex
   ├── Trivial → @dev (skip to Phase 2)
   └── Complex → Phase 1
       ↓
3. Phase 1 (planning)
   @analyst → briefing.md
   @pm → prd.md
   @architect → architecture.md
   @qa → critique (loop)
       ↓
4. Phase 1.5 (bridge)
   @sm → stories/NN-*.md
       ↓
5. Phase 2 (building)
   For each story:
     @dev → implement
     @qa → verify (PASS / FAIL)
       ↓
6. Done = all stories pass + green build
```

### Supporting actions (woven in throughout)

| When | Action |
|------|--------|
| Architecture question | graphify query first |
| External API question | Context7 MCP resolve-library-id → query-docs |
| Code search | graphify first, grep second, read sparingly |
| Bug | skills/debugging/SKILL.md |
| Review | skills/code-review/SKILL.md |
| Memory query | vault/decisions/ or vault/research/ (on demand) |
| Session end | state/SESSION.md + decision note if architecture changed |
