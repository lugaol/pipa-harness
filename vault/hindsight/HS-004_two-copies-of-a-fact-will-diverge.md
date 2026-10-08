# HS-004: Two copies of a fact will diverge — delete one, not add a check

- 2026-10-03 (agent tiers): `runtime.AGENT_MODEL_MAP` and
  `models/tiers.yaml::agent_tiers` held the same mapping and disagreed
  (`orchestrator: xhigh` vs `mid`). The fix was to delete the hardcoded map
  and derive from the YAML, not to add a drift check. A check tells you they
  differ; only one owner makes them unable to.
- 2026-10-03 (provider attribution): the registry took the FIRST provider to
  report a model id, the gateway composer let the LAST one win. A model the
  gateway served correctly through kilo was marked inactive (openrouter's key
  was unset) and dropped from the picker. One owner —
  `providers.resolve_backing()` — now serves both.
- 2026-10-03 (dashboard): `data/system.py` re-implemented `pipa status` with
  no severity model, so the same dead gateway read FAIL in one place, WARN in
  `pipa doctor`, and red on the page. `status.collect_checks()` is the owner
  now.
- Rule: when you find "X and Y should agree", first ask which one to delete.
  Answer that before writing the check that compares them.
- Context: `pipa doctor` shipped a permanent WARN about its own disagreeing
  tier map for weeks.
