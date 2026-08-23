# Architecture

pipa_harness separates five planes. The **contract surface** is markdown at the
install root; everything machine-specific is global wiring; projects carry only
facts and state.

## Planes mapped onto the tree

```
CONTRACT   AGENTS.md  rules/*.md  skills/*/SKILL.md  agents/*.md  specs/
           Pure markdown. Any runtime can consume it. This is the API.

RUNTIMES   clis/opencode/{global.jsonc,extension}     -> ~/.config/opencode/opencode.jsonc
           clis/deepseek-harness/cordis.patch.yml      -> ~/.dsh/cordis.patch.yml (+ .credentials.yaml)
           Templates rendered once per machine by `pipa up` / wire step.
           Projects hold NO runtime config — switching is `pipa runtime set <name>`.

LLM        models/local/*.yaml + models/cloud/*.yaml + models/settings.yaml
             --compose--> models/.effective.yaml --> LiteLLM proxy :4000
           Aliases: fast | primary | deep | explore. Cloud fragments activate
           only when their `requires:` env key exists; local Ollama is fallback.

MEMORY     vault/ (install-wide, dated as_of/valid_until)
           .pipa/memory/{decisions,research}/ (project-first)
           state/memory.db (SQLite index) · graphify-out/ (code graph)
           Access is always a query (`pipa recall`), never wholesale injection.

TRUTH      <project>/.pipa/state/session.log.ndjson   one append-only session bus
           state/spend.ndjson (gateway usage, metadata-only)
           state/traces.db (opt-in spans, PIPA_TRACING=1)
           Every consumer reads the bus; nothing else is authoritative.
```

## Resolution & precedence

Install root: `$PIPA_ROOT` > directory containing the `pipa` package (checkout) >
`~/.pipa-harness`.

- **Skills:** project `.pipa/skills/<name>/` beats a same-named global skill.
- **Rules:** project `.pipa/rules/*.md` load *alongside* global `rules/*.md`.
- **Router:** global `AGENTS.md` always loaded; project `.pipa/AGENTS.md` adds facts.
- **Recall:** project memory first, then install vault, then code graph;
  entries past `valid_until` are flagged, not applied.
- **Conflict order:** turn instruction > AGENTS.md > project overlay > base rules > skills > vault.

## Data flows

1. **Session bus.** Each runtime appends canonical NDJSON events to
   `<project>/.pipa/state/session.log.ndjson` (schema:
   [SESSION_BUS.md](SESSION_BUS.md)). Consumers: `pipa status`, dashboard
   sessions page, `pipa replay` / `pipa diff`, evals, future tooling.
2. **Model composer.** At wire time `pipa.config.compose_litellm_config` merges
   `models/local/*` + enabled `models/cloud/*` + `settings.yaml` into
   `models/.effective.yaml`; the LiteLLM proxy consumes it and its spend
   callback appends metadata-only rows to `state/spend.ndjson`.
3. **Wire-time merges.** Rendering a runtime merges (a) the `clis/<name>`
   template, (b) every enabled `mcp/<name>/config.json` block plus generated
   permission entries, (c) gateway endpoint settings — into one machine-global
   file per runtime. Re-run `pipa up` to re-render after registry edits.

## Module map

| Path | Role |
|------|------|
| `AGENTS.md`, `rules/`, `skills/`, `agents/` | contract markdown consumed by any runtime |
| `clis/<runtime>/` | template + wire entry per runtime |
| `models/` | LiteLLM fragments + composer inputs; `.effective.yaml` is generated |
| `mcp/<name>/` | MCP integration registry (enabled flag + verbatim server block) |
| `tools/` | evals, litellm helpers, memory_store indexer/query, ollama, tracing |
| `dashboard/` | FastAPI app; pages/ modules, fragments/, templates/, static/ |
| `pipa/` | CLI lib: cli, config (composer+paths), runtime, scaffold, services, hooks, recall, spend |
| `install/` | Makefile + steps/ scripts (deps, core, runtimes, apps, wire) |
| `tests/` | conformance suite pinning fragment/wiring/hook contracts |
| `vault/`, `state/` | dated memory and session/task state |

## Extension points

| Want to... | Do this |
|------------|---------|
| add a runtime | create `clis/<name>/` with a template + wire entry; register it in the runtime table |
| add a model provider | drop `models/cloud/<provider>.yaml` with a `requires:` env key; composer handles the rest |
| add an integration | drop `mcp/<name>/config.json`; merged at next wire |
| add a skill | `skills/<name>/SKILL.md` globally or `.pipa/skills/<name>/` per project (wins on name clash) |
| add a rule | `rules/<topic>.md` (global) or `.pipa/rules/` (project); attach via path scope |
