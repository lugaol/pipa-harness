# Token economy
- [HARD] Every tool round re-sends the whole conversation: cost = context size × rounds. Keep both small.
- [SOFT] Read once, read wide: one large file window beats five small slices. Never re-read a file already in context.
- [SOFT] Never dump raw logs or big outputs into context. Filter first (`tail`, `grep -iE 'error|fail'`, `| head -20`). Show the tail that matters, not the firehose.
- [SOFT] Bounded search: query the code graph before repo-wide grep; plain grep with `--include` + `head` elsewhere. A search returning >50 lines was done wrong.
- [SOFT] Delegate transcripts, import answers: open-ended exploration goes to `@explorer`/subagents — the search transcript dies in their context; only their short answer enters yours.
- [SOFT] One-shot local models for text tasks (commit message, summary, quick explanation): `tools/litellm/task.sh "…"` on the free local backend instead of a paid subagent turn.
- [SOFT] Summarize before continuing long work: past ~40 tool rounds, write a compact state note (done/left-next/files-touched) — future turns then need less history.
- [SOFT] Skills are lazy-loaded for a reason: don't preload rule/skill files "just in case". Every always-loaded line is paid on every turn.
- [SOFT] Output discipline (output tokens cost more than input): outcome + verification evidence, `file:line` refs instead of pasted snippets, no filler.
