# pipa_harness — Home

Project-agnostic agent harness, installed once at `~/.pipa-harness`, shared by every project. Start here.

## Philosophy (adapted from aiox-core, lean)
- **CLI First** → the CLI is the source of truth; UI only observes.
- **Two-phase** → plan (analyst→pm→architect) then build (sm→dev→qa).
- **File-driven context** → agents hand off via `specs/` files, not chat.
- **Global install, thin overlay** → machine-global wiring; projects carry only `.pipa/` facts and state.
- **Lean** → markdown + subagents + git. No engines.

## Quick start
1. **Install**: `bash bootstrap.sh` (or clone + `make -C install`), then `pipa up`
2. **Health**: `pipa status`
3. **Adopt a project**: `cd any-project && pipa init`
4. **Run**: `opencode` or `dsh web` · Dashboard: http://localhost:8080

## Agents
| Phase | Agent | Role |
|-------|-------|------|
| Plan  | `@analyst` | research + briefing |
| Plan  | `@pm` | requirements + PRD |
| Plan  | `@architect` | technical design + file refs |
| Plan  | `@qa` | critique spec |
| Bridge | `@sm` | spec → self-contained stories |
| Build | `@dev` | implement one story |
| Build | `@qa` | review + verify (objective verdict) |
| Util  | `@explorer` | read-only code search |
| Util  | `@researcher` | deep research → vault note |

## Map of content
- [[AGENTS]] — always-loaded router (philosophy, rules, routing, models)
- [[README]] — full usage guide: install, overlay, CLI, models, dashboard
- [[docs/ARCHITECTURE]] — planes, precedence rules, data flows
- [[WORKFLOW]] — layered loading + two-phase workflow reference
- [[vault/decisions/000-template|Decision template]] — architectural memory
- [[state/SESSION]] — warm session resume
- [[state/PLAN]] — in-session work ledger

## Layers
```
LAYER 0  AGENTS.md                  → always loaded: router + philosophy
LAYER 1  rules/*.md                 → path-scoped (project .pipa/rules load alongside)
LAYER 2  skills/*/SKILL.md          → trigger-loaded (.pipa/skills wins on name clash)
LAYER 3  specs/<feature>/           → plan→story workflow (file-driven context)
LAYER 4  graphify-out/ + vault/     → queried memory (`pipa recall`), never injected
LAYER 5  agents/*.md                → subagents (analyst, pm, architect, sm, dev, qa, explorer, researcher)
LAYER 6  <project>/.pipa/           → thin per-project overlay (facts, memory, state — no configs)
```

## Open this as an Obsidian vault
Open the repo root. Start here at `Home.md`. Generated graph notes live in
`graphify-out/obsidian/` (gitignored — regenerate with `graphify export obsidian`).
