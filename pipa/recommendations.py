"""Recommended tiers per agent — drift hints and reset targets.

Single source of truth: derived from `pipa.runtime.AGENT_MODEL_MAP`
(the agent defaults). Never a mirrored static map — ia's recommendations.py
carries a MUST-mirror warning precisely because a copy drifts; deriving
makes that bug class impossible.

Used only to compute "drift" hints and reset targets in the UI: never
overwritten automatically.
"""
from __future__ import annotations


def recommended_tier(agent: str) -> str:
    """Default tier for an agent ("" when the agent has no default)."""
    from pipa.model_registry import normalize_tier
    from pipa.runtime import AGENT_MODEL_MAP

    return normalize_tier(AGENT_MODEL_MAP.get(agent, ""))


def recommended_tiers() -> dict:
    """{agent: tier} for every agent with a default."""
    from pipa.runtime import AGENT_MODEL_MAP

    return {a: recommended_tier(a) for a in AGENT_MODEL_MAP if recommended_tier(a)}


def recommended_model(agent: str) -> str:
    """Resolved display model for the agent's recommended tier.

    "" when the tier is unassigned or the catalog lacks the model — the
    caller should fall back to showing the tier name.
    """
    from pipa.model_registry import tier_resolution

    tier = recommended_tier(agent)
    if not tier:
        return ""
    try:
        entry = tier_resolution().get(tier)
    except Exception:
        return ""
    return entry.display if entry else ""
