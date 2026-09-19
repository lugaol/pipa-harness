# Refactor Proposal — pipa_harness Simplification

> **Scope:** Harness (low layer) + project overlay (high layer) + dashboard UX
> **Principle:** CLI first → observability second → UI third. Lean by default.
> **Target:** 5 nav items, ~100-line AGENTS.md, one-page model setup, zero project pollution

---

## 1. Layering — Make It Explicit

### Current (correct but implicit)

```
~/.pipa-harness/          ← global install (singleton)
  AGENTS.md               ← always-loaded router
  rules/   skills/  agents/  ← base layer
  models/  clis/  mcp/  tools/  dashboard/  pipa/  ← wiring

<project>/
  AGENTS.md -> .pipa/AGENTS.md   ← symlink (1 file in root)
  .pipa/                           ← project overlay (high layer)
    AGENTS.md  rules/  skills/  agents-local/  memory/  state/
  graphify-out/                    ← gitignored cache
```

### Proposed (same structure, clearer contract)

```
LAYER 0 — Harness (global, installed once)
  AGENTS.md               slim router only (~100 lines)
  AGENTS_OPERATIONS.md    compaction / sandbox / tracing / todo (loaded on demand)
  rules/                  3 files (security, testing, git-workflow)
  skills/                 5 lean skills (ui-ux-pro-max → optional)
  agents/                 8 agents, 2 permission profiles
  models/                 providers.yaml + settings.yaml → .effective.yaml
  dashboard/              5 pages
  pipa/                   CLI thin, commands/ per-command modules

LAYER 1 — Project (.pipa/, created by pipa init, nothing else)
  AGENTS.md               project facts only, $PIPA_ROOT not hardcoded
  rules/  skills/  agents-local/  memory/  state/  specs/  tools/
  runtime                 one word: opencode | deepseek-harness

Uninstall:  rm -rf .pipa/ graphify-out/ && rm AGENTS.md
```

**Changes:**

| Area | Before | After |
|------|--------|-------|
| AGENTS.md path ref | `/Users/.../pipa_harness` | `$PIPA_ROOT` / `~/.pipa-harness` |
| Legacy compat | 3 layouts (`.pipa/`, `.pipa/extension/`, `.harness_extension/`) | Single `.pipa/` — keep `pipa migrate` for one release, then drop |
| Optional skill | `ui-ux-pro-max` (1.7 MB) in every install | Move to `skills-optional/ui-ux-pro-max/` — `pipa install ui-ux-pro-max` |
| Disabled MCP | 3 disabled entries in `mcp/` | Keep `context7` + one `config.example.json` |

---

## 2. AGENTS.md — From 238 Lines to ~100

### Keep in AGENTS.md (always-loaded, ~100 lines)

```
# pipa_harness router
Philosophy (3 bullets)
Stack (runtimes, pipa CLI, gateway, graphify, memory — 5 lines)
Golden rules (3 HARD)
Two-phase workflow (diagram, 10 lines)
Routing table (6 rows)
Agents (8 names, one line each)
Model tiers (5 tiers table)
Harness transparency (footer mandate)
Conflict priority (one line)
```

### Move to AGENTS_OPERATIONS.md (loaded on demand)

- Context compaction / token-saving rules
- Stop governor
- Todo tool
- Sandbox model
- Observability / tracing
- Repo layout (→ docs/ARCHITECTURE.md)
- Truth & spend planes (→ docs/SESSION_BUS.md)
- Concurrent execution / conflict resolution details

### Move to docs/

- `docs/OPERATIONS.md` — the extracted sections
- `docs/ARCHITECTURE.md` — already exists, expand with repo layout

**Result:** New user reads one screen and understands the workflow. Agents that need operational detail load `AGENTS_OPERATIONS.md` via their frontmatter `instructions`.

---

## 3. Agents, Rules, Skills — Keep Lean

### Agents (8 → 8, but 2 permission profiles)

