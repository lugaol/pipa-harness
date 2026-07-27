# pipa_harness

![pipa kite illustration](assets/pipa-sky.svg)

**A project-agnostic agent harness for AI coding assistants** — OpenCode + LiteLLM + graphify + Obsidian, orchestrated with emdash.

<p align="center">
  <a href="https://github.com/lugaol/pipa-harness/actions"><img alt="CI" src="https://github.com/lugaol/pipa-harness/actions/workflows/ci.yml/badge.svg"/></a>
  <a href="https://pypi.org/project/pipa-harness/"><img alt="PyPI" src="https://img.shields.io/pypi/v/pipa-harness.svg"/></a>
  <a href="https://github.com/lugaol/pipa-harness/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/badge/License-Apache_2.0-blue.svg"/></a>
  <a href="https://github.com/lugaol/pipa-harness/issues"><img alt="Issues" src="https://img.shields.io/github/issues/lugaol/pipa-harness.svg"/></a>
</p>

---

## What it does

AI agents work best with *just enough* context. This harness keeps the always-loaded context tiny (one `AGENTS.md` router) and loads everything else on demand:
- **Rules** attach by file path glob
- **Skills** load by trigger keyword
- **Memory** is queried, not injected wholesale
- **Models** route through a single LiteLLM gateway you control

Result: lower token costs, less context bloat, and zero conversation loss across sessions.

## Why developers choose it

| Feature | Benefit |
|---------|---------|
| **Token-efficient** | Only `AGENTS.md` is always loaded; everything else is progressive disclosure. |
| **Model-agnostic** | One `config/litellm.yaml` holds every alias. Swap providers in one place. |
| **Two-phase workflow** | Planning agents produce a spec, scrum master turns it into self-contained story files, build agents consume them. No context loss. |
| **Extensible** | Layer project-specific rules/skills/agents with `.harness_extension/`. |
| **Lean** | Markdown files + subagents + git. No frameworks, no engines. |
| **Observable** | Built-in tracing, evals, checkpoints, and a live dashboard. |

## Current status

- **Stable** — used in production for Android audio app development
- **Active development** — see [vault/research/agent-framework-sota-2026.md](vault/research/agent-framework-sota-2026.md) for latest SOTA patterns adopted
- **Compatible** — works with OpenCode, LiteLLM, graphify, Obsidian, emdash
- **Tested** — agent behavioral evals pass (transparency, approval gates, golden rules)

## Quick start

### One-command install (from a clean machine)

```bash
curl -fsSL https://raw.githubusercontent.com/lugaol/pipa-harness/main/bootstrap.sh | bash
```

This downloads the harness to `~/.local/share/pipa-harness`, adds it to your shell `PATH`, installs dependencies (`uv`, `ollama`, `litellm`, `graphify`, `opencode`, `obsidian`, `emdash`), and starts services. If API keys are not set, it falls back to a free-only Ollama-based config so you can start immediately.

### Or install from a local clone

```bash
# Clone the harness
git clone https://github.com/lugaol/pipa-harness.git
cd pipa-harness

# Install dependencies (macOS + Linux)
./bin/pipa-up.sh
```

### Run OpenCode

```bash
opencode
```

OpenCode reads `AGENTS.md` automatically. You're ready to go.

### Open the dashboard

```bash
# In another terminal
bin/dashboard.sh start
# Opens http://localhost:8080
```

![Dashboard](assets/dashboard-screenshot.png)

## Adopt in your project

### One-command setup

```bash
cd /path/to/your-project
pipa-up
```

Idempotent: creates `.harness_extension/`, `.opencode/`, symlinks root `AGENTS.md`, and auto-fills `AGENTS.md` placeholders from detected project facts. Never overwrites existing files.

### Pick a project-type template

```bash
cd /path/to/your-android-project
pipa-up --init android
```

Available templates live in `templates/project/`. Each overlays domain-specific rules, skills, and routing on top of the generic scaffold. You can add new templates by copying `templates/project/generic/`.

### Or use the wrapper

```bash
# From any project after pipa-up
pipa-up            # scaffold + wire
pipa-up --status   # report only
pipa-up --stop     # stop services
pipa-up --init android   # scaffold with the Android template
```

## Layout

