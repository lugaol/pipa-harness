# NN — <short-name>

## Context
<2-3 lines: why this story exists, what feature it belongs to>

## Goal
<One sentence linking this story to the feature goal from SESSION.md>

## Acceptance criteria
- [ ] <binary, testable criterion 1>
- [ ] <criterion 2>

## Implementation
<Ordered steps with file:line references from the architecture doc>

1. Modify `path/to/file.ts:42` — <what to change>
2. Create `path/to/new-file.ts` — <what it does>

## Test plan
- [ ] <regression test description>
- [ ] <edge case to verify>

## Handoff packet
```yaml
task: implement
goal: <from SESSION.md>
context:
  - file:path:line
acceptance_criteria:
  - <from above>
fallback: if blocked, escalate to @architect or ask user
```

## Refs
- Architecture: `specs/<feature>/architecture.md`
- PRD: `specs/<feature>/prd.md`
- Goal: `state/SESSION.md`
