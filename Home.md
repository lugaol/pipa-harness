# pipa_harness — Home

Project-agnostic agent harness. Start here.

## Philosophy (adapted from aiox-core, lean)
- **CLI First** → the CLI is the source of truth; UI only observes.
- **Two-phase** → plan (analyst→pm→architect) then build (sm→dev→qa).
- **File-driven context** → agents hand off via `specs/` files, not chat.
- **Lean** → markdown + subagents + git. No engines.

## Quick start
1. **LiteLLM**: `litellm --config config/litellm.yaml --port 4000`
2. **Health**: `python3 bin/harness_status.py`
3. **OpenCode**: `opencode` (reads `.opencode/opencode.jsonc`)
4. **Parallel**: emdash → Add Task → OpenCode provider

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
- [[README]] — full usage guide + install + extensions
- [[specs/README]] — two-phase plan→story workflow
- [[README]] — full usage guide + install + extensions
- [[vault/decisions/000-template|Decision template]] — architectural memory
- [[state/SESSION]] — warm session resume
- [[state/PLAN]] — in-session work ledger

## Layers
```
LAYER 0  AGENTS.md                  → always loaded: router + philosophy
LAYER 1  rules/*.md                 → loaded via opencode.jsonc instructions glob
LAYER 2  skills/*/SKILL.md          → auto-discovered by OpenCode on trigger
LAYER 3  specs/<feature>/           → plan→story workflow (file-driven context)
LAYER 4  graphify-out/ + vault/      → queried memory (MCP + files), never injected
LAYER 5  agents/*.md                 → OpenCode subagents (analyst, pm, architect, sm, dev, qa, explorer, researcher)
LAYER 6  .harness_extension/        → project extensions (project-local rules, skills, agents)
```

## Open this as an Obsidian vault
Open the repo root. Start here at `Home.md`. Generated graph notes live in
`graphify-out/obsidian/` (gitignored — regenerate with `graphify export obsidian`).
