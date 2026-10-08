"""Model catalog (discovered) + user-owned tier assignments.

The catalog comes from live provider discovery cached in
state/model_catalog.json — nothing here is static. Tier -> model mapping
is a user decision made in the dashboard; it persists in
state/tier_assignments.json. Key NAMES are surfaced, never values.
"""
from __future__ import annotations

import json
from typing import Dict, List

from pipa.model_registry import (
    TIER_ALIASES,
    normalize_tier,
    provider_label,
    set_tier_assignment,
    tier_assignments,
)

def verification() -> dict:
    """{model: {ok, detail}} from the last live probe, plus its timestamp.

    Written by `pipa-check models` / `pipa-check tiers`. Absence means "never
    probed", which is not the same as broken — the UI must distinguish those.
    """
    from pipa import config

    path = config.state_dir() / "model_verification.json"
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {"checked_at": None, "results": {}}
    if not isinstance(data, dict):
        return {"checked_at": None, "results": {}}
    checked_at = data.pop("_checked_at", None)
    return {"checked_at": checked_at, "results": data}

def env_keys() -> List[dict]:
    """[{name, present}] derived from provider wiring; values never read."""
    import os

    from pipa.providers import PROVIDERS

    names = sorted({k for p in PROVIDERS.values() for k in p.requires})
    return [{"name": name, "present": bool(os.environ.get(name))} for name in names]

def catalog() -> List[dict]:
    """Flat discovered-model rows: [{alias, display, provider, kind, active}].

    Sorted by provider then display name so the page reads stably.
    """
    try:
        from pipa.model_registry import entries
    except ImportError:
        return []
    rows = [
        {
            "alias": e.alias,
            "display": e.display,
            "provider": provider_label(e.provider_slug),
            "kind": e.kind,
            "active": e.active,
        }
        for e in entries()
    ]
    return sorted(rows, key=lambda r: (r["provider"].lower(), r["display"]))

def assignments() -> Dict[str, str]:
    """{tier -> alias} as configured by the user."""
    return tier_assignments()

def set_tier(tier: str, alias: str) -> tuple[bool, str]:
    """Persist one user decision: tier -> model ('' clears)."""
    return set_tier_assignment(normalize_tier(tier) or tier, alias)

def ensure_seeded() -> bool:
    """Auto-seed tiers from discovered models when none are assigned."""
    if tier_assignments():
        return False
    try:
        from pipa.model_registry import seed_default_tiers

        result = seed_default_tiers()
        return bool(result)
    except Exception:
        return False

def missing_keys_for(alias: str) -> List[str]:
    from pipa.providers import missing_keys

    return missing_keys(alias)

def refresh_status() -> dict:
    """Discovery freshness for the Models page header."""
    from pipa.providers import PROVIDERS, cached_catalog, fetched_at

    cat = cached_catalog()
    providers = []
    for slug in PROVIDERS:
        entry = cat.get(slug) or {}
        providers.append({
            "label": PROVIDERS[slug].label,
            "ok": bool(entry.get("ok")),
            "count": len(entry.get("models") or []),
            "error": entry.get("error") or "",
        })
    return {"fetched_at": fetched_at(), "providers": providers}

def refresh_models(timeout: int = 8) -> dict:
    """Live re-discovery from every provider (dashboard Refresh button)."""
    from pipa.providers import refresh

    summary = refresh(timeout=timeout)
    try:
        from pipa import config

        config.compose_litellm_config()
    except Exception:
        pass
    return summary