```
bootstrap.sh         one-command installer (curl | bash)
AGENTS.md            always-loaded router (the only injected context)
rules/               path-scoped rules (git, testing, security, code-review)
skills/              trigger-loaded skills (debugging, release, performance, ...)
agents/              subagents: analyst → pm → architect → sm → dev → qa, explorer, researcher
specs/               two-phase plan→story workflow output
bin/                 litellm-task.sh, pipa-up.sh, dashboard.sh, pipa-init-project.py, pipa-extension-check.sh
config/              litellm.yaml + litellm.free.yaml — every model alias lives here
tools/               dashboard (FastAPI, :8080), tracing, evals, memory store
templates/           .harness_extension/ scaffold + .opencode/ + project-type templates + emdash scripts
vault/               dated memory (decisions, research) with as_of/valid_until
state/               SESSION.md (warm resume) + PLAN.md (task ledger)
```

## Project extension layout (`.harness_extension/`)

```
AGENTS.md            project-specific router (symlinked from root)
rules/               project-scoped rules (audio-ndk, ui-xml, ...)
skills/              project-specific skills (blow-detection, gesture-mapping, ...)
agents/              project-specific subagents (my-supervisor, my-explorer, ...)
state/               SESSION.md + PLAN.md + checkpoints + summaries
vault/               decisions/ + research/ + architecture/ — dated project memory
```

## Workflow

```
PLAN   @analyst → @pm → @architect → specs/<feature>/*.md
BUILD  @sm → specs/<feature>/stories/*.md → @dev implements → @qa verifies
```

Each story file is self-contained — the dev agent reads one file and has everything. Trivial task? Skip planning, go straight to `@dev`.

## Model orchestration

All calls go through LiteLLM aliases:

| Alias | Use for | Token cost |
|-------|---------|------------|
| `fast` | Triage, QA verdicts, summaries | Low |
| `primary` | Implementation, dev agent, supervisor | Medium-High |
| `deep` | Research, planning, architect | High |
| `explore` | Read-only codebase Q&A | Lowest |

Script: `bin/litellm-task.sh <alias> "<prompt>"`. Override via env: `LITELLM_MODEL_FAST`, `LITELLM_MODEL_PRIMARY`, etc.

## Dashboard

After `pipa-up.sh`, the dashboard opens at `http://localhost:8080`:

- **Status** — litellm, ollama, opencode, graphify, emdash health
- **LLMs** — manage model aliases with presets; changes write to `config/litellm.yaml`
- **API Keys** — manage `.env` keys from the UI
- **Agents** — every base + extension agent, with per-agent model override
- **Extensions** — `.harness_extension/` projects under your development root
- **Tools** — pipa_harness bin scripts + dashboard
- **Traces** — agent run spans (enable with `PIPA_TRACING=1`)
- **Evals** — behavioral regression checks for agents
- **Checkpoints** — fault tolerance & resume points
- **Summaries** — rolling conversation summaries
- **Memory** — SQLite-backed vault index

Start/stop manually: `bin/dashboard.sh {start|stop|status}`

## Usage examples

### Run a specific agent

```bash
# Deep research (papers, API docs)
bin/litellm-task.sh deep "Research Oboe latency best practices for Android audio"

# Fast QA verdict
bin/litellm-task.sh fast "Review this diff for security issues: ..."

# Cheap codebase search
bin/litellm-task.sh explore "Find all JNI method signatures in app/src/main/cpp"
```

### Use with OpenCode

In OpenCode, just mention an agent by name:

```
@dev Implement the story in specs/feature/stories/01-core.md
```

OpenCode reads the agent definition from `agents/*.md` and routes to the right model alias automatically.

### Enable tracing

```bash
export PIPA_TRACING=1
# Agent runs now emit trace spans to state/traces.db
# View in dashboard or: python tools/tracing.py export
```

### Run evals

```bash
python3 tools/agent_evals/run.py
# Checks: transparency blocks, approval gates, golden rules, file:line refs
```

### Index vault memory

```bash
python3 tools/memory_store/index_vault.py
# Indexes vault/*.md into state/memory.db for scoped recall
python3 tools/memory_store/query.py "blow detection"
```

## Requirements

- [OpenCode](https://opencode.ai) (`curl -fsSL https://opencode.ai/install | bash`)
- [LiteLLM](https://docs.litellm.ai) (`uv tool install 'litellm[proxy]'`)
- Optional: graphify, emdash, Obsidian

## Migration

- The legacy `pipa-extend.sh` + `squads/` extension model has been removed. Use `.harness_extension/` per project instead.
- The old Ollama/Kilo wrappers (`harness/bin` → `~/harness/bin`) are retired. Use `pipa_harness/bin/litellm-task.sh` instead.

## License

Apache-2.0 — see [LICENSE](LICENSE).
