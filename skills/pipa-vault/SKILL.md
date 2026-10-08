---
name: pipa-vault
description: "Obsidian vault memory for persistent knowledge across sessions. Triggers: save a note, vault, decision record, hindsight, research note, write memory, read memory."
---

# Pipa Vault Integration

The vault provides persistent memory across sessions. Use it to store and retrieve architectural decisions, research findings, and lessons learned.

## Vault Structure

```
vault/
├── decisions/      # Architectural decisions (as_of/valid_until)
├── research/       # External research findings
├── architecture/   # Architecture documentation
├── triage/         # Triage state
└── hindsight/      # Lessons learned (post-mortems)
```

## Usage

### Store a decision
```python
# Write to vault/decisions/ with frontmatter
---
as_of: 2026-09-20
valid_until: 2026-12-20
status: active
---
# Decision Title
- Context: Why this decision was made
- Decision: What was decided
- Consequence: What happens next
```

### Query the vault
```bash
pipa recall "audio engine architecture"
```

### Check for stale notes
```bash
pipa recall --stale
```

## Memory Hygiene Rules

1. **One bullet = one durable fact**, dated and scoped
2. **Search before write** — check for near-duplicates first
3. **Budgets**: vault notes ≤ 100 lines, project notes ≤ 150 lines
4. **Staleness is a defect** — delete or mark SUPERSEDED

## Integration with OmO

- OmO plans sync to `vault/decisions/`
- OmO evidence syncs to `vault/research/`
- Session state syncs to `state/SESSION.md`