| Change | Detail |
|--------|--------|
| Permission profiles | Replace 8 hand-maintained `permission:` blocks with 2: `readonly` (explorer, qa) and `edit` (analyst, pm, architect, sm, dev, researcher). Central registry in `pipa/permissions.py` or `models/permissions.yaml` |
| Tier clarity | Keep 5 tiers but document which agents use which: `lowest→explorer`, `low→qa`, `mid→dev+sm`, `high→analyst+pm+architect+researcher`, `xhigh→reserved` |
| No agent count change | 8 roles map cleanly to the workflow — keep all |

### Rules (4 → 3)

| Change | Detail |
|--------|--------|
| Fold `code-review.md` into `security.md` | Both forbid secrets — one file, two sections |
| Keep `testing.md`, `git-workflow.md` | As-is |
| Add `glob:` frontmatter | Make path scoping explicit instead of always-loaded |

### Skills (6 → 5 + 1 optional)

| Change | Detail |
|--------|--------|
| Keep 5 lean skills | `debugging`, `code-review`, `graphify`, `performance`, `release` (23–33 lines each) |
| Extract `ui-ux-pro-max` | Move to `skills-optional/` — install with `pipa install ui-ux-pro-max`. Saves 1.7 MB from every install |

---

## 4. Model Configuration — One Page, One Save

### Problem today

```
Dashboard:  Models page → 5 individual forms → 5 saves → 5 page reloads
            + manual "Refresh from providers" + manual gateway restart on Overview
            = 7+ clicks, 2 pages, no feedback that restart is needed
CLI:        pipa up → discover → seed_default_tiers() → compose → start gateway
            (auto-seed only via CLI, never from dashboard alone)
```

### Proposed

```
Dashboard:  Models & Agents — single page, two sections

  Section A — Tier assignments (5 rows, single form)

    ┌─────────────────────────────────────────────────┐
    │ Tier        Model                    Status      │
    │ lowest  →  [mimo-v2.5-free     ▼]  ● ready     │
    │ low     →  [deepseek-v4-flash  ▼]  ● ready     │
    │ mid     →  [deepseek-v4-flash  ▼]  ● ready     │
    │ high    →  [kilo-auto/free     ▼]  ● ready     │
    │ xhigh   →  [step-3.7-flash     ▼]  ● ready     │
    │                                                 │
    │ [Save all & restart gateway]                    │
    └─────────────────────────────────────────────────┘
    "Last refreshed: 2h ago · Ollama: 0 · Zen: 8 · Kilo: 15"
    [Refresh from providers]

  Section B — Agent overrides (card grid, same page or collapsed)

    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ explorer │ │ dev      │ │ analyst  │
    │ lowest   │ │ mid      │ │ high     │
    │ [auto ▼] │ │ [auto ▼] │ │ [auto ▼] │
    └──────────┘ └──────────┘ └──────────┘
    (auto = frontmatter default, no override needed)

  Flow:
    1. First visit with no tier_assignments.json → banner:
       "No tiers configured — using auto-seeded defaults. Adjust or press Save."
       (seed_default_tiers() runs on page load when empty)
    2. Change any tier → Save all → composes .effective.yaml + restarts gateway
       in one action. No second page.
    3. Inactive models (missing API key) show "— needs KILO_API_KEY" disabled.
```

### Backend changes

| File | Change |
|------|--------|
| `pipa/model_registry.py` | `seed_default_tiers()` already exists — call it from `dashboard/data/models.py` when `tier_assignments()` is empty and `entries(active_only=True)` is non-empty. No CLI-only path |
| `pipa/config.py` | `compose_litellm_config()` stays, but surface a single `apply_tiers(assignments) → (ok, msg)` that composes + restarts |
| `dashboard/pages/models.py` | Single `POST /api/tiers/batch` instead of 5 individual `POST /api/tiers`. Handler calls `apply_tiers` |
| `dashboard/data/services.py` | `gateway_restart()` called inline from the batch save — no separate Overview action |
| `providers.yaml` (new) | Replace `PROVIDERS` dict in `pipa/providers.py` (196 lines, lambdas with `os.environ/...` strings) with a declarative `models/providers.yaml` — one entry per provider, no code change to add a provider |

### Wiring stays the same

