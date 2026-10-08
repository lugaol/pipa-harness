---
name: pipa-graphify
description: "Persistent code knowledge graph — query BEFORE reading files. Triggers: code question, architecture, file relationships, where is, how does, graphify."
mcp:
  pipa-graphify:
    command: graphify-mcp
    args: ["--project", "${PROJECT_ROOT}"]
    env:
      GRAPHIFY_DB: "${PROJECT_ROOT}/graphify-out/graph.json"
---

# Pipa Graphify Integration

Every agent MUST query the code knowledge graph before reading files.

## Usage

### Query for broad context
```
graphify query "How does the audio engine work?"
```

### Find relationships between concepts
```
graphify path "AudioEngine" "GestureRecognizer"
```

### Get plain-language explanation
```
graphify explain "BlowDetector"
```

## Rules

1. **Graph first, grep second** — always query graphify before grep
2. **Cite file:line refs** — include file paths and line numbers in responses
3. **No pasted code** — reference files, don't copy them
4. **Fallback to grep** — if graphify unavailable, use grep with `--include`

## Integration with Jev

When classifying tasks, graphify provides context for better routing:
- Query graphify to understand task scope
- Use results to improve Jev classification confidence
- Route to correct agent with code-aware decisions
