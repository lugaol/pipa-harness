"""MCP registry reader + enable/disable toggle.

The registry lives at <harness>/mcp/<name>/config.json (one folder per
server, see mcp/README.md). Toggling flips the top-level "enabled" key —
the opencode wiring merges enabled servers at `pipa runtime wire` time.
"""
from __future__ import annotations

import json
import re
from typing import List, Optional, Tuple

from pipa import config

_NAME_RE = re.compile(r"[a-z0-9-]+")


def _server_path(name: str) -> Optional[Path]:
    if not name or not _NAME_RE.fullmatch(name):
        return None
    path = config.mcp_dir() / name / "config.json"
    return path if path.is_file() else None


def list_servers() -> List[dict]:
    """[{name, enabled, type, detail}] sorted with enabled first."""
    root = config.mcp_dir()
    out: List[dict] = []
    try:
        dirs = sorted(root.iterdir())
    except OSError:
        return []
    for d in dirs:
        cfg = d / "config.json"
        if not d.is_dir() or not cfg.is_file():
            continue
        try:
            data = json.loads(cfg.read_text())
        except (OSError, ValueError):
            data = {}
        mcp_block = data.get("mcp") or {}
        out.append({
            "name": str(data.get("name") or d.name),
            "enabled": bool(data.get("enabled")),
            "type": str(mcp_block.get("type") or "—"),
            "detail": str(mcp_block.get("url")
                          or mcp_block.get("command")
                          or "—"),
        })
    out.sort(key=lambda s: (not s["enabled"], s["name"]))
    return out


def set_enabled(name: str, enabled: bool) -> Tuple[bool, str]:
    path = _server_path(name)
    if path is None:
        return False, f"unknown MCP server: {name}"
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        return False, f"cannot read registry entry: {exc}"
    if not isinstance(data, dict):
        return False, "registry entry is not a JSON object"
    data["enabled"] = bool(enabled)
    try:
        path.write_text(json.dumps(data, indent=2) + "\n")
    except OSError as exc:
        return False, f"write failed: {exc}"
    state = "enabled" if enabled else "disabled"
    return True, f"{name} {state} — re-run `pipa up` to apply"
