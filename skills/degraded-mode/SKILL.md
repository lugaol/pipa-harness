---
name: degraded-mode
description: "Decide whether to trust a signal and whether to stop, when a subsystem is stale, offline, or unconfirmed. Triggers: gateway down, offline, cache stale, index missing, provider discovery failed, memory store unavailable, optional service down, cannot reach, degraded, fall back."
---

# Degraded mode

Sync is best-effort and silent on failure. This skill exists so a failed
infra call never blocks real work — and so a degraded signal is never
mistaken for a confirmed one.

## Decision table

| Signal | Trust | Mark | Stop or proceed? |
|---|---|---|---|
| Code graph stale or missing | Targeted `grep -R` in that module only | `Graph: stale, grep-scoped` in verification | Proceed |
| Gateway down | Nothing (all gateway routes fail together) | Blocker + `pipa diagnose` tail | **STOP** — no in-harness fallback |
| Provider discovery offline | Last cached catalog | `Discovery: cached (<age>)` | Proceed for known models; **STOP** for brand-new model ids |
| Memory store unavailable | Session log + files only | `Memory: unavailable (<error>)` | Proceed, max 1 retry |
| Optional service down (ollama, graphify) | Remainder of the harness | Gap noted in verification | Proceed |

## Rules

- **One live confirmation per task.** A second candidate needs an explicit
  user request — even when degraded.
- **Stale is a label.** `candidate, unconfirmed` / `not confirmed` /
  `possibly stale — verify`. Never let unconfirmed read as confirmed.
- **Fail closed.** Denial by default, not open.
- **Never invent success.** Blocker + best partial result + what the human
  must provide.

## Reporting format

State the gap in the verification section, not in prose. Example:

```
Graph: stale (index 3 days old), grep-scoped in src/auth only
Memory: unavailable (sqlite locked), session log only
Gateway: up, 51 models
```

## Why this exists

A harness that blocks on infrastructure is a harness that wastes your time.
A harness that silently proceeds on a guessed signal is worse — it produces
confident wrong work. The rule is: **proceed loudly, never proceed falsely.**