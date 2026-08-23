# {{PROJECT_NAME}} — project context

{{PROJECT_DESCRIPTION}}

This file carries ONLY project-specific facts. The global harness
(rules, skills, agents, workflow) lives in the pipa install and is
loaded automatically. Add here what makes this project different.

## Golden rules
- [HARD] Never commit or push unless the user explicitly asks.
- Add project-specific invariants (performance budgets, conventions).

## Commands
- Build: `{{BUILD_COMMAND}}`
- Tests: `{{TEST_COMMAND}}`

## Project rules & memory
- `.pipa/rules/*.md` — loaded as instructions alongside the global tier.
- `.pipa/memory/` — decisions/ research/ with as_of/valid_until; query with
  `pipa recall "<question>"`.
- `.pipa/skills/` — OPTIONAL project-only skills; same name = wins over a
  global skill.
