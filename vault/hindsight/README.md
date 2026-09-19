# Hindsight — durable lessons (one file per lesson)

Format: `HS-NNN_slug.md`. One bullet = one durable fact: dated, scoped,
and phrased as guidance, not narrative. Narratives go in session logs.

Template:

```markdown
# HS-NNN: <one-line lesson>

- <YYYY-MM-DD> (<scope>): <the lesson — what to do / not do, and why>
- Context: <one line — where it bit us>
```

Rules:
- Lessons only — no TODOs, no decisions (those live in `decisions/`).
- Stale lessons get deleted, or rewritten as
  `- <date> SUPERSEDED: <one-line why>` when the history matters.
- Indexed by the memory store (`vault/**/*.md`) — no extra wiring.
