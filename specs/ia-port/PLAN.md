# ia_harness → pipa_harness port — execution plan

Source: `/Users/noname/Development/ia_harness` (v1.02.01, AOSP-specific).
Rule: port the operations maturity, keep pipa generic. AOSP-only logic
(VHAL, emulator/RADB device flows, KPM/GEI, hardcoded Bitbucket remote,
`vendor/vw` paths) ships as an optional project pack, never in core.

## Phase 1 — Dashboard shell parity (ia `base.html` + per-page CSS/JS split)
- Group sidebar nav: Overview (Status, Observability) / Config (Models,
  Agents→models#agents, Context, Knowledge) / Catalog (Providers — Phase 2)
  / Setup (Install — Phase 4).
- Top-bar per page (title slot + Refresh + Restart Gateway), toast container,
  mobile sidebar toggle. Keep flash + `/api/health` pill + button spinner.
- Test: `tests/test_dashboard.py::test_app_serves_pages` green.

## Phase 2 — Providers page + API-keys parity
- New `dashboard/pages/providers.py` + `templates/providers.html`, nav entry.
- `data/providers.py`: per-provider key presence (names only), Test buttons
  (gateway `/v1/models` probe / ollama probe / key-presence check).
- Secret scrubbing helper shared with Phase 4.
- Test: page serves 200, no values leak in HTML.

## Phase 3 — Model economy policy layer + doctor
- `models/tiers.yaml`: per-tier label/description/cost-ceiling/latency/
  min-context/max-steps + `agent_tiers` defaults (generic model ids only).
- `pipa/commands/doctor.py` + `pipa doctor`: registry validity, tier
  resolution, generated-config sync (`--check` parity), provider
  reachability, credential presence. Exit 1 on hard errors.
- Dashboard Models page: tier descriptions + agent-default mapping.
- Tests: `tests/test_doctor.py` (all-green, all-red, stale-config cases).

## Phase 4 — Install wizard + lifecycle (`pipa update/diagnose`)
- `dashboard/pages/install.py` + `templates/install.html`: staged component
  install (`pipa install` components) via single-flight background runner
  with secret scrubbing (`data/installer.py`).
- `pipa update/check-update/version` (VERSION-based), `pipa diagnose`
  (ports, pids, stale locks).
- Tests: installer single-flight + scrubbing unit tests.

## Phase 5 — Team usage metrics (shared parser)
- `tools/metrics_lib.py`: parse session NDJSON + spend ledger → sync/usage
  rollups. Shared by `pipa usage-report` and Observability Team tab.
- Retention GC (`pipa gc` dry-run/apply) for `state/scratch`.
- Tests: parser fixtures, GC dry-run safety.

## Phase 6 — Task router + routing evals
- `rules/task-router.md` (generic slugs, ≤3, union cap) + `evals/routing.json`
  (≥20 cases, ≥5 negative) + `evals/validate.py`.
- `pipa eval` also runs routing eval; CI-wirable exit codes.
- Tests: validator rejects unknown slug / >3 slugs.

## Phase 7 — MCP bridge conventions
- `mcp/_template/` example bridge with `--status`/`--self-test` contract;
  `mcp/README.md` documents the convention; wiring test extended.
- Tests: template self-test passes; status shape asserted.

## Phase 8 — AOSP project pack + docs + full pass
- `templates/project/aosp/`: AGENTS.md overlay, VHAL/emulator/RADB skills,
  build helpers. `pipa init --type aosp`.
- `docs/` port notes; full `pytest` green.

## Non-goals
Hardcoded Azure/Eldorado endpoints, `device/vw` coupling, Makefile surface
(pipa CLI is the surface), `MEMORY_GIT_*` hardcoded remote (per-project
`.pipa/memory.remote` instead).
