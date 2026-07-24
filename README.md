# pipa_harness

A project-agnostic agent harness built on **OpenCode + LiteLLM + graphify +
Obsidian**, orchestrated with **emdash**. Philosophy adapted (lean) from
aiox-core: CLI-first, two-phase plan→build, file-driven context passing.

Token-efficient: AGENTS.md is the only always-loaded file. Rules attach by
path-glob, skills load on trigger, memory is queried (never injected), and
all models route through a single LiteLLM gateway.

## Philosophy
- **CLI First → Observability Second → UI Third.** The CLI is the source of
  truth; dashboards only observe.
- **Two-phase workflow.** Planning agents (analyst→pm→architect) produce a
  spec; the scrum master turns it into self-contained stories; build agents
  (dev, qa) consume stories with full context — no conversation loss.
- **File-driven context.** Agents hand off via `specs/` files, not chat.
- **Lean.** Markdown + subagents + git. No engines, no frameworks.

## Stack
| Tool | Role |
|------|------|
| OpenCode | Interactive + headless coding agent (TUI, `opencode run`) |
| LiteLLM | Model gateway at `:4000` — one place for all model config |
| graphify | Persistent codebase knowledge graph (query before grep) |
| Obsidian | This harness is a vault; memory in `vault/` |
| emdash | Parallel agent orchestration via git worktrees |

## Quick start

```bash
# 1. LiteLLM gateway (terminal 1)
litellm --config harness/config/litellm.yaml --port 4000

# 2. Health check
python3 harness/bin/harness_status.py

# 3. OpenCode (terminal 2) — in the project root
opencode
```

For parallel agents: open **emdash** → Add Task → select **OpenCode** as provider.

## Install in any project

```bash
cd /path/to/your-project
/Users/noname/Development/pipa_harness/install.sh
```

Idempotent: `harness/` is a **symlink** to the pipa_harness repo (updates to the
base harness reach every project instantly), `.opencode/` is created and
populated (never overwrites existing files), and an existing root `AGENTS.md`
is left untouched. After install, edit `harness/AGENTS.md` (project facts,
commands, repo map) and the skill stubs.

## Layout
```
pipa_harness/
├── AGENTS.md              # always-loaded router (the only injected context)
├── Home.md                # Obsidian map of content
├── rules/                 # path-scoped rules (git, code-review, security, testing)
│   ├── git-workflow.md
│   ├── code-review.md
│   ├── security.md
│   └── testing.md
├── skills/                # trigger-loaded skills (OpenCode SKILL.md format)
│   ├── graphify/SKILL.md
│   ├── debugging/SKILL.md
│   ├── code-review/SKILL.md
│   ├── release/SKILL.md
│   └── performance/SKILL.md
├── agents/                # OpenCode subagents (markdown + frontmatter)
│   ├── analyst.md         # Phase 1: research + briefing
│   ├── pm.md              # Phase 1: requirements + PRD
│   ├── architect.md       # Phase 1: technical design
│   ├── sm.md              # bridge: spec → self-contained stories
│   ├── dev.md             # Phase 2: implement one story + test
│   ├── qa.md              # Phase 2: review build, objective verdict
│   ├── explorer.md        # read-only code exploration (graphify → grep)
│   └── researcher.md      # deep research → vault note
├── bin/                   # model + status wrappers
│   ├── litellm-task.sh    # <fast|primary|deep|explore> "<prompt>"
│   ├── model_battery.sh   # benchmark model aliases
│   └── harness_status.py  # pre-session health check
├── config/
│   └── litellm.yaml       # model gateway config (aliases → providers)
├── templates/
│   ├── project/           # project-type-specific AGENTS.md snippets
│   └── opencode-emdash/  # .opencode/ worktree scripts + emdash doc
├── specs/                # two-phase plan→story workflow output
│   ├── STORY_TEMPLATE.md # copy per story
│   └── README.md
├── squads/               # project extensions + domain bundles
│   ├── projects/         # per-project extension bundles
│   ├── template/         # copy to create a new extension
│   └── README.md
├── vault/                 # dated project memory
│   ├── decisions/         # architectural decisions (as_of/valid_until)
│   ├── research/          # research notes
│   └── architecture/      # architecture diagrams/notes
└── state/
    ├── SESSION.md         # warm resume (≤30 lines)
    └── PLAN.md            # in-session work ledger
```

