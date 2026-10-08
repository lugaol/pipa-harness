"""JSON API: tier -> model assignments and agent -> tier overrides.

Split out of api.py (Phase A.3). Routes byte-identical — no behavior change.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from pipa.model_registry import TIER_ALIASES, normalize_tier

from data import models as models_data
from pages.api_common import _known_aliases

router = APIRouter()


def _rerender_agents() -> None:
    """Push saved overrides into the deployed agent files.

    The override store is not the agent; the rendered frontmatter is. Without
    this, a save updates state/agent_llm_overrides.json and every deployed
    agent keeps the tier it was last rendered with — the dashboard toast says
    success while the agent ignores it. Failure is loud: the override was
    saved but did not take effect, which is the whole bug this prevents.
    """
    from pipa.runtime import refresh_agents

    try:
        refresh_agents()
    except Exception as exc:  # noqa: BLE001 — surface it, never swallow
        raise HTTPException(500, f"override saved, but agent re-render failed: {exc}")


@router.put("/api/tier-models")
async def api_set_tier_models(request: Request):
    """Batch tier -> model (+optional max_steps), like ia's Tier Manager."""
    from pipa.model_registry import apply_tiers

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "JSON body required")
    updates = payload.get("tiers")
    if not isinstance(updates, dict) or not updates:
        raise HTTPException(400, "tiers must be a non-empty mapping of tier -> {model, max_steps}")
    for tier, cfg in updates.items():
        steps = cfg.get("max_steps") if isinstance(cfg, dict) else None
        if steps is not None:
            try:
                _set_tier_steps(normalize_tier(tier), int(steps))
            except (TypeError, ValueError):
                raise HTTPException(400, f"tier {tier} max_steps must be an integer")
    models = {t: (c.get("model") or "") if isinstance(c, dict) else ""
              for t, c in updates.items()}
    ok, msg, warnings = apply_tiers(models)
    if not ok:
        raise HTTPException(400, msg)
    from data import services as services_data

    # gateway_restart verifies the composed config before it spawns anything
    # (pipa.services.start_litellm -> config.verify_effective), so there is no
    # window here where a bad compose reaches a running gateway.
    restarted, detail = services_data.gateway_restart()
    _rerender_agents()
    out = {"ok": True,
           "detail": detail or ("gateway restarted" if restarted else "saved (gateway restart failed)"),
           "restarted": restarted}
    if warnings:
        out["warnings"] = warnings
    return JSONResponse(out)


@router.put("/api/tiers/{name}")
async def api_set_tier(name: str, request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "JSON body required")
    tier = normalize_tier(name)
    if tier not in TIER_ALIASES:
        raise HTTPException(404, f"no tier {name!r}")
    model = str(payload.get("model") or "").strip()
    if model and model not in _known_aliases():
        raise HTTPException(400, f"unknown model {model!r} - not in the model catalog")
    if payload.get("max_steps") is not None:
        try:
            _set_tier_steps(tier, int(payload["max_steps"]))
        except (TypeError, ValueError):
            raise HTTPException(400, "max_steps must be an integer")
    if model:
        ok, msg = models_data.set_tier(tier, model)
        if not ok:
            raise HTTPException(400, msg)
    return JSONResponse({"ok": True, "tier": tier, "model": model})


def _set_tier_steps(tier: str, steps: int) -> None:
    if steps < 1:
        raise ValueError("max_steps must be >= 1")
    import yaml

    from pipa import config

    path = config.models_dir() / "tiers.yaml"
    raw = yaml.safe_load(path.read_text()) or {}
    raw.setdefault("tiers", {}).setdefault(tier, {})["max_steps"] = steps
    path.write_text(yaml.safe_dump(raw, sort_keys=False))


@router.put("/api/agent-tiers")
async def api_set_agent_tiers(request: Request):
    from data import agents as agents_data

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "JSON body required")
    mapping = payload.get("agent_tiers")
    if not isinstance(mapping, dict) or not mapping:
        raise HTTPException(400, "agent_tiers must be a non-empty mapping of agent -> tier")
    bad = sorted({a for a, t in mapping.items() if normalize_tier(t or "") not in TIER_ALIASES})
    if bad:
        raise HTTPException(400, f"unknown tier for: {', '.join(bad)}")
    for agent, tier in mapping.items():
        if not str(agent).strip():
            raise HTTPException(400, "agent name must not be empty")
        agents_data.set_tier_override(str(agent), normalize_tier(str(tier)))
    _rerender_agents()
    return JSONResponse({"ok": True, "agent_tiers": dict(mapping)})


@router.put("/api/agents/{agent_name}")
async def api_set_agent(agent_name: str, request: Request):
    from data import agents as agents_data

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "JSON body required")
    tier = normalize_tier(str(payload.get("tier") or ""))
    if tier:
        if tier not in TIER_ALIASES:
            raise HTTPException(400, f"unknown tier {tier!r}")
        agents_data.set_tier_override(agent_name, tier)
        _rerender_agents()
        return JSONResponse({"ok": True, "agent": agent_name, "tier": tier})
    if payload.get("model"):
        raise HTTPException(400, "pipa agents run on tiers, not direct models - assign a tier instead")
    raise HTTPException(400, "tier is required")


@router.post("/api/agents/{agent_name}/reset")
def api_reset_agent(agent_name: str):
    from pipa.runtime import agent_tier
    from data import agents as agents_data

    agents_data.reset_override(agent_name)
    _rerender_agents()
    default = normalize_tier(agent_tier(agent_name))
    return JSONResponse({"ok": True, "agent": agent_name, "tier": default})


# ── orchestrator (primary agent) ────────────────────────────────────────

@router.put("/api/orchestrator")
async def api_set_orchestrator(request: Request):
    """Pin the primary-agent tier (ia orchestrator route, tier-only).

    Reads back through pipa.runtime.primary_tier so the response reflects
    the effective tier, not just the stored override.
    """
    from pipa.agent_tiers import set_tier_override
    from pipa.runtime import primary_tier

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "JSON body required")
    tier = normalize_tier(str(payload.get("tier") or ""))
    if not tier:
        raise HTTPException(400, "tier is required")
    if tier not in TIER_ALIASES:
        raise HTTPException(400, f"unknown tier {tier!r}")
    set_tier_override("orchestrator", tier)
    return JSONResponse({"ok": True, "agent": "orchestrator", "tier": primary_tier()})


@router.post("/api/orchestrator/reset")
def api_reset_orchestrator():
    from pipa.agent_tiers import reset_override
    from pipa.recommendations import recommended_tier
    from pipa.runtime import primary_tier

    reset_override("orchestrator")
    return JSONResponse({"ok": True, "agent": "orchestrator",
                         "tier": primary_tier(),
                         "recommended": recommended_tier("orchestrator")})
