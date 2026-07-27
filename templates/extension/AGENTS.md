# {{PROJECT_NAME}} — pipa harness extension

{{PROJECT_DESCRIPTION}}

This `.harness_extension/` directory carries only project-specific context.
The base rules, skills, agents, and workflow come from the globally installed
pipa_harness (`~/.config/opencode` points at it). Edit this file with your
project's facts; delete what you don't need.

## Golden rules
- [HARD] Never commit or push unless the user explicitly asks.
- Add project-specific invariants here (e.g. performance budgets, conventions).

## Commands
- Build: `{{BUILD_COMMAND}}`
- Tests: `{{TEST_COMMAND}}`

## Routing (load ONLY when the trigger matches)
| Task involves...        | Load                                   |
|-------------------------|----------------------------------------|
| <domain keyword>        | skills/<your-skill>/SKILL.md           |

Base routing (graphify, debugging, code-review, release, performance, …) is
already loaded globally by pipa_harness.

## Repo map
`src/` (·) `tests/` (·) `<key dirs>` — replace with your layout.
