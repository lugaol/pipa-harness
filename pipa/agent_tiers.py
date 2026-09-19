"""Per-agent tier override store (user decisions).

Single owner for state/agent_llm_overrides.json: {agent: {"tier": ...}}.
Pre-2026-08 rows carry {"model": ...} and still read (normalized on load).
Dashboard discovery lives in dashboard/data/agents.py; it delegates here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from pipa import config

OVERRIDES_FILE = "agent_llm_overrides.json"


def overrides_path() -> Path:
    return config.state_dir() / OVERRIDES_FILE


def load_overrides() -> Dict[str, dict]:
    """{agent: {"tier"|"model": str}}; {} when absent/corrupt."""
    try:
        data = json.loads(overrides_path().read_text())
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def save_overrides(data: dict) -> None:
    path = overrides_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def set_tier_override(agent: str, tier: str) -> None:
    """Set (non-empty tier) or clear (empty tier) one agent's tier override."""
    if not agent:
        return
    overrides = load_overrides()
    if tier.strip():
        overrides[agent] = {"tier": tier.strip()}
    else:
        overrides.pop(agent, None)
    save_overrides(overrides)


def reset_override(agent: str) -> None:
    """Drop one agent's override from the store (no-op when unset)."""
    set_tier_override(agent, "")


def override_for(agent_name: str) -> Optional[str]:
    row = load_overrides().get(agent_name) or load_overrides().get(f"agents/{agent_name}.md")
    if isinstance(row, dict):
        # New stores carry {"tier": ...}; pre-2026-08 stores {"model": ...}.
        value = row.get("tier") or row.get("model")
        return str(value) if value else None
    return None
