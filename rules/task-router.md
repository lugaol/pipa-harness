# Task router
- [HARD] Route first: every non-trivial task starts with one line
  `route: <slug> + <slug> · tier <t> · <model>` — max 3 slugs, rest goes to
  `deferred:`. `<model>` is the tier's dashboard-resolved model, never a
  hardcoded id.
- [HARD] Union cap: at most 3 slugs per route (`base` + 2). More signals →
  pick the 2 strongest, defer the rest explicitly.
- [SOFT] Slug vocabulary (closed — keep in sync with `evals/routing.json`):

| Slug | Meaning | Tier hint |
|---|---|---|
| `base` | always-on harness context | lowest |
| `playbook` | recurring/daily team task | low |
| `memory` | needs vault/project memory first | lowest |
| `impl` | code change, small and scoped | mid |
| `network` | external APIs, endpoints, auth | mid |
| `build-failure` | broken build, CI red | mid |
| `hard-bug` | root-cause unknown, deep debug | high |
| `tdd` | test-first development requested | mid |
| `build` | build system / packaging change | mid |
| `full-test` | release/regression validation pass | high |
| `perf` | latency, memory, benchmarks | high |
| `security` | secrets, auth, input validation | high |
| `review` | code review of a change | high |
| `merge` | conflict resolution, rebases | mid |
| `multi-story` | spans several stories/specs | high |
| `handoff` | context transfer between agents | low |
| `meta` | harness itself needs changing | high |
| `docs` | documentation lookup or writing | low |
| `delegate` | fan out to subagents | mid |
| `triage` | report-only signal gathering (L1) | lowest |

- [SOFT] Wide-not-deep: fan out only when the task is wide (many
  independent items); keep one agent when it is deep (one coupled failure).
  Parallel agents only with disjoint file lists.
- [SOFT] Validate routes with `pipa eval` (runs `evals/validate.py` over
  `evals/routing.json`). Router/skill edits must keep evals green.
