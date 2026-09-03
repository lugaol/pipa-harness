# 01 — session-bus plugin for OpenCode

> Worked example of the two-phase handoff (see `specs/README.md`). This story
> was executed as written — keep it as the reference when cutting new stories.

## Context
The flight recorder promised in README.md needs every runtime appending to one
NDJSON log. The dsh side had no equivalent gap, but nothing wired OpenCode to
`pipa hook`, so sessions were only recorded when instrumented by hand.

## Goal
OpenCode sessions land in `<project>/.pipa/state/session.log.ndjson`
automatically at wire time, with zero per-project config.

## Acceptance criteria
- [ ] `pipa runtime set opencode` installs a plugin under
      `~/.config/opencode/plugin/` that forwards tool/session/model events via
      `pipa hook`.
- [ ] Plugin is create-only: an existing file is never overwritten.
- [ ] `pipa status` fails the extension check when the plugin is missing.
- [ ] Events conform to `docs/SESSION_BUS.md` (`tests/test_hooks_schema.py`).

## Implementation
1. Create `clis/opencode/plugin/pipa-session-bus.js` — Bun plugin using the
   documented hooks (`event`, `tool.execute.before/after`, `chat.params`);
   spawns `pipa hook ...` fire-and-forget with `PIPA_RUNTIME=opencode`.
2. Modify `pipa/runtime.py:258` (`wire_opencode`) — render the template,
   substituting `@@PIPA_BIN@@` → `<root>/bin/pipa`; write only when absent.
3. Modify `pipa/scaffold.py:check_extension` — add a
   "session bus plugin wired" check for the opencode runtime.

## Test plan
- [x] `tests/test_wiring.py::test_wire_opencode_installs_session_bus_plugin`
- [x] Schema round-trip still passes: `pytest tests/test_hooks_schema.py`

## Handoff packet
```yaml
task: implement
goal: one session bus shared by all runtimes
context:
  - file:pipa/runtime.py:258
  - file:clis/opencode/global.jsonc
acceptance_criteria:
  - plugin installed + create-only + status-gated
fallback: if blocked, escalate to @architect or ask user
```

## Refs
- Architecture: `docs/ARCHITECTURE.md`
- Contract: `docs/SESSION_BUS.md`
- Goal: `state/SESSION.md`
