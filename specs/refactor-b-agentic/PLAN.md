# Phase B — Agentic upgrades (spec)

Goal: agents that self-correct. Port ia's agentic patterns, genericized; no AOSP specifics.

## Stories
- **B1 — recommendations source**: new `pipa/recommendations.py` with
  `recommended_tier(agent)` derived from `pipa.runtime.AGENT_MODEL_MAP`
  (single source — never a mirrored map that can drift, cf. ia's warning).
  Dashboard `/api/dashboard` agent entries gain `recommended`; Agents table
  shows "recommended: X" under the default line. Tests: every discovered
  agent has a recommended tier in TIER_ALIASES or "".
- **B2 — orchestrator (primary) tier**: today `AGENT_MODEL_MAP["orchestrator"]`
  exists but the wire path ignores it (primary = strongest assigned tier).
  Add `primary_tier()` (override > map default) in `pipa/runtime.py`;
  `render_opencode_config` pins `cfg["model"]` to the orchestrator tier when
  resolvable, else falls back to strongest-assigned (current behavior).
  New routes in `api_models.py`: `PUT /api/orchestrator` {tier} + reset
  (override store; unknown tier → 400). Dashboard payload gains an
  `orchestrator (primary)` agent row (renders via existing agents.js).
  Tests: wire fallback matrix + route validation + reset roundtrip.
- **B3 — qa-verdict schema**: new `evals/qa-verdict.schema.json` (ia port,
  genericized: `emulator` dropped, `build` required, `criteria[]` with
  evidence required). `validate_verdict()` in `evals/validate.py` (pure,
  no I/O) + `tests/test_qa_verdict.py` with PASS/FAIL samples.
  `agents/qa.md` Output section points at the schema.
- **B4 — hindsight convention**: `vault/hindsight/README.md` (one lesson per
  file, `HS-NNN_slug.md`, dated/scope/one-fact) + 2 seeds from real history
  (adapter ownership — Phase A; fail-closed verify — gateway restart).
  Indexed by existing `rglob("*.md")` — no recall changes.
- **B5 — memory-gc**: new `pipa/memory_gc.py` (`collect_candidates()` pure:
  `state/summaries/*.md` older than N days → monthly rollup under
  `state/summaries/rollups/`; `state/scratch/**` older than N days → prune
  list; vault notes over budget → report-only, never auto-prune).
  CLI `pipa memory-gc [--apply] [--manifest]` (dry-run default).
  Never touches spend ledger, session bus, vault knowledge.
  Tests with tmp dirs.
- **B6 — stale check**: `pipa recall --stale` report mode (expired
  `valid_until` + untouched >180d + over-budget notes), read-only, exit 0
  with report (empty = clean). Reuses `pipa/recall.py` parsing. Tests.

## Constraints
- No route renames; primary-model fallback preserved (no behavior change
  when orchestrator tier unassigned).
- Key-names-only, 200KB doc cap, jail discipline untouched.
- No spend-ledger / session-bus contract changes.