## Two-phase workflow (plan → build)
```
PHASE 1 — PLAN
  @analyst   → specs/<feature>/briefing.md
  @pm        → specs/<feature>/prd.md
  @architect → specs/<feature>/architecture.md
  @qa        → critique spec (loop)

PHASE 2 — BUILD
  @sm        → specs/<feature>/stories/NN-*.md  (self-contained)
  @dev       → implement one story + regression test
  @qa        → review build, objective verdict
```
Each story file carries full context — the dev agent opens ONE file and has
everything it needs. For trivial tasks, skip Phase 1 and go straight to `@dev`.

## Project extensions
Layer project-specific rules, skills, and agents on top of the base harness:
```bash
# Create an extension bundle
cp -r squads/template squads/projects/my-project
# Edit AGENTS.md, rules/, skills/, agents/ inside it...
# Merge into the harness (additive, never overwrites):
bin/pipa-extend.sh squads/projects/my-project
```
Extensions append an AGENTS.md section between markers and copy new
rules/skills/agents with `cp -n`. See `squads/README.md`.

## Routing (how context stays small)
- Open a file → matching `rules/*.md` attaches via `opencode.jsonc` `instructions`.
- Mention bug/review/release/performance → the matching skill loads via the
  `skill` tool.
- Architecture question → query the graph FIRST: `graphify query "..."`,
  `graphify explain "X"`, `graphify path "A" "B"`. Fall back to grep.
- Broad review → `graphify-out/GRAPH_REPORT.md`.

## Model orchestration
All model calls go through LiteLLM aliases. Change models in ONE place:
`harness/config/litellm.yaml`.

| Alias   | Use for                          |
|---------|----------------------------------|
| `fast`  | triage, titles, summaries        |
| `primary` | implementation, build agent     |
| `deep`  | research, complex reasoning       |
| `explore` | read-only codebase Q&A          |

Scripts: `harness/bin/litellm-task.sh <alias> "<prompt>"`.
Override via env: `LITELLM_MODEL_FAST`, `LITELLM_MODEL_PRIMARY`, etc.
Re-benchmark: `harness/bin/model_battery.sh`.

## Library API docs (Context7 MCP)
Context7 MCP (`https://mcp.context7.com/mcp`) fetches up-to-date library docs
on-demand. Configured in `opencode.jsonc` under `mcp.context7`.
- `resolve-library-id` → resolve a library name to a Context7 ID
- `query-docs` → fetch version-specific docs for that library

## Memory workflow
- Session start (per AGENTS.md): read `state/SESSION.md` + `PLAN.md` + newest
  `vault/decisions/` note.
- Decision/research notes need `as_of` + `valid_until` frontmatter. Expired →
  flag, don't apply.
- Session end: update SESSION.md (≤30 lines); write a decision note if
  architecture changed.

## Knowledge graph maintenance
- Post-commit hook rebuilds AST automatically (no LLM, no cost).
- After doc changes: `graphify extract . --update` (standalone, heavy).
- Scope control: `.graphifyignore` (build output, deps, graphify's own skill).

## Subagents (OpenCode)
- `@explorer` — read-only code exploration. Returns ≤ 50 lines with `file:line`.
- `@implementer` — surgical edits at approved file:line refs.
- `@verifier` — runs build/tests, objective pass/fail verdict.
- `@researcher` — deep research → vault note + 5-line summary.
- Delegate when: > 3 unknown files, research, or long logs.

## emdash (parallel worktrees)
- Add Task in emdash → each task gets its own git worktree + branch.
- Select **OpenCode** as the provider → reads `.opencode/opencode.jsonc`.
- `setup-script.sh` bootstraps deps on worktree creation.
- `run-script.sh` verifies the build before the agent starts.
- Review diffs side-by-side, merge what works.

## Obsidian
Open the repo root as a vault. Start at `harness/Home.md`. Generated graph notes
live in `graphify-out/obsidian/` (gitignored — regenerate with
`graphify export obsidian`).

## Troubleshooting
| Symptom | Fix |
|---------|-----|
| `litellm: command not found` | `uv tool install 'litellm[proxy]'` (Python 3.10+) |
| `opencode: command not found` | `curl -fsSL https://opencode.ai/install \| bash` |
| Status "litellm: fail" | `litellm --config harness/config/litellm.yaml --port 4000` not running |
| Skills not loading | check `.opencode/skills/*/SKILL.md` exists + frontmatter has `name`+`description` |
| Graphify MCP unavailable | check `mcp.graphify` in `opencode.jsonc` + `graphify-mcp` on PATH |
| Context7 MCP unavailable | check `mcp.context7` in `opencode.jsonc` |
| `graphify` command not found | `uv tool update-shell`, new terminal |
| emdash worktree build fails | check `.opencode/setup-script.sh` ran (submodules/deps) |
