# AGENTS.md — pipa_harness
<meta awareness="high">
A project-agnostic, runtime-agnostic agent harness: LiteLLM + graphify +
Obsidian, wired into OpenCode or DeepSeek Harness. This file is the
always-loaded router. Everything else loads on demand.

## Philosophy
CLI First → Observability Second → UI Third. Two-phase workflow (plan → build).
File-driven context passing (`specs/` → stories). Lean by default.

## Stack
- **Runtimes** — OpenCode or DeepSeek Harness (agent runner; see `clis/`)
- **pipa CLI** — `bin/pipa` (Python, `pipa/` package): init, up, stop, status, runtime, migrate, hook, eval
- **LiteLLM** — model gateway `:4000`; model lists discovered live from providers (cached in `state/model_catalog.json`) and composed into `models/.effective.yaml` (shared by all runtimes)
- **graphify** — persistent codebase graph; query BEFORE grep
- **Obsidian** — vault memory in `vault/`

## Runtimes
The harness is runtime-agnostic: AGENTS.md, rules/, skills/, agents/ are pure
markdown consumed by any runtime. Per-project selection lives in
`.pipa/runtime` (`opencode` | `deepseek-harness`).
- `pipa runtime list|show|set <name>` — inspect/switch runtimes
- CLI config templates: `clis/<name>/` (opencode global.jsonc / dsh cordis.patch.yml); wiring is machine-global (~/.config/opencode, ~/.dsh)
- Both runtimes share the LiteLLM gateway and the NDJSON session log at
  `.pipa/state/session.log.ndjson` (OpenCode via `pipa hook`; dsh sessions
  live separately under `~/.dsh/sessions/`).

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

In OpenCode frontmatter these are expressed as `"git push": ask` /
`"git commit": ask` — OpenCode permission actions are only
`allow | ask | deny`, and `ask` IS the approval gate.

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

## Agents (base)
Planning: `@analyst` `@pm` `@architect` `@qa`
Bridge: `@sm`
Build: `@dev` `@qa`
Utility: `@explorer` `@researcher`
Definitions in `agents/*.md`. Invoke with `@name` in OpenCode.

## Project overlay
Projects carry their own context in a thin `.pipa/` overlay (AGENTS.md,
rules/, memory/, skills/, agents-local/, state/) scaffolded by `pipa init`.
The legacy `.pipa/extension/` and `.harness_extension/` layouts are still read
for compatibility but created by nothing; `pipa migrate` converts them.
Conflict priority: project overlay (.pipa/) > base.

## Knowledge graph
`graphify query "<q>"`, `graphify path "A" "B"`, `graphify explain "X"`.
Fallback to grep, no error.

## Library API docs
`resolve-library-id` → `query-docs` for external libraries. Prevents hallucinated APIs.

## Memory
<details>
<summary>Active (high awareness) — read at session start</summary>

- `state/SESSION.md` — current goal, active work, blockers (≤30 lines)
- `state/PLAN.md` — in-session task ledger + goal hierarchy + active loops
</details>

<details>
<summary>Passive (low awareness) — apply only when relevant</summary>

- `vault/decisions/` — architectural decisions with `as_of`/`valid_until`
- `vault/research/` — external findings with `as_of`/`valid_until`
- `vault/architecture/` — architecture notes
- `graphify-out/` — queryable codebase graph
</details>

**Rule:** Never inject passive memory wholesale. Check `as_of`/`valid_until`; expired → flag, don't apply.

**One-query access:** `pipa recall "<query>"` fans out over the vault,
memory.db and the code graph with expiry-aware ranking — prefer it over
manual greps when hunting prior decisions.

## Memory store (structured recall)
- **Index:** `tools/memory_store/index_vault.py` — indexes `vault/*.md` into `state/memory.db`.
- **Query:** `tools/memory_store/query.py "<query>"` — returns matching notes with scope, dates, status.
- **Why:** Flat markdown is human-readable but slow to query. SQLite adds scoped recall without changing the vault format.

## Artifacts & scratch
- Deliverables: final path, tagged.
- Scratch: `state/scratch/` (gitignored). Never in repo root.

## Model orchestration
All calls go through LiteLLM aliases — never call providers directly.
Tiers are user-assigned in the dashboard (Models page); agents pick a tier.
| Alias | Use for | Token cost |
|-------|---------|------------|
| `lowest` | Read-only codebase Q&A, triage | Lowest |
| `low` | Triage, QA verdicts, summaries | Low |
| `mid` | Implementation, dev agent, supervisor | Medium-High |
| `high` | Research, planning, architect | High |
| `xhigh` | Hardest reasoning, long-horizon work | Highest |
Scripts: `tools/litellm/task.sh <alias> "<prompt>"`.

### Token-saving rules
- Delegate search to `@explorer` instead of reading files.
- Use `@qa` for binary verdicts, not reasoning.
- Reserve `mid`+ for code/decisions/coordination.
- Reserve `high`/`xhigh` for multi-source reasoning only.
- Never run `xhigh` for simple lookups.

