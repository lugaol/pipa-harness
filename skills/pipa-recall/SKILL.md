---
name: pipa-recall
description: "One-query memory over vault + memory.db + code graph (pipa recall). Triggers: remember, recall, what did we decide, prior art, has this come up before, search memory, past sessions."
---

# Pipa Recall Integration

Query harness memory before assuming context. Single entry point, bounded output.

## Usage

```bash
pipa recall "why did we choose X"          # fan-out: vault + memory.db + graph
pipa recall "audio engine" --limit 5       # fewer rows
pipa recall --stale                        # expired / over-budget notes
pipa recall "text" --digest                # compact digest for prompts
```

## Rules

1. **Recall before inventing** — if the answer might exist in memory, query first.
2. **Cite the source** — vault note path or graph node, with date.
3. **Staleness is a defect** — flag expired notes instead of following them.
4. **Never store secrets** — no tokens, keys, or personal data in memory.

## Integration with Jev

Explore and research routes suggest this skill: recall results sharpen task
scope before the agent reads code.
