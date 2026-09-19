# Phase A — De-duplicate core (spec)

Goal: one owner per capability. `pipa/` owns logic; `dashboard/data/` adapts; no `sys.path` hacks.

## Findings (verified, not assumed)
- spend/registry/recall twins are **already thin adapters** (prior hard-refactors). No merge needed — verify only.
- Real duplication: `tools/metrics_lib.py` imported via `sys.path.insert` hacks in 2 places; `dashboard/pages/api.py` (535 lines, 6 domains) vs ia's `routers/` per-domain pattern.

## Stories
- **A1**: Move `tools/metrics_lib.py` → `pipa/metrics.py`. Update `pipa/commands/usage.py`, `dashboard/pages/observability.py`, `tests/test_metrics.py`. Delete the `sys.path.insert` hacks. No behavior change.
- **A2 (verify-only)**: recall (`pipa/recall.py` owns; `data/memory.py:254`, `data/graph.py:85` delegate) + spend/registry adapters — confirm no logic duplication, no change.
- **A3**: Split `dashboard/pages/api.py` → `api_common.py` (helpers, `_`-prefixed = unmounted) + `api_status.py` (status/ollama/gateway/env-keys/dashboard) + `api_models.py` (tier-models/tiers/agent-tiers/agents) + `api_install.py` (install/state) + `api_graph.py` (graph/*) + `api_docs.py` (docs/*). Routes byte-identical.
- **A4**: Full verify — `pytest` green, live page+API crawl, mutating roundtrips with state restore, browser open.

## Constraints
- No route renames; `tests/test_api.py` must pass unmodified.
- No session-bus / spend-ledger contract changes.
- Key-names-only discipline untouched.
