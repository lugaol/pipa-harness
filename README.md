# pipa_harness

![A pipa flying through the sky](assets/pipa-sky.svg)

**A project-agnostic agent harness for AI coding assistants** — built on
OpenCode + LiteLLM + graphify + Obsidian, orchestrated with emdash.

The problem it solves: AI agents work best with *just enough* context. This
harness keeps the always-loaded context tiny (one `AGENTS.md` router) and loads
everything else on demand — rules attach by file path, skills load by trigger,
memory is queried instead of injected, and all models route through a single
gateway you control.

## Why

- **Token-efficient** — only `AGENTS.md` is always loaded; everything else is
  progressive disclosure.
- **Model-agnostic** — one LiteLLM gateway (`config/litellm.yaml`) holds every
  model name. Swap providers in one place; agents and scripts never change.
- **Two-phase workflow** — planning agents produce a spec, the scrum master
  turns it into self-contained story files, build agents consume them. No
  context loss across sessions.
- **Extensible** — layer project-specific rules/skills/agents on top with
  extension bundles (`.harness_extension/` in each project).
- **Lean** — markdown files + subagents + git. No frameworks, no engines.

## Quick start

### First time in a project

From your project root, run:

```bash
/path/to/pipa_harness/bin/pipa-up.sh
```

This one command:
- installs missing tools (uv, ollama, litellm, graphify, opencode, obsidian, emdash)
- starts services (ollama `:11434`, litellm gateway `:4000`)
- starts the dashboard on `http://localhost:8080` and opens it in your browser
- sets up the global OpenCode config (`~/.config/opencode`)
- adds `pipa_harness/bin` to your shell PATH (`.zshrc` / `.bashrc`)
- scaffolds `.harness_extension/` + `.opencode/` + root `AGENTS.md` symlink

After it finishes, **open a new terminal** (or `source ~/.zshrc`) so the new
`pipa-up.sh` command is on PATH.

### Subsequent runs (from any project)

```bash
pipa-up.sh            # macOS + Linux; idempotent — safe to re-run
pipa-up.sh --status   # report only, change nothing
pipa-up.sh --stop     # stop the services it started
```

Then: `cd your-project && opencode`

### Adopt it in your own project

```bash
cd /path/to/your-project
/path/to/pipa_harness/install.sh
```

Idempotent: creates `.harness_extension/` from templates, `.opencode/` from
templates, and symlinks root `AGENTS.md` → `.harness_extension/AGENTS.md`.
Never overwrites your files. Then edit `.harness_extension/AGENTS.md` with
your project's commands and repo map.

### Extend it per project

Each project carries its own `.harness_extension/` directory with project-specific
rules, skills, agents, state, and vault. The base rules, skills, and agents
come from the globally installed pipa_harness (`~/.config/opencode` points at it).

## Layout

```
AGENTS.md      always-loaded router (the only injected context)
rules/         path-scoped rules (git, testing, security, code-review)
skills/        trigger-loaded skills (debugging, code-review, release, ...)
agents/        subagents: analyst → pm → architect → sm → dev → qa, explorer, researcher
specs/         two-phase plan→story workflow output
bin/           litellm-task.sh, model_battery.sh, harness_status.py, pipa-up.sh, dashboard.sh
config/        litellm.yaml — every model name lives here
templates/     .harness_extension/ scaffold + .opencode/ + emdash worktree scripts
tools/         dashboard (FastAPI, :8080) + project tools
vault/         dated memory (decisions, research) with as_of/valid_until
state/         SESSION.md (warm resume) + PLAN.md (task ledger)
```

## Project extension layout (`.harness_extension/`)

```
AGENTS.md      project-specific router snippet (symlinked from root)
rules/         project-scoped rules (audio-ndk, ui-xml, ...)
skills/        project-specific skills (blow-detection, gesture-mapping, ...)
agents/        project-specific subagents (jam-explorer, jam-implementer, ...)
state/         SESSION.md + PLAN.md
vault/         decisions/ + research/ — dated project memory
```

## Workflow at a glance

```
PLAN   @analyst → @pm → @architect → specs/<feature>/*.md
BUILD  @sm → specs/<feature>/stories/*.md → @dev implements → @qa verifies
```

Each story file is self-contained — the dev agent reads one file and has
everything. Trivial task? Skip planning, go straight to `@dev`.

## Dashboard

After `pipa-up.sh`, the dashboard auto-opens in **Google Chrome** at `http://localhost:8080`:
- **Status** — litellm, ollama, opencode, graphify, emdash health
- **LLMs** — manage model aliases (primary, fast, deep, explore) with presets for Kimi, Claude, Gemini, GPT-4o, and local Ollama models. Changes write to `config/litellm.yaml` directly.
- **Extensions** — all `.harness_extension/` projects under your development root
- **Agents** — every base + extension agent, with a dropdown to set the LLM model per agent (writes directly to the agent file)
- **Tools** — pipa_harness bin scripts + dashboard

Start/stop manually: `bin/dashboard.sh {start|stop|status}`

### Setting up LLMs

1. Open the dashboard → **LLMs** section
2. Pick a preset (Kimi k2 free, Claude Sonnet, Gemini Flash, GPT-4o Mini, or local Ollama)
3. Click **Apply** on the alias you want to change
4. Click **Restart gateway** to apply the new config

Or enter a custom `model` + `api_base` + `api_key` and click **Save custom**.
Environment-variable keys are supported: `os.environ/ANTHROPIC_API_KEY`.

### Agent LLM override

In the **Agents** table, pick a model from the dropdown and click **Save**.
This writes the `model:` frontmatter directly into the agent `.md` file.

## Requirements

- [OpenCode](https://opencode.ai) (`curl -fsSL https://opencode.ai/install | bash`)
- [LiteLLM](https://docs.litellm.ai) (`uv tool install 'litellm[proxy]'`)
- Optional: graphify for the codebase knowledge graph, emdash for parallel
  worktree agents, Obsidian for the vault

## Migration from `pipa-extend` / `squads/`

The old `pipa-extend.sh` + `squads/` bundle model is deprecated. Projects
should migrate to `.harness_extension/`:

1. Copy project-specific content from `squads/projects/<name>/` into
   `.harness_extension/` (rules/, skills/, agents/, state/, vault/).
2. Delete the `squads/` entry and any `pipa-extend.sh` merges.
3. Run `bin/pipa-up.sh` to re-scaffold and verify.

## License

Apache-2.0 — see [LICENSE](LICENSE).
