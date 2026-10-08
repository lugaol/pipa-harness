# AGENTS.md — the map

> This is a **map, not a rulebook**. Anything a tool can enforce belongs in a
> tool. Prose rules rot, conflict, and compete for attention.
> Keep this file near 100 lines. Add here only what an agent cannot look up.

## Where things live

| Thing | Location |
|---|---|
| This harness (global) | `pipa_harness/` |
| Project overlay | `<project>/.pipa/` — the only harness state a project should own |
| Model gateway | LiteLLM on `:4000`, OpenAI-compatible |
| Model catalog (generated) | `models/.effective.yaml` — **never hand-edit** |
| Tier assignments | `state/tier_assignments.json` — the single source of truth for tier → model |
| Live agent/model config | `~/.config/opencode/opencode.jsonc` |
| Memory | `state/memory.db`, `vault/{decisions,research,architecture,hindsight}/` |
| CLI | `bin/pipa` |
| **Enforced checks** | `bin/pipa-check` — git hooks + CI, not prose |
| Knowledge graph | `graphify query "<q>"` — try before grep |

## Layers

**Layer 0** (global) — this file, `rules/`, `agents/`, `skills/`.
**Layer 1** (per project) — `<project>/.pipa/`. If absent, the harness is
inactive for that project; do not assume overlay state exists.

Conflict priority:
`turn instruction > AGENTS.md > .pipa/ overlay > rules/ > skills/ > vault`

## Model routing

All model calls go through the gateway. Never call a provider directly.
Tiers: `jev`, `lowest`, `low`, `mid`, `high`, `xhigh`.

**Do not write model ids into config files or prompts.** Read them from
`state/tier_assignments.json`. A hardcoded id is a future HTTP 400.

> **Invariants** — verify with `bin/pipa-check config`, `models`, and `tiers`:
>
> 1. Every model named in `opencode.jsonc` appears in `GET :4000/v1/models`.
> 2. Every model an agent depends on is **genuinely callable** — not merely
>    listed. Some upstream providers reject requests arriving via a third-party
>    proxy ("free tier can only be used from within OpenCode") while still
>    advertising the model in the catalog. Listing a model proves nothing;
>    only a live call does.
> 3. Every model in the opencode picker is callable. A listed-but-broken model
>    is worse than an absent one — the user picks it and the session dies.
>
> Prefer a **tier alias** in an agent's `model:` — `litellm/mid`, never
> `litellm/kilo-auto/free`. The alias is resolved by the gateway from
> `state/tier_assignments.json`, so reassigning a tier on the dashboard moves
> every agent at once. A concrete id freezes that agent until someone edits
> the file, and is a future HTTP 400 when the provider retires it.
> `tools/evals/run.py` fails the build if any agent hardcodes an id.

### Provider reality (verified 2026-10-03, re-verify before trusting)

`pipa-check models` and `pipa-check tiers` are the authority here; the numbers
below are a snapshot. Reach for the tool, not for this table.

The catalog lists whatever providers report, and free-tier endpoints fail in
ways that look exactly like working configuration. Four traps, all verified:

| Trap | Example | Symptom |
|---|---|---|
| Proxy-restricted free tier | `opencode-zen` `*-free` (7 of 8) | `free tier can only be used from within OpenCode` |
| Needs a higher plan | `kimi-for-coding-highspeed` | HTTP 401 "subscription does not have access" |
| Engine overloaded | `kimi-for-coding` | HTTP 429, persistent across retries |
| Flaky / rate-limited | `qwen/qwen3.8-27b:free`, `thinkingmachines/inkling-small:free` | 429 or timeout, intermittent |

Working: **kilo**, **kimi** (`k3`, `k3-256k` — the paid plan), and
`space-bunny-free` from opencode-zen. Kimi must be reached at
`https://api.kimi.com/coding/v1` — `api.moonshot.ai` returns 401 for this key.

Two structural rules exist because ignoring them produced invisible models:

