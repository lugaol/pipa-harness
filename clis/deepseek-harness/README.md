# clis/deepseek-harness — DeepSeek Harness runtime support

DeepSeek Harness (DSH, `dsh`) is an alternative agent runner that pipa can
drive instead of OpenCode. Shared harness markdown (AGENTS.md, rules/,
skills/, agents/) works as-is — DSH reads AGENTS.md natively.

## Install

Requires Node.js:

```sh
npm install -g @deepseek-ai/dsh
```

`pipa up --runtime deepseek-harness` installs it automatically when npm is
available.

## What pipa wires

DSH has no per-project config: it composes patch layers from `$DSH_HOME`
(default `~/.dsh`). `pipa init --runtime deepseek-harness` (or
`pipa runtime set deepseek-harness`) writes:

1. `.pipa/deepseek-harness/cordis.patch.yml` — project-local copy of the
   routing patch (portable record; gitignored).
2. `~/.dsh/cordis.patch.yml` — the machine-level layer (outranks per-profile
   layers). Routes the dormant base-bundle `llm-pi-ai` adapter at the LiteLLM
   gateway (`api: openai-completions`) and sets `agent-default-model` to
   `litellm/primary`. Written only when missing or already pipa-managed —
   user edits are never clobbered.
3. `~/.dsh/.credentials.yaml` — `LITELLM_API_KEY` ref on fresh installs.
   dsh resolves `apiKeyEnv` per request from env or this file; keys never
   live in YAML.

Verify without booting:

```sh
dsh --profile headless --dump-config   # shows litellm route + supplying file
```

## Session log

pipa's NDJSON session log (`.pipa/state/session.log.ndjson`, written by
hooks for OpenCode) and DSH's own JSONL sessions under `~/.dsh/sessions/`
are separate stores today; the dashboard reads the pipa log for both via
`pipa hook`. There is no `session:` config key in dsh — earlier versions of
this template claimed one; that schema was fictional.

## extension/

`extension` is a symlink to `../opencode/extension` — the project extension
scaffold (rules, skills, agents, specs, vault, state) is pure markdown and
runtime-agnostic, so both runtimes share one template.

## Gotchas (verified against dsh source)

- Patch entries replace a row's whole `config` block — no deep merge.
- No fallback chains in dsh; recovery is per-route `retryPolicy`.
- Hand-declared routes need compat flags for non-OpenAI gateways:
  `supportsDeveloperRole: false`, `maxTokensField: max_tokens` (LiteLLM
  rejects the developer role / `max_completion_tokens` defaults).
- Only `web` and `headless` profiles ship; other names must be created with
  `dsh plugin --profile <name> ...` first.
