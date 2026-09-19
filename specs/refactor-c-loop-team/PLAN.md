# Phase C — Loop + Team (spec)

Goal: unattended signal-gathering (report-only) + a multi-user adoption view.
Generic signals only — no Jira/Bitbucket/vault-shard specifics (those stay
in the AOSP pack).

## Stories
- **C1 — L1 triage loop**: new `pipa/triage.py` (`collect_signals()` —
  pure sink over existing readers, all best-effort) + `pipa triage`
  command (prints report, rewrites `vault/triage/STATE.md`, `--json`
  for machines). Signals: doctor pass/warn/fail; graph freshness
  (harness + active project, by `graph.json` mtime: fresh <7d, stale with
  age, missing); stale notes count (B6); GC eligibility counts (B5);
  session volume (7d) + error events. Report-only: no code edits, no
  pushes, no auto-fix. Tests with tmp dirs + stubbed readers.
- **C2 — Team page**: new `/team` route (`dashboard/pages/team.py`,
  server-rendered like Observability) composing `pipa.metrics`
  (sessions/day, top tools/models, runtimes, spend) + session durations
  (avg/median/longest from start/end) + alerts strip from
  `pipa/triage.py` (doctor fails, stale notes, GC eligible, stale graphs)
  + harness version. Nav: Overview section after Observability.
  Tests: page 200, cards/tables present, alerts render with stubbed signals.

## Constraints
- Triage never writes beyond `vault/triage/STATE.md`; never fails loudly
  (degraded signals become `unknown`, not errors).
- No new data readers — compose `pipa.session`, `pipa.spend`,
  `pipa.metrics`, `pipa.recall`, `pipa.memory_gc`, doctor `_collect`.
- STATE.md schema is machine-readable (keep the shape).
