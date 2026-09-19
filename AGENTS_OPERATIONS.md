# AGENTS_OPERATIONS.md — operational detail for planning agents

Loaded on demand by agents that need it. Not part of the always-loaded router.

## Context compaction

- **Budget:** Keep agent context under 50% of the model's window. The rest is reserved for the user message + tool results.
- **Compression:** If tool results exceed 200 lines, summarize them before adding to context. Use `compress_tool_results` in LiteLLM settings.
- **Summaries:** After 3+ tool calls, generate a rolling summary of what was found. Inject the summary + last 2 turns into the next prompt, not the full history.
- **Token counting:** Before running an agent, estimate the token cost of the prompt. If it exceeds the budget, compress or split the task.

## Stop governor

- One tool round solves it → stop.
- 3 search rounds without progress → ask the user.
- "Done" = green build + tests pass, never "looks good".

## Todo tool

Use `todowrite` for structured task tracking. Read it at session start; update after each step.
Format: `content`, `priority` (high/medium/low), `status` (pending/in_progress/completed/cancelled).
Rule: keep exactly one `in_progress` while work remains.

## Sandbox model

- `/tmp` — ephemeral workspace for scratch, temp files, experiments. Wiped between sessions.
- `/mnt/agents` (project root) — persistent workspace for deliverables, state, vault. Code must not die in `/tmp`.
- Rule: never put deliverables in `/tmp`; never leave scratch in project root.

## Concurrent execution

Run independent tasks in parallel via `task` tool with unique `task_id`s.
Guard: parallel agents MUST NOT edit the same file. Check `git status` first.

## Conflict resolution

1. `@explorer` presents evidence (`file:line` refs).
2. `@researcher` presents external evidence (citations).
3. Orchestrator (or user) decides based on goal alignment.
4. Stalemate → escalate to user with both positions.

## ask_user tool

Use `ask_user` only for:
- Genuine ambiguity where the next action is irreversible
- Conflicting instructions that can't be resolved by priority rules
- Missing critical information that blocks progress

Do NOT use for:
- Preferences that don't affect correctness
- "Looks good?" confirmations — just do the work
- Re-stating what the user already said

## Observability (optional, opt-in)

- **Traces:** Each agent run can emit a trace span: agent name, model alias, token count, latency, tools called. Stored in SQLite (`state/traces.db`) or exported to OTel collector.
- **Enable:** Set `PIPA_TRACING=1` in env. Use `tools/tracing.py start|end|export`.
- **Why:** Enables debugging latency, token usage, and failure modes without manual log inspection.

## Truth & spend planes

- **Session bus:** every runtime appends to `<project>/.pipa/state/session.log.ndjson`
  (canonical contract: `docs/SESSION_BUS.md`, enforced by `tests/test_hooks_schema.py`).
- **Flight recorder:** `pipa replay [SID]` · `pipa diff A B` — cross-runtime replay/compare.
- **Spend ledger:** the LiteLLM gateway logs metadata-only usage rows to
  `state/spend.ndjson`; inspect with `pipa spend [--since TS] [--json]`.
- **Conformance:** `tests/test_conformance_*.py` pin runtime config contracts
  (gateway aliases, dsh patch schema, opencode jsonc) — run before changing clis/, models/ or mcp/.

## Repo layout

`AGENTS.md` (router) · `AGENTS_OPERATIONS.md` (this file) · `pipa/` (CLI + core lib) ·
`clis/` (per-runtime config: opencode, deepseek-harness) · `rules/` (path-scoped) ·
`skills/` (trigger-loaded) · `agents/` (subagents) · `specs/` (plan→story) ·
`bin/pipa` (entrypoint) · `models/` (LiteLLM settings; model lists discovered
from providers into state/, composed to `.effective.yaml`) · `mcp/` (integration registry) ·
`dashboard/` (5-page UI) · `install/` (Makefile + steps) · `tools/` (evals, litellm, memory_store, ollama) ·
`vault/` (memory) · `state/` (session, ledger, registry; gitignored) · `graphify-out/` (gitignored)

Per-project layout (created by `pipa init`, thin overlay only):
`.pipa/runtime` (selected runtime) · `.pipa/AGENTS.md` (project facts,
symlinked from root) · `.pipa/rules/` · `.pipa/memory/` · `.pipa/skills/`
(optional, overrides global) · `.pipa/agents-local/` (project agents, exposed
to opencode via symlink) · `.pipa/state/` (session log, traces, memory.db;
gitignored) — runtime configs are machine-global and never live in projects.

## Token economy

- Delegate search to `@explorer` instead of reading files yourself.
- Use `@qa` for binary verdicts, not reasoning.
- Reserve `mid`+ for code/decisions/coordination.
- Reserve `high`/`xhigh` for multi-source reasoning only.
- Never run `xhigh` for simple lookups.

## Memory store (structured recall)

- **Index:** `tools/memory_store/index_vault.py` — indexes `vault/*.md` into `state/memory.db`.
- **Query:** `tools/memory_store/query.py "<query>"` — matching notes with scope, dates, status.
- **Why:** flat markdown is human-readable but slow to query; SQLite adds scoped recall without changing the vault format.

## Approval-gate frontmatter mapping

- OpenCode permission actions are only `allow | ask | deny`; `ask` IS the approval gate.
- Express every HITL gate as `"<action>": ask` in agent frontmatter (`git push`, `git commit`, `rm` on tracked files, exfiltration).
- `eval()`/`exec()`/`Function()` on untrusted input: `deny` (forbidden, HARD).

## Harness usage block (exact shape)

```markdown
## Harness usage
- Agents used: @explorer, @dev, @qa
- Skills loaded: debugging, code-review
- Rules applied: security (HARD), testing (HARD)
- Tools used: graphify query, grep, git diff
- Orchestration: sequential (explorer → dev → qa), 1 parallel task
- Model routing: lowest (cheapest) for search, mid for implementation, low for verification
```
