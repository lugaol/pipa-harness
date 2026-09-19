# HS-002: Fail closed on gateway writes — verify compose before restart

- 2026-09-19 (reliability): any dashboard/CLI write that recomposes
  `.effective.yaml` must parse-verify `model_list` BEFORE restarting the
  gateway (`_verify_effective` / `api_gateway_rebuild` discipline). A bad
  write must never take the running gateway down.
- Context: `dashboard/pages/api_status.py` + `api_models.py` — both
  mutating tier routes verify-then-restart; tests pin the guard.
