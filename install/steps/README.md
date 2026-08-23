# install/steps — ordered setup scripts

Two-layer design:

1. **Orchestration layer** (`install/Makefile`, `bootstrap.sh`) — copies the
   working tree to `~/.pipa-harness`, wires PATH, and sequences the steps
   below. It contains no install logic of its own.
2. **Implementation layer** (`bin/pipa install <component>`, see
   `pipa/cli.py` → `INSTALL_COMPONENTS` / `cmd_install`) — does all the heavy
   lifting: uv, ollama, litellm, graphify, dsh, opencode, apps.

**DRY rule:** there is exactly ONE implementation per component (the Python
CLI). These step scripts are thin wrappers so a user can run a single phase
without knowing Make, and so `bootstrap.sh` / `make` share identical behavior.

## Scripts (run in lexical order)

| Script | Purpose | Delegates to |
|--------|---------|--------------|
| `00-deps.sh` | Verify base tooling exists: git, rsync, python3. Fails fast with a clear message. | — |
| `10-core.sh` | Core engine: uv tool manager, LiteLLM gateway, graphify code graph. | `bin/pipa install uv litellm graphify` |
| `20-runtimes.sh` | Agent runtimes: deepseek-harness + opencode. | `bin/pipa install dsh opencode` |
| `30-apps.sh` | OPTIONAL GUI apps (obsidian, emdash). Skip with `PIPA_SKIP_APPS=1`. | `bin/pipa install apps` |
| `40-wire.sh` | Final wiring: ensure tools + start services, no GUI apps, no model pulls. Also persists PATH via `services.persist_path`. | `bin/pipa up --no-apps --no-pull` |

## Usage

```sh
# full sequence on an already-installed checkout (~/.pipa-harness)
for s in install/steps/*.sh; do sh "$s"; done

# just one phase
sh ~/.pipa-harness/install/steps/20-runtimes.sh
```

Each script is POSIX sh, `set -eu`, and `cd`s to the harness root it belongs
to (`$(dirname "$0")/../..`) — they work both from a source checkout and from
the installed copy at `~/.pipa-harness`.
