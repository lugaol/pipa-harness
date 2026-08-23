# mcp/<name>/ — MCP integration registry

One folder per MCP integration. `pipa` merges every enabled entry into the
runtime configs at wire time (`pipa init` / `pipa up` / `pipa runtime set`).
**Adding an integration = dropping a new folder here. Nothing else changes.**

## config.json schema

```json
{
  "name": "context7",          // tool namespace; defaults to folder name
  "enabled": true,             // false = ignored by the composer
  "mcp": { ... }               // verbatim OpenCode MCP server block
}
```

The registry also emits `<name>_*: allow` permission entries for each
enabled server.

## Planned integrations (scaffold your credentials via env, never in git)

- `bitbucket/` — PRs, pipelines (env: BITBUCKET_TOKEN)
- `jira/` — issues, sprints (env: JIRA_TOKEN)
- `figma/` — design context (env: FIGMA_TOKEN)

Copy `context7/config.json` as the shape reference.
