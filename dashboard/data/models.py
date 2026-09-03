"""Model catalog (discovered) + user-owned tier assignments.

The catalog comes from live provider discovery cached in
state/model_catalog.json — nothing here is static. Tier -> model mapping
is a user decision made in the dashboard; it persists in
state/tier_assignments.json. Key NAMES are surfaced, never values.
"""
from __future__ import annotations

from typing import Dict, List

from pipa.model_registry import (
    TIER_ALIASES,
    normalize_tier,
    provider_label,
    set_tier_assignment,
    tier_assignments,
)


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


def tier_rows() -> List[dict]:
    """The five fixed tiers with their current user-chosen model, if any.

    [{alias, label, assigned_alias, display, status}]
      status: 'unset' | 'ready' | 'needs-key'
    """
    cat = {c["alias"]: c for c in catalog()}
    assigned = assignments()
    rows = []
    for tier in TIER_ALIASES:
        alias = assigned.get(tier, "")
        info = cat.get(alias)
        if not alias or info is None:
            status, display = "unset", ""
        else:
            missing = missing_keys_for(alias)
            display = info["display"]
            status = "needs-key" if missing else "ready"
        rows.append({
            "alias": tier,
            "label": tier.capitalize(),
            "assigned_alias": alias,
            "display": display,
            "status": status,
        })
    return rows
