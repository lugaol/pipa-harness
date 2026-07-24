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
  extension bundles (`squads/`), merged with full add/update/remove support.
- **Lean** — markdown files + subagents + git. No frameworks, no engines.

## Quick start

One command installs anything missing (uv, ollama, litellm, graphify,
opencode, obsidian, emdash), pulls the configured ollama models, starts both
services (ollama `:11434`, litellm gateway `:4000`), and verifies:

```bash
bin/pipa-up.sh            # macOS + Linux; idempotent — safe to re-run
bin/pipa-up.sh --status   # report only, change nothing
bin/pipa-up.sh --stop     # stop the services it started
```

Then: `cd your-project && opencode`

### Adopt it in your own project

```bash
cd /path/to/your-project
/path/to/pipa_harness/install.sh
```

Idempotent: symlinks `harness/` to this repo, creates `.opencode/` from
templates, never overwrites your files. Then edit `harness/AGENTS.md` with
your project's commands and repo map.

### Extend it per project

```bash
cp -r squads/template squads/projects/my-project   # create a bundle
# ...edit AGENTS.md, rules/, skills/, agents/ inside it...
bin/pipa-extend.sh squads/projects/my-project      # merge into the harness
bin/pipa-extend.sh --update my-project             # re-merge after edits
bin/pipa-extend.sh --remove my-project             # unmerge cleanly
```

Bundles can be symlinks to a `harness/` dir inside your project's repo, so the
extension is versioned together with the project.

## Layout

```
AGENTS.md      always-loaded router (the only injected context)
rules/         path-scoped rules (git, testing, security, code-review)
skills/        trigger-loaded skills (debugging, code-review, release, ...)
agents/        subagents: analyst → pm → architect → sm → dev → qa, explorer, researcher
specs/         two-phase plan→story workflow output
bin/           litellm-task.sh, model_battery.sh, harness_status.py, pipa-extend.sh
config/        litellm.yaml — every model name lives here
templates/     .opencode/ + emdash worktree scripts
squads/        extension bundles (template + projects/)
vault/         dated memory (decisions, research) with as_of/valid_until
state/         SESSION.md (warm resume) + PLAN.md (task ledger)
```

## Workflow at a glance

```
PLAN   @analyst → @pm → @architect → specs/<feature>/*.md
BUILD  @sm → specs/<feature>/stories/*.md → @dev implements → @qa verifies
```

Each story file is self-contained — the dev agent reads one file and has
everything. Trivial task? Skip planning, go straight to `@dev`.

## Requirements

- [OpenCode](https://opencode.ai) (`curl -fsSL https://opencode.ai/install | bash`)
- [LiteLLM](https://docs.litellm.ai) (`uv tool install 'litellm[proxy]'`)
- Optional: graphify for the codebase knowledge graph, emdash for parallel
  worktree agents, Obsidian for the vault

## License

Apache-2.0 — see [LICENSE](LICENSE).
