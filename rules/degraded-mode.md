# Degraded mode
- [HARD] Sync is best-effort and silent on failure (offline, missing keys, merge conflict) — never let an infra call block work. This rule owns working degraded.

## Decision table

| Signal | Trust | Mark | Stop or proceed? |
|---|---|---|---|
| Code graph stale/missing | Targeted `grep -R` in that module only | `Graph: stale, grep-scoped` in verification | Proceed |
| Gateway down | Nothing (all gateway routes fail together) | Blocker + `pipa diagnose` tail | STOP — no in-harness fallback |
| Provider discovery offline | Last cached catalog | `Discovery: cached (<age>)` | Proceed for known models; STOP for brand-new model ids |
| Memory store unavailable | Session log + files only | `Memory: unavailable (<error>)` | Proceed, never >1 retry |
| Optional service down (ollama, graphify) | Remainder of the harness | Gap noted in verification | Proceed |

## Rules

- [SOFT] Stale/unconfirmed is a label, not a guess: `candidate, unconfirmed` / `not confirmed` / `possibly stale — verify`.
- [SOFT] One live confirmation per task; a second candidate needs an explicit user request — even degraded.
- [HARD] Never invent success: report blocker + best partial result + what the human must provide.
