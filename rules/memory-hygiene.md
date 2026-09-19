# Memory hygiene
- [HARD] Never store secrets, tokens, certificates, location, or personal data in the vault or memory.db.
- [SOFT] Search before write: `pipa recall "<query>"` first; if a near-duplicate exists, UPDATE it instead of appending.
- [SOFT] One bullet = one durable fact, dated and scoped.
  BAD: `- fixed bug in login` (narrative, undated, unscoped).
  GOOD: `- 2026-09-01 (auth): OAuth refresh races logout — guard with a token-generation check`.
  Narratives go in session logs, never in decisions/research notes.
- [SOFT] Trim over append: editing an over-budget note means consolidating it in the same pass (merge/delete, don't just append).
  Budgets: project memory notes ≤ 150 lines, vault notes ≤ 100 lines.
- [SOFT] Staleness is a defect: outdated guidance misleads future sessions. Delete it, or rewrite as `- <date> SUPERSEDED: <one-line why>` only when the history matters.
- [SOFT] Memory is best-effort and silent on failure — never let a recall/store call block the task. One retry max, then proceed and note the gap.
