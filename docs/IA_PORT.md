# ia_harness port — what was adopted, what was left out

Source: `ia_harness` v1.02.01 (AOSP-specific agent harness). Principle:
adopt its **operations maturity**, keep pipa **project-agnostic**. Anything
AOSP-only lives in `templates/project/aosp/` (`pipa init --type aosp`),
never in core.

## Adopted (generalized)

| ia feature | pipa home |
|---|---|
| Dashboard shell: grouped sidebar, top-bar (Refresh/Restart), toasts, mobile drawer | `dashboard/templates/base.html`, `dashboard/static/style.css` |
| Status + API-keys live view | `dashboard/pages/overview.py`, `templates/overview.html` |
| Providers page (key names only, Test buttons, no cloud live-calls) | `dashboard/{pages,data}/providers.py`, `templates/providers.html` |
| Tier Manager descriptions + cost ceilings | `models/tiers.yaml`, Models page tier rows |
| `doctor.py` health diagnostics | `pipa doctor` (`pipa/commands/doctor.py`) |
| `diagnose.sh` troubleshooting dump | `pipa diagnose` (`pipa/commands/lifecycle.py`) |
| `auto-update.sh` fast-forward updater | `pipa update/check-update/version` |
| Single-flight install job runner + secret scrubbing | `dashboard/data/installer.py`, Install page |
| `metrics_lib.py` shared usage parser | `pipa/metrics.py` (package) → `pipa usage-report` + Observability Usage tab |
| `task-router.md` (route line, ≤3 slugs, union cap) | `rules/task-router.md` |
| `evals/validate.py` + `routing.json` | `evals/`, wired into `pipa eval` |
| MCP bridge `--status`/`--self-test` contract + template | `mcp/_template/`, `mcp/README.md` |
| L1 loop-triage discipline (report-only) | `rules/task-router.md` triage slug (no autonomous loops in core) |

## Framework parity screens (JS + JSON API, same actions as ia)

`dashboard/pages/api.py` (18 JSON routes) + `static/js/pages/*.js`:

| Screen | Routes | Actions |
|---|---|---|
| Status | `/api/status`, `/api/env-keys` | live grid, ollama Start, key Set/Change/Save (writes `$PIPA_ROOT/.env` 600, restarts gateway) |
| Tier Manager (`/tiers`) | `/api/dashboard`, `PUT /api/tier-models`, `/api/tiers/{t}`, `/api/gateway/rebuild` | per-tier model + max_steps, catalog view, rebuild+restart |
| Agents (`/agents`) | `PUT /api/agents/{a}`, `POST /api/agents/{a}/reset` | tier override, drift marker, reset to default |
| Install (`/install`) | `/api/install/state`, `/api/install/run`, `/api/install/log` | staged runner, readiness per stage, live log |
| Graph (`/graphify`) | `/api/graph/stats|search`, `POST /api/graph/refresh` | index status, symbol search, rebuild via graphify CLI |
| Rules & Skills (`/docs`) | `/api/docs`, `/api/docs/content` (GET+PUT) | browse/search, markdown view, in-place edit (200KB cap, jail) |

## Round 2 (screenshot-driven review + second sweep)

Verified via headless-Chromium screenshots of every screen
(`state/scratch/shots/`). Fixed from shots: JS tables empty
(`loadDashboard` stubbed — restored ia's bootstrap loader), drawer toggle
icons collapsed to 0 width (flex-shrink), desktop toggle unhidden by the
bare-button rule, clock wrapping, absolute-path status details.

| ia feature | pipa home |
|---|---|
| `token-economy.md` / `degraded-mode.md` rules | `rules/` (de-AOSP'd; auto-loaded) |
| `check-subagent-return.sh` scope+secrets gate | `tools/check-subagent-return.sh` (git-root default) |
| `memory-context.ts` auto digest plugin | `clis/opencode/plugin/pipa-memory-context.js` + `pipa recall --digest` (bounded, `MEMORY_CONTEXT_*` caps) |
| Install verify gate (`90-verify`) | `pipa install verify` + Install `verify` stage (`pipa doctor` must be green) |
| `make start` freshness gate (warn) | `freshness_note()` warning inside `pipa up` (silent offline) |
| Orchestrator primary-agent tier (xhigh) | `AGENT_MODEL_MAP` + `models/tiers.yaml` agent_tiers |
| Pre-existing crash found by review: `Reporter("install")` | fixed to `Reporter()` — every Install Run button was broken |

Deliberately not ported: live cloud-key Test calls (pipa never spends API
calls from checks), Atlassian/Bitbucket/Jira sync (no Atlassian in core),
llama.cpp backend (platform-specific; noted), RADB/emulator device pages
(AOSP pack territory), LiteLLM-DB spend (NDJSON ledger covers it).

## Deliberately not ported to core

- `vendor/vw` edit scope, VHAL/navmap/RADB device flows, KPM/GEI process →
  `templates/project/aosp/` pack.
- Hardcoded Azure/Eldorado endpoints and Bitbucket memory remote → user
  `.env` / per-project config instead.
- Makefile command surface → `pipa` CLI is the surface.
- LiteLLM DB spend tracking → pipa's metadata-only NDJSON ledger
  (`pipa spend`) covers it with zero infra.

## Verification

`python3 -m pytest tests/ -q` · `python3 -m pipa eval` ·
`python3 -m pipa doctor` · `python3 -m pipa diagnose`

## Round 3 (user-driven UI pass + third sweep)

- Table fragments scroll instead of squeezing (min-width + nowrap cells);
  sessions table uses the agents-table style.
- Rules & Skills: project group labels.
- Context removed from the sidebar (routes stay for compat; rules/skills
  management lives on Rules & Skills).
- Models page is list-only (catalog + tier badges + state); tier/agent
  configuration lives on Tier Manager / Agents.
- Compose-before-restart guard on tier saves + gateway rebuild (fail
  closed — a bad compose never takes the gateway down).
- `rules/memory-hygiene.md` (search-before-write, budgets, staleness).
