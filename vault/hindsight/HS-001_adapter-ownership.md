# HS-001: Adapters, not twins — pipa/ owns logic, dashboard adapts

- 2026-09-19 (architecture): every capability has exactly one owner in
  `pipa/`; `dashboard/data/` modules are thin adapters that degrade to
  empty results, never re-implement. Twins (spend, recall, registry,
  override store) were merged in Phase A; `tools/` holds scripts, not
  importable logic (`metrics_lib` → `pipa/metrics.py`).
- Context: `specs/refactor-a-dedup/PLAN.md` — the "twins" audit found most
  pairs already adapters; the real duplication was `sys.path` hacks.
