---
name: graphify
description: "Use for any question about a codebase, its architecture, file relationships, or project content — especially when graphify-out/ exists, where the question should be treated as a graphify query first. Turns code/docs into a persistent knowledge graph with query/path/explain tools."
---
# /graphify

Persistent knowledge graph of the codebase. Query BEFORE grepping for architecture questions.

## Usage
```
/graphify                                             # full pipeline on current directory
/graphify <path>                                      # full pipeline on specific path
/graphify <path> --update                             # incremental - re-extract only changed files
/graphify query "<question>"                          # BFS traversal - broad context
/graphify path "AuthModule" "Database"                # shortest path between two concepts
/graphify explain "SwinTransformer"                   # plain-language explanation of a node
```

## What to do when invoked
1. If `graphify-out/graph.json` exists AND the request is a question (not a rebuild), run
   `graphify query "<question>"` immediately — skip extraction entirely.
2. For explicit rebuilds, run `/graphify <path>` or `/graphify --update`.
3. For broad review, read `graphify-out/GRAPH_REPORT.md`.
4. If graphify can't answer → fall back to grep without error.

## Maintenance
- Post-commit hook rebuilds AST automatically (free, no LLM).
- After doc changes: `graphify extract . --update` (heavy; standalone).
- Scope control: `.graphifyignore` (build output, deps, graphify's own skill).
