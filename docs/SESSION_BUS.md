# The Session Bus — canonical NDJSON contract

Every runtime writes agent activity to ONE append-only file per project:

    <project>/.pipa/state/session.log.ndjson

One JSON object per line. This file is the substrate for `pipa status`,
the dashboard, `pipa replay`, `pipa diff`, evals, and any future
flight-recorder tooling. Runtime-agnostic by construction: OpenCode writes
via `pipa hook` (wired through opencode.jsonc), dsh sessions are mirrored in
by tooling, anything else can `pipa hook note ...` directly.

## Canonical schema

```jsonc
{
  "ts": "2026-08-22T12:00:00.000+00:00", // ISO-8601, tz-aware, required
  "event": "post-tool",                  // see EVENTS below, required
  "runtime": "opencode",                 // emitting runtime, optional
  "session_id": "s3",                    // grouping key, optional
  // ── payload, keyed by event ──
  "tool": "bash",                        // pre-tool / post-tool
  "payload": "rg -n foo",                // args (pre-*) / output excerpt (post-*)
  "model": "primary",                    // pre-model / post-model
  "tokens_in": 1200, "tokens_out": 340,  // post-model, optional usage
  "cost_usd": 0.0,                       // post-model, optional
  "text": "human note"                   // note
}
```

Contract rules (enforced by tests/test_hooks_schema.py):

1. Every record carries `ts` (ISO-parseable) and `event` ∈ EVENTS.
2. Unknown fields are forbidden-not: readers MUST ignore extra keys.
3. Writers MUST NOT embed secrets or full message content — payloads are
   excerpts. This bus is a flight recorder, not a transcript dump.
4. Sessions group by `session_id`; absent that, a `session-start` event
   opens an implicit session closed by the next `session-start`.

## EVENTS

| event        | payload keys            | emitted by          |
|--------------|-------------------------|---------------------|
| session-start| runtime                 | runtimes, pipa      |
| session-end  | —                       | runtimes, pipa      |
| pre-tool     | tool, payload           | opencode hook       |
| post-tool    | tool, payload           | opencode hook       |
| pre-model    | model, payload          | opencode hook       |
| post-model   | model, payload, tokens* | opencode hook, spend|
| note         | text                    | anyone              |

## Consumers

| consumer        | reads                          |
|-----------------|--------------------------------|
| `pipa status`   | session.stats()                |
| dashboard       | session.tail()                 |
| `pipa replay`   | sessions(), load_session()     |
| `pipa diff`     | load_session() ×2              |

The spend ledger (`pipa spend`) is a separate NDJSON stream
(state/spend.ndjson) written by the LiteLLM callback — same design rules,
different producer.
