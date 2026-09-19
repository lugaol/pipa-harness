# mcp/_template/ — starting point for a new MCP integration

1. Copy this folder to `mcp/<name>/`.
2. Implement the backend in `example_bridge.py` (rename it), keeping the
   `--status` / `--self-test` / `--<tool>` flag contract.
3. Copy `config.json.example` to `config.json`, set `"enabled": true`,
   and point the command at your bridge.
4. Verify: `python3 mcp/<name>/<bridge>.py --self-test`
   and `pipa status` picks it up after `pipa up`.

Underscore-prefixed folders (`_template`) are never merged into runtime
configs and never listed on the dashboard.
