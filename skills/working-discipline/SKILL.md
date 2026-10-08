---
name: working-discipline
description: "Token economy, memory hygiene, and honest reporting under long sessions. Triggers: long-running task, context full, compacting, saving a note, writing memory, recap, summarize, out of context, what did we do, session log."
---

# Working discipline

The always-loaded map carries the prohibitions. This skill carries the
operational discipline that only matters *during* work — deliberately not
in the hot path, because these are tactics, not constraints.

## Token economy

Every tool round re-sends the whole conversation. Cost = context × rounds.

- **Read once, read wide.** One large window beats five small slices. Never
  re-read a file already in context.
- **Never dump raw logs.** Filter first (`tail`, `grep -iE 'error|fail'`,
  `| head -20`). Show the tail that matters, not the firehose.
- **Bounded search.** Query the knowledge graph before repo-wide grep. A
  plain grep gets `--include` and `head`. A search returning >50 lines was
  done wrong.
- **Delegate transcripts.** Open-ended exploration goes to a subagent. The
  search transcript dies in *their* context; only their short answer enters
  yours.
- **Summarize before continuing.** Past ~40 tool rounds, write a compact
  state note (done / left-next / files-touched). Future turns then need less
  history.
- **Output discipline.** Outcome + `file:line` refs instead of pasted
  snippets. No filler.

## Memory hygiene

- **Never** store secrets, tokens, certificates, location, or personal data.
- **Search before write.** `pipa recall "<query>"` first. If a near-duplicate
  exists, UPDATE it instead of appending.
- One bullet = one dated, scoped fact.
  - BAD: `- fixed bug in login`
  - GOOD: `- 2026-09-01 (auth): OAuth refresh races logout — guard with a token-generation check`
- **Trim over append.** Editing an over-budget note means consolidating it
  in the same pass (merge/delete, don't just append).
  Budgets: project memory ≤150 lines, vault notes ≤100 lines.
- **Staleness is a defect.** Delete it, or rewrite as
  `- <date> SUPERSEDED: <one-line why>` only when the history matters.
- Best-effort and silent on failure — never let recall/store block the task.
  One retry max, then proceed and note the gap.

## Honest reporting

- **Never invent success.** Report blocker + best partial result + what the
  human must provide.
- **Stale is a label, not a guess.** Write `candidate, unconfirmed` /
  `possibly stale — verify`. Never let unconfirmed read as confirmed.
- **One live confirmation per task.** A second candidate needs an explicit
  user request, even degraded.
- **Pre-existing failures are pre-existing.** Report them as such; fixing
  them unasked is scope creep.