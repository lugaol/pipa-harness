# AGENTS.md — pipa_harness
A project-agnostic agent harness built on OpenCode + LiteLLM + graphify +
Obsidian, orchestrated with emdash. This file is the always-loaded router.
## Philosophy (adapted from aiox-core, lean)
- **CLI First → Observability Second → UI Third.** The CLI is the source of
  truth. New features must work 100% via CLI before any UI. Dashboards only
  *observe* what the CLI does — they never control it.
- **Two-phase workflow.** Planning (analyst→pm→architect) produces a spec;
  the scrum master turns the spec into self-contained stories. Build agents
  open a story file with complete context — no conversation loss.
- **File-driven context passing.** Agents hand off via files (`specs/` →
  stories), not chat history. This eliminates context loss across sessions.
- **Lean by default.** No engines, no epics, no orchestration frameworks.
  Markdown files + subagents + git. That's the whole system.
## Stack
- **OpenCode** — interactive/headless coding agent (TUI + `opencode run`).
- **LiteLLM** — model gateway at `http://localhost:4000`. All model names
  (`primary`, `fast`, `deep`, `explore`) are aliases in `config/litellm.yaml`.
- **graphify** — persistent knowledge graph. Query BEFORE grepping.
- **Obsidian** — this harness is a vault; memory lives in `vault/`.
- **emdash** — parallel agent orchestration via git worktrees.
## Golden rules
- [HARD] Never commit or push unless the user explicitly asks.
- [HARD] Never hardcode secrets/API keys. Use env vars or `{file:}`.
- [HARD] Follow existing conventions; mimic neighboring code.
- [SOFT] Prefer early-return and short functions in new code.
- [SOFT] Verify with the project's own test/build commands before "done".
- [SOFT] Output discipline: show the outcome, not the machinery. Don't
  narrate compliance ("I will now follow rule X") — just do the work.
- [SOFT] Search discipline: judge time-stability before searching — answer
  stable facts from knowledge, search only what's volatile. Search to verify
  assumptions, not to fish for answers; cite sources inline for searched facts.
- [SOFT] Interrupt the user only on genuine ambiguity, conflicting
  instructions, or irreversible/outward-facing actions. Otherwise pick the
  most reasonable interpretation, proceed, and note the assumption.
## Conflict priority
turn instruction > AGENTS.md > project extension > base rules/ > skills/ > vault
On overlap, the project extension wins over base files. User skills win over
built-in skills on format.
## Two-phase workflow
```
PHASE 1 — PLAN (produce a spec)
  @analyst   → research + briefing       → specs/<feature>/briefing.md
  @pm        → requirements + PRD         → specs/<feature>/prd.md
  @architect → technical design          → specs/<feature>/architecture.md
  @qa        → critique spec             → (feedback loop)
PHASE 2 — BUILD (consume stories)
  @sm        → spec → detailed stories   → specs/<feature>/stories/*.md
  @dev       → implement one story        → code + regression test
  @qa        → review build + verify      → pass/fail verdict
```
Each story file is self-contained: context, acceptance criteria, implementation
notes, file refs. The dev agent reads ONE file and has everything it needs.
For small/trivial tasks, skip Phase 1 — go straight to `@dev`.
## Routing (load ONLY when the trigger matches)
Progressive disclosure: this table is all you get upfront. Never load a skill
whose trigger didn't fire; never read a rule file outside the path glob you
touched. Full SKILL.md content loads on demand, per task stage.
| Task involves...                       | Load                                  |
|----------------------------------------|---------------------------------------|
| architecture, "how does X work"        | skills/graphify/SKILL.md              |
| debugging, bug, error, crash            | skills/debugging/SKILL.md             |
| code review, PR, diff                  | skills/code-review/SKILL.md           |
| release, version, tag, changelog       | skills/release/SKILL.md               |
| latency, performance, profiling        | skills/performance/SKILL.md           |
| UI/UX design, styling, design system   | skills/ui-ux-pro-max/SKILL.md         |
## Agents
**Planning** (Phase 1): `@analyst` `@pm` `@architect`
**Bridge**: `@sm` (spec → stories)
**Build** (Phase 2): `@dev` (was implementer) `@qa` (was verifier)
**Utility**: `@explorer` `@researcher`
See `agents/*.md` for definitions. Invoke with `@name` in OpenCode.
## Project extensions
Include project-specific rules, skills, and AGENTS.md snippets via:
```bash
harness/bin/pipa-extend.sh /path/to/your-project-extension
```
Extension bundles live in `squads/projects/<name>/` and are merged on top of
the base harness. See "Project extensions" in README.md.
## Knowledge graph — query BEFORE reading files
`graphify query "<q>"`, `graphify explain "<Node>"`, `graphify path "A" "B"`.
Broad review: `graphify-out/GRAPH_REPORT.md`. Fallback to grep, no error.
## Library API docs — Context7 MCP
Use `resolve-library-id` → `query-docs` for any external library. Prevents
hallucinated APIs, saves tokens vs reading full source.
## Memory (two tiers)
- **ACTIVE** (`<meta awareness="high">`): `state/SESSION.md` + `state/PLAN.md`.
  Read at session start; PLAN.md doubles as the structured task ledger for
  multi-step work — keep it current as you go.
- **PASSIVE** (`<meta awareness="low">`): `vault/decisions/`, `vault/research/`.
  Queried on demand, never injected wholesale. Apply only when relevant to the
  current task; check `as_of`/`valid_until` frontmatter before citing —
  expired → flag, don't apply.
- Session end: update SESSION.md (≤30 lines); write a decision note if
  architecture changed.
## Artifacts & scratch
- Deliverables are written in place, at their final path.
- Scratch/intermediate files go to `state/scratch/` (gitignored) — never leave
  them in the repo root or mix them into the deliverable diff.
## Scheduled tasks (optional)
No framework: schedule `bin/litellm-task.sh <alias> "<prompt>"` via OS
cron/launchd when a recurring check is needed. The CLI stays the source of
truth.
## Model orchestration
All calls go through LiteLLM aliases — never call providers directly.
| Alias    | Use for                          |
|----------|----------------------------------|
| `fast`   | triage, titles, summaries        |
| `primary`| implementation, dev agent         |
| `deep`   | research, planning, architect    |
| `explore`| read-only codebase Q&A            |
Scripts: `bin/litellm-task.sh <alias> "<prompt>"`.
Override via env: `LITELLM_MODEL_FAST`, `LITELLM_MODEL_PRIMARY`, etc.
## Stop governor
- One tool round solves it → stop.
- 3 search rounds without progress → ask the user.
- "Done" = green build + tests pass, never "looks good".
## Repo layout
`AGENTS.md` (router) · `rules/` (path-scoped) · `skills/` (trigger-loaded) ·
`agents/` (subagents) · `specs/` (plan→story workflow) · `bin/` (wrappers) ·
`config/` (LiteLLM + OpenCode) · `vault/` (dated memory) · `state/` (session) ·
`squads/` (project extensions + domain bundles) · `graphify-out/` (gitignored) ·
`.opencode/` (per-project, gitignored).
