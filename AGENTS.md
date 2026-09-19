# AGENTS.md — pipa_harness
<meta awareness="high">
A project-agnostic, runtime-agnostic agent harness: LiteLLM + graphify +
Obsidian, wired into OpenCode or DeepSeek Harness. This file is the
always-loaded router. Everything else loads on demand.
Detail lives in `AGENTS_OPERATIONS.md` (compaction, sandbox, tracing, todo,
repo layout — loaded on demand by planning agents).

## Philosophy
CLI First → Observability Second → UI Third. Two-phase workflow (plan → build).
File-driven context passing (`specs/` → stories). Lean by default.

## Stack
- **Runtimes** — OpenCode or DeepSeek Harness (agent runner; see `clis/`); selection in `.pipa/runtime`
- **pipa CLI** — `bin/pipa`: init, up, stop, status, runtime, triage, recall, spend, memory-gc
- **LiteLLM** — model gateway `:4000`; tiers user-assigned in the dashboard, composed into `models/.effective.yaml`
- **graphify** — persistent codebase graph; query BEFORE grep
- **Obsidian** — vault memory in `vault/` (`pipa recall` fans out over vault + memory.db + graph)

## Golden rules
- [HARD] Never commit/push unless asked.
- [HARD] Never hardcode secrets; use env vars or `{file:}`.
- [HARD] Follow existing conventions; mimic neighboring code.
- [SOFT] Early-return, short functions.
- [SOFT] Verify with project's own test/build commands.
- [SOFT] Output discipline: show outcome, not machinery.
- [SOFT] Search discipline: judge time-stability; search assumptions, not answers; cite sources.
- [SOFT] Interrupt only on genuine ambiguity/conflicts; otherwise pick the most reasonable interpretation and note it.

## HITL approval gates
Agents MUST request explicit approval for irreversible or outward-facing actions:
- `git push` — requires approval
- `git commit` — requires approval (prefer no commits unless asked)
- `rm -rf` / `rm` on tracked files — requires approval
- External data exfiltration — requires approval
- `eval()`, `exec()`, `Function()` on untrusted input — forbidden (HARD)

In OpenCode frontmatter these are `ask` rules (`allow | ask | deny`) — `ask` IS the approval gate.

## Conflict priority
turn instruction > AGENTS.md > project overlay (.pipa/) > base rules/ > skills/ > vault
User skills win over built-in skills on format.

## Two-phase workflow
```
PHASE 1 — PLAN
  @analyst → briefing.md
  @pm → prd.md
  @architect → architecture.md
  @qa → critique (loop)
PHASE 1.5 — BRIDGE
  @sm → stories/NN-*.md
PHASE 2 — BUILD
  @dev → implement + test
  @qa → verify (PASS/FAIL)
```
Trivial tasks → skip Phase 1, go straight to `@dev`.

## Routing (progressive disclosure)
Skills are listed by name + trigger only. Full SKILL.md loads on demand.
| Trigger keywords | Skill |
|-----------------|-------|
| architecture, how does X work | graphify |
| bug, error, crash | debugging |
| review, PR, diff | code-review |
| release, version, tag | release |
| latency, performance | performance |
| design, UI, style | ui-ux-pro-max |
| external library, API syntax, SDK | resolve-library-id → query-docs (never hallucinate APIs) |

> `ui-ux-pro-max` is optional — `pipa install ui-ux-pro-max` to enable.

## Agents (base)
Planning: `@analyst` `@pm` `@architect` `@qa`
Bridge: `@sm`
Build: `@dev` `@qa`
Utility: `@explorer` `@researcher`
Definitions in `agents/*.md`. Invoke with `@name` in OpenCode.

## Project overlay
Projects carry their own context in a thin `.pipa/` overlay (AGENTS.md,
rules/, memory/, skills/, agents-local/, state/) scaffolded by `pipa init`.
`.pipa/` is the only thing in a project. Uninstall: `rm -rf .pipa/ graphify-out/ && rm AGENTS.md`.

## Knowledge graph
`graphify query "<q>"`, `graphify path "A" "B"`, `graphify explain "X"`.
Fallback to grep, no error.

## Memory
Active: `state/SESSION.md` + `state/PLAN.md` (read at session start).
Passive: `vault/{decisions,research,architecture,hindsight}/` (apply when
relevant; `as_of`/`valid_until`, expired → flag). Never inject wholesale.
`pipa recall --stale` + `pipa memory-gc` keep it fresh (dry-run default).
## Model orchestration
All calls go through LiteLLM aliases — never call providers directly.
| Alias | Use for | Token cost |
|-------|---------|------------|
| `lowest` | Read-only codebase Q&A, triage | Lowest |
| `low` | Triage, QA verdicts, summaries | Low |
| `mid` | Implementation, dev agent, supervisor | Medium-High |
| `high` | Research, planning, architect | High |
| `xhigh` | Hardest reasoning, long-horizon work | Highest |

Token economy (delegate search to `@explorer`, `mid`+ for code, `high`/`xhigh`
for multi-source reasoning only) — detail in `AGENTS_OPERATIONS.md`.

## Harness transparency
Every agent that delegates, coordinates, or produces a final result MUST end
with a `## Harness usage` block (agents, skills, rules, tools,
orchestration, model routing) — exact shape in `AGENTS_OPERATIONS.md`.

## Layering
- **Layer 0 — Harness** (global, `~/.pipa-harness`): this file, rules/, skills/, agents/, models/, clis/, mcp/, tools/, dashboard/, vault/
- **Layer 1 — Project** (`.pipa/` overlay): project AGENTS.md, rules/, skills/, agents-local/, memory/, state/, specs/, tools/
- Operational detail: `AGENTS_OPERATIONS.md` (loaded on demand by planning agents)

## ask_user tool
Detail in `AGENTS_OPERATIONS.md`. Rule: genuine ambiguity on irreversible
actions only — never preferences or "looks good?" confirmations.

## Todo tool
Detail in `AGENTS_OPERATIONS.md`. Rule: track in `todowrite`, exactly one
`in_progress` while work remains.
</meta>