- `models/.effective.yaml` — still generated, still gitignored, still `model_list + settings.yaml`
- `clis/opencode/global.jsonc` and `clis/deepseek-harness/cordis.patch.yml` — still machine-global, still read `tier_assignments.json` via `runtime_model_list()`
- Both runtimes share the same 5 tier aliases — one config, two consumers

---

## 5. Dashboard — From 10 Pages to 5

### Current nav (10 items, 3 groups)

```
Overview  ·  Sessions  ·  Spend
Models  ·  Context  ·  Memory  ·  Graph
Projects  ·  Agents  ·  Evals
```

### Proposed nav (5 items)

```
┌─────────────────────────────────────────────┐
│  π  pipa                                    │
│                                             │
│  ● Status          ← Overview + health +    │
│  │                   service ops + projects  │
│  │                   summary + graph badge   │
│  ○ Models          ← Tiers + agents +       │
│  │                   catalog (THE config)    │
│  ○ Context         ← Rules + skills         │
│  │                   (global / project)      │
│  ○ Observability   ← Sessions + spend       │
│  │                   (tabs within one page)  │
│  ○ Knowledge       ← Memory + graph query   │
│                      (advanced, collapsed)   │
│                                             │
│  ── health pill (gateway / ollama) ──       │
└─────────────────────────────────────────────┘
```

### Page-by-page plan

| Current page | Action | Detail |
|-------------|--------|--------|
| **Overview** | **Keep → Status** | Add project count + graph status badge. Keep service restart + API key chips. Remove duplicate "Run evals" button |
| **Models** + **Agents** | **Merge → Models** | Single page, two sections (tiers + agent cards). Batch save. Auto-seed banner |
| **Context** | **Keep, simplify** | `Rules` + `Skills` only. Move `MCP` toggle to Status footer. Remove `Agents` tab (now on Models). 4 tabs → 2 tabs |
| **Sessions** + **Spend** | **Merge → Observability** | One page, two tabs. Sessions table + spend summary. No new code — just a tab strip |
| **Memory** + **Graph** | **Merge → Knowledge** | One page, two sections. Recall search + graph query. Collapsed by default (advanced) |
| **Projects** | **Fold into Status** | Project table becomes a section on Status. Runtime switch stays. Remove top-level nav |
| **Evals** | **Remove from nav** | Trigger via `pipa eval` CLI or a button on Status. Not daily workflow |

### UX details

| Concern | Proposal |
|---------|----------|
| First-run onboarding | When `model_catalog.json` is empty → Models page shows wizard: "Step 1: Refresh from providers → Step 2: Review auto-seeded tiers → Step 3: Save & restart" |
| Batch save | One `<form>` wrapping all 5 tier rows + agent cards. Single POST, single redirect, single `?saved=1` flash |
| Restart feedback | Save button says "Save & restart gateway" — handler composes + restarts + flashes "Tiers saved, gateway restarted (51 models)" |
| Gateway not running | Status page shows "Gateway down — [Start gateway]" CTA. Models page shows "Gateway not running — tiers will apply on next start" |
| Mobile | Keep existing `@media max-width: 900px` stacking. 5 items fit without scroll |
| No JS framework | Keep PRG pattern (POST → 303 → GET with `?saved=1`). No HTMX/JSX needed |

---

## 6. CLI — Thin Parser, Fat Commands Stay Elsewhere

### Current: `pipa/cli.py` is 601 lines (arg parsing + orchestration)

### Proposed: `pipa/cli.py` < 120 lines, commands in `pipa/commands/`

```
pipa/
  cli.py              arg parsing only — build_parser() + dispatch
  commands/
    up.py             service orchestration (from cli.py:cmd_up)
    status.py         health checks (from cli.py:cmd_status)
    runtime.py        list/show/set (from cli.py:cmd_runtime)
    recall.py         already exists as pipa/recall.py
    spend.py          already exists as pipa/spend.py
  config.py           path resolution + compose (as-is)
  model_registry.py   tier logic (as-is, + providers.yaml)
  providers.py        discovery, reads providers.yaml
  services.py         start/stop/health (as-is)
```