## Context compaction
- **Budget:** Keep agent context under 50% of the model's window. The rest is reserved for the user message + tool results.
- **Compression:** If tool results exceed 200 lines, summarize them before adding to context. Use `compress_tool_results` in LiteLLM settings.
- **Summaries:** After 3+ tool calls, generate a rolling summary of what was found. Inject the summary + last 2 turns into the next prompt, not the full history.
- **Token counting:** Before running an agent, estimate the token cost of the prompt. If it exceeds the budget, compress or split the task.

## Stop governor
- One tool round solves it → stop.
- 3 search rounds without progress → ask the user.
- "Done" = green build + tests pass, never "looks good".

## Truth & spend planes
- **Session bus:** every runtime appends to `<project>/.pipa/state/session.log.ndjson`
  (canonical contract: `docs/SESSION_BUS.md`, enforced by `tests/test_hooks_schema.py`).
- **Flight recorder:** `pipa replay [SID]` · `pipa diff A B` — cross-runtime replay/compare.
- **Spend ledger:** the LiteLLM gateway logs metadata-only usage rows to
  `state/spend.ndjson`; inspect with `pipa spend [--since TS] [--json]`.
- **Conformance:** `tests/test_conformance_*.py` pin runtime config contracts
  (gateway aliases, dsh patch schema, opencode jsonc) — run before changing clis/, models/ or mcp/.

## Concurrent execution
Run independent tasks in parallel via `task` tool with unique `task_id`s.
Guard: parallel agents MUST NOT edit the same file. Check `git status` first.

## Conflict resolution
1. `@explorer` presents evidence (`file:line` refs).
2. `@researcher` presents external evidence (citations).
3. Orchestrator (or user) decides based on goal alignment.
4. Stalemate → escalate to user with both positions.

## Harness transparency
Every agent that delegates, coordinates, or produces a final result MUST end
with:
```markdown
## Harness usage
- Agents used: @explorer, @dev, @qa
- Skills loaded: debugging, code-review
- Rules applied: security (HARD), testing (HARD)
- Tools used: graphify query, grep, git diff
- Orchestration: sequential (explorer → dev → qa), 1 parallel task
- Model routing: lowest (cheapest) for search, mid for implementation, low for verification
```

## ask_user tool
Use `ask_user` only for:
- Genuine ambiguity where the next action is irreversible
- Conflicting instructions that can't be resolved by priority rules
- Missing critical information that blocks progress

Do NOT use for:
- Preferences that don't affect correctness
- "Looks good?" confirmations — just do the work
- Re-stating what the user already said

## Sandbox model
- `/tmp` — ephemeral workspace for scratch, temp files, experiments. Wiped between sessions.
- `/mnt/agents` (project root) — persistent workspace for deliverables, state, vault. Code must not die in `/tmp`.
- Rule: never put deliverables in `/tmp`; never leave scratch in project root.

## Todo tool
Use `todowrite` for structured task tracking. Read it at session start; update after each step.
Format: `content`, `priority` (high/medium/low), `status` (pending/in_progress/completed/cancelled).
Rule: keep exactly one `in_progress` while work remains.

## Observability (optional, opt-in)
- **Traces:** Each agent run can emit a trace span: agent name, model alias, token count, latency, tools called. Stored in SQLite (`state/traces.db`) or exported to OTel collector.
- **Enable:** Set `PIPA_TRACING=1` in env. Use `tools/tracing.py start|end|export`.
- **Why:** Enables debugging latency, token usage, and failure modes without manual log inspection.

## Repo layout
`AGENTS.md` (router) · `pipa/` (Python CLI + core lib) · `clis/` (per-runtime
config + templates: opencode, deepseek-harness) · `rules/` (path-scoped) ·
`skills/` (trigger-loaded) · `agents/` (subagents) · `specs/` (plan→story) ·
`bin/pipa` (entrypoint) · `models/` (LiteLLM settings; model lists discovered
from providers into state/, composed to `.effective.yaml`) · `mcp/` (integration registry, one folder per server)
· `dashboard/` (modular pages+fragments UI) · `install/` (Makefile + steps)
· `tools/` (evals, litellm, memory_store, ollama) · `vault/` (memory) ·
`state/` (session, ledger, registry; gitignored) · `graphify-out/` (gitignored)

Per-project layout (created by `pipa init`, thin overlay only):
`.pipa/runtime` (selected runtime) · `.pipa/AGENTS.md` (project facts,
symlinked from root) · `.pipa/rules/` · `.pipa/memory/` · `.pipa/skills/`
(optional, overrides global) · `.pipa/agents-local/` (project agents, exposed
to opencode via symlink) · `.pipa/state/` (session log, traces, memory.db;
gitignored) — runtime configs are machine-global and never live in projects.
Legacy `.pipa/extension/` and `.harness_extension/` layouts are still read for
compatibility; `pipa migrate` converts them.
