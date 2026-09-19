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

Copy `mcp/config.example.json` as the shape reference. Only `context7` ships
enabled; add others by creating `mcp/<name>/config.json`.

## Bridge script convention

Bridges that do local work (memory, graph, build) live next to their
config as `mcp/<name>/<bridge>.py` and follow one contract (see
`mcp/_template/example_bridge.py`):

- `--status` → one JSON line `{"ok": bool, "detail": str}`
- `--self-test` → exit 0 on success, reason on stderr otherwise
- one `--<tool>` flag per tool, JSON on stdout, soft failures (no
  tracebacks, never print secrets)

Folders starting with `_` (like `_template`) are never merged into
runtime configs and never appear on the dashboard.