| Command | Keep? | Notes |
|---------|-------|-------|
| `init` | Yes | Thin — scaffold `.pipa/` |
| `up` | Yes | Core — discover → seed → start → wire |
| `status` | Yes | Core — health check |
| `runtime` | Yes | list/show/set |
| `recall` | Yes | One-query memory |
| `spend` | Yes | Ledger |
| `replay` / `diff` | Yes | Flight recorder |
| `stop` | Yes | Kill services |
| `install` | Simplify | Fold into `up --component` or keep but dedup with `services.ensure_*` |
| `hook` | Internal | Keep but hide from `--help` (it's called by runtime plugins, not users) |
| `migrate` | Deprecate | Keep one release, then remove |
| `eval` | Keep | Thin passthrough to `tools/evals/run.py` |

---

## 7. Implementation Phases

### Phase 0 — No-regret cleanups (1–2 days, no UX change)

- [ ] Extract `AGENTS_OPERATIONS.md`, slim `AGENTS.md` to ~100 lines
- [ ] Fold `code-review.md` into `security.md`
- [ ] Move `ui-ux-pro-max` to `skills-optional/`
- [ ] Remove 3 disabled `mcp/` entries → one `config.example.json`
- [ ] Replace hardcoded paths in templates with `$PIPA_ROOT`
- [ ] Create `models/providers.yaml`, make `providers.py` read it
- [ ] Unify permission profiles (2 instead of 8)

### Phase 1 — Model config simplification (2–3 days)

- [ ] Auto-seed tiers on dashboard first visit (call `seed_default_tiers()` from `data/models.py`)
- [ ] Batch save: `POST /api/tiers/batch` → compose + restart in one action
- [ ] Single-page Models & Agents (merge `pages/models.py` + `pages/agents.py`)
- [ ] Update `templates/models.html` to batch form + agent cards section
- [ ] Wire `providers.yaml` declarative config

### Phase 2 — Dashboard nav simplification (2–3 days)

- [ ] Merge Sessions + Spend → `pages/observability.py` (tab strip)
- [ ] Merge Memory + Graph → `pages/knowledge.py` (collapsed sections)
- [ ] Fold Projects into Status, Evals out of nav
- [ ] Simplify Context: 4 tabs → 2 (Rules, Skills), MCP → Status footer
- [ ] Update `templates/base.html` nav to 5 items
- [ ] Add first-run wizard banner on Models when catalog is empty

### Phase 3 — CLI split + polish (1–2 days)

- [ ] Split `cli.py` → `commands/` per-command modules
- [ ] Hide `hook` from help, dedup `install`/`up`
- [ ] Add `pipa providers refresh` as alias for dashboard Refresh (optional)

### Phase 4 — Legacy removal (next major, 1 day)

- [ ] Drop `.harness_extension/` and `.pipa/extension/` compat after migration window
- [ ] Remove `pipa migrate` command
- [ ] Clean `state/` vs `.pipa/state/` duality docs

---

## 8. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Users rely on 10-page nav bookmarks | Keep old routes as 307 redirects for one release (`/sessions` → `/observability?tab=sessions`) |
| `ui-ux-pro-max` users lose skill | `pipa install ui-ux-pro-max` restores it; migration note in CHANGELOG |
| AGENTS.md slim breaks agent prompts | Keep `AGENTS_OPERATIONS.md` auto-loaded for planning agents via `additional_instructions` in `clis/*/global.jsonc` |
| Batch save + restart races with running gateway | `services.gateway_restart()` already handles kill→wait→start with timeout — reuse as-is |

---

## 9. Success Criteria

- [ ] New user: `pipa init` → `pipa up` → open dashboard → tiers auto-seeded → Save → agent runs. Under 2 minutes.
- [ ] Dashboard: 5 nav items, not 10. Each page has one job.
- [ ] AGENTS.md: ~100 lines. Fits on one screen.
- [ ] Model config: one page, one save, one restart. No second page.
- [ ] Project overlay: `ls` shows one symlink in root. `rm -rf .pipa/ graphify-out/ && rm AGENTS.md` = clean uninstall.
- [ ] All 115 harness tests + 9 jamming tests still green.
