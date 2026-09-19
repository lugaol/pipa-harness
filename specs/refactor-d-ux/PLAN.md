# Phase D — UX consolidation (spec)

Executes the REMAINDER of specs/refactor-simplify (Phase 3 CLI split,
providers.yaml, batch save, auto-seed, observability merge are done).
Phase 4 legacy removal is explicitly next-major — out of scope.

## Stories
- **D1 — nav 11 → 6**: Status (/), Models (/models), Team (/team),
  Observability (/observability), Knowledge (/knowledge),
  Rules & Skills (/docs). All other routes stay mounted (bookmarks safe).
  In-page cross-links cover the unlisted: Models→Tier Manager/Agents/
  Providers (exist — verify), Knowledge→Graph (add if missing),
  Status→Install (add if missing).
  **REVERTED per user review**: all 11 sidebar links restored
  (Tiers, Agents, Providers, Graph, Install delinked felt like page
  removal). Routes were never touched. Cross-links kept.
- **D2 — AGENTS.md diet (179 → ~100 lines)**: keep router + workflow +
  golden rules + agents + tiers + transparency footer. Move token-economy
  internals, memory-store detail, and approval-gate frontmatter mapping to
  AGENTS_OPERATIONS.md. No meaning change — pure move. Landed at 124 lines
  (floor with all HARD rules + router + workflow + footer verbatim is ~119;
  the footer exact shape moved to OPERATIONS — safe because all 8
  agents/*.md carry the mandate individually and the mandate line names
  every field).
- **D3 — single `apply_tiers()`**: new `pipa/model_registry.apply_tiers(
  assignments) -> (ok, msg, warnings)` (validate + persist + missing-key
  warnings). Both batch endpoints (`PUT /api/tier-models`,
  `POST /api/tiers/batch`) call it; batch keeps form parsing + agent
  overrides + redirect, JSON keeps its validation errors. No UX change,
  logic owned once. Tests: unknown tier/model rejected, warnings listed.
- **D4 — status polling**: `renderStatusGrid()` re-runs every 15s when the
  tab is visible (`document.hidden` guard, silent — no toasts on poll).
  Keys panel refreshes on `visibilitychange` return. Tests: static JS
  assertions (interval + guard present), live DOM stable across polls.

## Constraints
- No route renames/removals; redirect pages untouched.
- test_api.py crawl list unchanged (routes identical).
- AGENTS.md keeps every HARD rule verbatim.
