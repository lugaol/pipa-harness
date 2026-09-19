"""JSON API: status, services, env keys, dashboard bootstrap.

Split out of api.py (Phase A.3). Routes byte-identical — no behavior change.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from pipa import config
from pipa.model_registry import TIER_ALIASES, normalize_tier

from data import envkeys as envkeys_data
from data import models as models_data
from data import system as system_data
from pages.api_common import _catalog, _verify_effective

router = APIRouter()


# ── status ────────────────────────────────────────────────────────────────

@router.get("/api/status")
def api_status():
    """{name: {up, detail}} — same shape as ia's harness_status()."""
    out = {}
    try:
        for c in system_data.checks():
            out[c["name"]] = {"up": bool(c["ok"]), "detail": c["detail"]}
    except Exception as exc:
        raise HTTPException(500, str(exc)[:200])
    return JSONResponse(out)


@router.post("/api/ollama/start")
def api_ollama_start():
    from data import services as services_data

    ok, detail = services_data.ollama_start()
    return JSONResponse({"ok": ok, "detail": detail})


@router.post("/api/gateway/rebuild")
def api_gateway_rebuild():
    """Recompose .effective.yaml from discovery + tiers, restart gateway."""
    from pipa import config
    from data import services as services_data

    try:
        config.compose_litellm_config()
        _verify_effective()
    except Exception as exc:
        raise HTTPException(500, f"compose failed, gateway untouched: {exc}")
    ok, detail = services_data.gateway_restart()
    return JSONResponse({"ok": ok,
                         "detail": detail or ("gateway restarted" if ok else "restart failed")})


# ── env keys ──────────────────────────────────────────────────────────────

@router.get("/api/env-keys")
def api_get_env_keys():
    return JSONResponse(envkeys_data.list_env_keys())


@router.post("/api/env-keys")
async def api_set_env_key(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "JSON body required")
    key = str(payload.get("key") or "")
    value = str(payload.get("value") or "").strip()
    if key not in envkeys_data.managed_keys():
        raise HTTPException(400, f"unknown key {key!r}")
    if not value or any(c in value for c in " \t\r\n"):
        raise HTTPException(400, "value must be non-empty with no whitespace")
    if envkeys_data.is_placeholder(value):
        raise HTTPException(400, "that looks like a placeholder - paste the real value")
    try:
        result = envkeys_data.set_key_and_apply(key, value)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, str(exc)[:200])
    return JSONResponse(result)


# ── dashboard bootstrap (tiers + agents + catalog) ────────────────────────

def _dashboard_payload() -> dict:
    from pipa.model_registry import tier_policy, tier_resolution
    from pipa.recommendations import recommended_model, recommended_tier
    from pipa.runtime import AGENT_MODEL_MAP
    from data import agents as agents_data

    try:
        policy = tier_policy()
    except Exception:
        policy = {}
    try:
        models_data.ensure_seeded()
    except Exception:
        pass
    try:
        assigned = models_data.assignments()
    except Exception:
        assigned = {}
    tiers = {
        "tiers": policy,
        "tier_order": list(TIER_ALIASES),
        "resolved": dict(assigned),
    }
    try:
        discovered = agents_data.discover_agents()
    except Exception:
        discovered = []
    resolved = {}
    try:
        resolved = tier_resolution()
    except Exception:
        pass
    agents = []
    for a in discovered:
        name = a.get("name") or ""
        default = normalize_tier(AGENT_MODEL_MAP.get(name, ""))
        ov = agents_data.override_for(name) or ""
        tier = normalize_tier(ov) or default
        entry = resolved.get(tier)
        agents.append({
            "name": name,
            "description": a.get("description") or "",
            "source": a.get("source") or "",
            "tier": tier,
            "override": normalize_tier(ov),
            "default_tier": default,
            "model": entry.display if entry else "",
            "model_active": bool(entry.active) if entry else False,
            "steps": (policy.get(tier) or {}).get("max_steps") if tier else None,
            "drift": bool(ov) and normalize_tier(ov) != default,
            "recommended": recommended_tier(name) or default,
            "recommended_model": recommended_model(name),
        })
    # Orchestrator (primary agent) has no agents/*.md file but is a
    # first-class tier assignment: override > map default, resolved model
    # follows like any other agent.
    try:
        from pipa.agent_tiers import override_for as _ov_for
        from pipa.runtime import primary_tier as _primary_tier

        ov = _ov_for("orchestrator") or ""
        tier = _primary_tier()
        entry = resolved.get(tier)
        agents.append({
            "name": "orchestrator",
            "description": "Primary agent (opencode model)",
            "source": "primary",
            "tier": tier,
            "override": normalize_tier(ov),
            "default_tier": recommended_tier("orchestrator"),
            "model": entry.display if entry else "",
            "model_active": bool(entry.active) if entry else False,
            "steps": (policy.get(tier) or {}).get("max_steps") if tier else None,
            "drift": bool(ov) and normalize_tier(ov) != recommended_tier("orchestrator"),
            "recommended": recommended_tier("orchestrator"),
            "recommended_model": recommended_model("orchestrator"),
        })
    except Exception:
        pass
    return {"tiers": tiers, "agents": agents, "catalog": _catalog()}


@router.get("/api/dashboard")
def api_dashboard():
    return JSONResponse(_dashboard_payload())