- **Provider attribution has one owner** (`pipa.providers.resolve_backing`).
  When two providers report the same id, the *later* one serves it. Registry
  and gateway composer must never each pick their own winner, or a working
  model gets marked inactive (wrong provider's key checked) and vanishes from
  the picker.
- **A `keep:` filter in `providers.yaml` that does not exist keeps nothing.**
  It used to fall through to "keep everything", which let one misconfigured
  provider inject 84 unusable ids (`jev_only` was the missing name).

Routing decisions: the slug vocabulary and thresholds live in
`agents/router.md`. Do not restate them here.

## Workflow

Plan → build, with a bridge. `specs/` holds briefs, PRDs, architecture.
`stories/NN-*.md` holds self-contained work items a worker can execute
without asking a question. Small changes skip planning and build directly.

Check `skills/` before acting: process skills first (brainstorming,
debugging, TDD, verification-before-completion, subagent-driven-development),
then domain skills. A skill that matches is not optional.

## Subagents

opencode provides `build`, `plan` (read-only), and `general` (search).
`agents/` adds pipeline personas on top.

Read a target agent's frontmatter before invoking it — permissions and
model are declared there. Delegate by role, not by name-guessing.

## Approval gates — required, not optional

Ask **before** any of these:

- `git push`
- `git commit` (prefer no commits unless asked)
- `rm` on tracked files
- external data exfiltration

## Hard prohibitions

- No `eval()`, `exec()`, or `Function()` on untrusted input.
- Never log or store secrets, tokens, passwords, or PII.
- Never hardcode secrets — use env vars or `{file:}`.
- Never suppress type errors (`as any`, `@ts-ignore`, `@ts-expect-error`).
- Never delete or weaken tests to make a run pass.
- Never `git add -A`; stage only intended files.
- Fail closed, not open.

## Enforced, not remembered

Installed hooks: `pipa-check install-hooks`. Local only — CI is still
required to enforce on other machines.

| Rule | Enforced by | Status |
|---|---|---|
| No secrets in commits | `pipa-check secrets` (pre-commit) | active; gitleaks if installed, else pattern fallback |
| Commit message ≤72 chars, conventional shape | `pipa-check commit-msg` | active |
| No pushes straight to `main` | `pipa-check branch` (pre-push) | active |
| Declared models exist in the gateway | `pipa-check config` | active, run manually |
| Every model in the picker is callable | `pipa-check models` | active, run manually (live, ~1 req/model) |
| Assigned tiers are genuinely callable | `pipa-check tiers` | active, run manually |
| No unreachable dashboard surface | `pipa-check deadcode` | active, in `all` |
| Skills are discoverable (name/dir/triggers) | `pipa-check skills` | active, in `all` + CI |
| Agents run on tiers, never a model id | `tools/evals/run.py` + `test_round2` | active (CI + suite) |
| Agents keep their reporting contract | `tools/evals/run.py` | active (CI + suite) |
| Gateway never starts on an unverified config | `start_litellm` → `verify_effective` | active (HS-002) |
| New behavior ships with a test | **nothing enforces this** | prose only |
| Branch per feature | **nothing enforces this** | prose only |

`pipa-check` exits **three-valued**: `0` pass, `1` a violated invariant, `2`
unverifiable. A check that cannot reach its evidence returns 2 and the rollup
prints `INCONCLUSIVE` — never `PASSED`. If you see `PASSED`, every invariant
was genuinely verified.

If you catch yourself repeating a rule, **promote it to `bin/pipa-check`**
instead of adding it to this file. That is the whole point.

## Memory

Search before write: `pipa recall "<query>"`. One dated, scoped fact per
bullet. Trim over append; delete what is stale. Memory is best-effort —
never let it block a task.

## Verify

Use the project's own test and build commands. Report pre-existing
failures as pre-existing; do not fix them unasked.

## Reporting

Outcome plus evidence — `file:line`, command exit codes. No narration of
machinery.

## Reporting

Every agent that delegates or delivers a result ends with **one line** of
JSON, not a prose block:

```json
{"event":"delegation","agent":"dev","outcome":"done","tier":"mid","skills":["debugging"],"files":["src/auth.py"],"verified":true}
```

- `outcome` — `done` | `partial` | `blocked` | `failed`. Claim `done` only
  when acceptance criteria are met and verification passed. `blocked` with a
  `note` is the honest alternative to guessing.
- `verified` — did you actually run the verification command? `false` marks
  the result unconfirmed; `pipa contract` lists those separately.
- `files` — what you touched, so the parent can review precisely.

`pipa contract` parses these into a run summary. The previous prose
`## Harness usage` block was emitted by nine files and read by nothing.

## Talking to other agents

`task()` covers parent → child with a return value. It does not cover
siblings, or durability across calls. For those, use the bus — a shared
append-only board at `.pipa/state/bus.ndjson`:

```sh
pipa bus post --from explorer --to dev --kind finding \
  --body "Token validation: src/auth/session.py:42"
pipa bus read --to dev --since 12      # cursor: only what is new
pipa bus list                          # whole board
```

Read the bus **before** broad exploration — a sibling may already have
answered. Post `finding` when you learn something another agent needs, and
`handoff` when you finish work someone else depends on. `blocker` and
`question` are for work you cannot finish alone.

Addressed messages go to one agent; `--to all` is readable by everyone,
which is how sibling discovery works.
