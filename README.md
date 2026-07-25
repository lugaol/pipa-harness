# pipa_harness

A project-agnostic agent harness for AI coding assistants — OpenCode + LiteLLM + graphify + Obsidian, orchestrated with emdash.

## Why

- **Token-efficient** — only `AGENTS.md` is always loaded; everything else is progressive disclosure.
- **Model-agnostic** — one LiteLLM gateway (`config/litellm.yaml`) holds every model alias. Swap providers in one place.
- **Two-phase workflow** — planning agents produce a spec, the scrum master turns it into self-contained story files, build agents consume them. No context loss across sessions.
- **Extensible** — layer project-specific rules/skills/agents on top with `.harness_extension/` in each project.
- **Lean** — markdown files + subagents + git. No frameworks, no engines.

## Quick start

### First time

From the pipa_harness repo root:

```bash
bin/pipa-up.sh
```

This one command installs tools (uv, ollama, litellm, graphify, opencode, obsidian, emdash), starts services (ollama `:11434`, litellm `:4000`), opens the dashboard (`:8080`), wires global OpenCode config (`~/.config/opencode`), and adds `pipa_harness/bin` to your shell PATH.

From any project root after that:

```bash
pipa-up.sh            # idempotent; scaffolds .harness_extension/ + .opencode/ + AGENTS.md symlink
pipa-up.sh --status   # report only
pipa-up.sh --stop     # stop services
```

The `pipa-up` wrapper in your project root execs `pipa_harness/bin/pipa-up.sh` from PATH.

### Adopt in an existing project

```bash
cd /path/to/your-project
/path/to/pipa_harness/install.sh
```

Idempotent: creates `.harness_extension/`, `.opencode/`, and symlinks root `AGENTS.md` → `.harness_extension/AGENTS.md`. Never overwrites existing files.

## Layout

```
AGENTS.md            always-loaded router
rules/               path-scoped rules (git, testing, security, code-review)
skills/              trigger-loaded skills (debugging, release, performance, ...)
agents/              subagents: analyst → pm → architect → sm → dev → qa, explorer, researcher
specs/               two-phase plan→story workflow output
bin/                 litellm-task.sh, model_battery.sh, harness_status.py, pipa-up.sh
config/              litellm.yaml — every model alias lives here
templates/           .harness_extension/ scaffold + .opencode/ + emdash worktree scripts
tools/               dashboard (FastAPI, :8080)
vault/               dated memory (decisions, research) with as_of/valid_until
state/               SESSION.md (warm resume) + PLAN.md (task ledger)
```

## Project extension layout (`.harness_extension/`)

```
AGENTS.md            project-specific router snippet (symlinked from root)
rules/               project-scoped rules (audio-ndk, ui-xml, ...)
skills/              project-specific skills (blow-detection, gesture-mapping, ...)
agents/              project-specific subagents (jam-explorer, jam-implementer, ...)
state/               SESSION.md + PLAN.md
vault/               decisions/ + research/ + architecture/ — dated project memory
```

## Workflow

```
PLAN   @analyst → @pm → @architect → specs/<feature>/*.md
BUILD  @sm → specs/<feature>/stories/*.md → @dev implements → @qa verifies
```

Each story file is self-contained — the dev agent reads one file and has everything. Trivial task? Skip planning, go straight to `@dev`.

## Dashboard

After `pipa-up.sh`, the dashboard opens at `http://localhost:8080`:
- **Status** — litellm, ollama, opencode, graphify, emdash health
- **LLMs** — manage model aliases with presets; changes write to `config/litellm.yaml`
- **Extensions** — `.harness_extension/` projects under your development root
- **Agents** — every base + extension agent, with per-agent model override
- **Tools** — pipa_harness bin scripts + dashboard

Start/stop manually: `bin/dashboard.sh {start|stop|status}`

## Model orchestration

All calls go through LiteLLM aliases:

| Alias    | Use for                          |
|----------|----------------------------------|
| `fast`   | triage, titles, summaries        |
| `primary`| implementation, dev agent        |
| `deep`   | research, planning, architect    |
| `explore`| read-only codebase Q&A            |
| `kilo-free`| free Kilo Code models           |

Script: `bin/litellm-task.sh <alias> "<prompt>"`. Override via env: `LITELLM_MODEL_FAST`, `LITELLM_MODEL_PRIMARY`, etc.

## Requirements

- [OpenCode](https://opencode.ai) (`curl -fsSL https://opencode.ai/install | bash`)
- [LiteLLM](https://docs.litellm.ai) (`uv tool install 'litellm[proxy]'`)
- Optional: graphify, emdash, Obsidian

## Notes

- `pipa-extend.sh` + `squads/` are deprecated. Migrate to `.harness_extension/`.
- The old Ollama/Kilo wrappers (`harness/bin` → `~/harness/bin`) are retired. Use `pipa_harness/bin/litellm-task.sh` instead.

## License

Apache-2.0 — see [LICENSE](LICENSE).
