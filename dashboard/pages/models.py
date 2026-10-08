"""Models — discovered-model catalog (list only).

Tier assignment lives on /tiers (Tier Manager), agent assignment on
/agents. The form POSTs below stay for backwards compat.
"""
from __future__ import annotations

import urllib.parse

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from data import agents as agents_data
from data import models as models_data
from . import form_fields, render

router = APIRouter()


@router.get("/models")
def models_view(request: Request):
    # Auto-seed when no tiers assigned and models are available
    seeded = False
    try:
        seeded = bool(models_data.ensure_seeded())
    except Exception:
        pass

    try:
        catalog = models_data.catalog()
        discovery = models_data.refresh_status()
    except Exception:
        catalog, discovery = [], {"fetched_at": None, "providers": []}
    try:
        assigned = models_data.assignments()
    except Exception:
        assigned = {}
    try:
        verification = models_data.verification()
    except Exception:
        verification = {"checked_at": None, "results": {}}
    tier_of: dict = {}
    for tier, alias in assigned.items():
        tier_of.setdefault(alias, []).append(tier)

    # A model can hold its API key and still be unusable (401 on the plan,
    # 429 on an overloaded engine, or a provider that refuses proxy delivery).
    # `active` only means "key present", so annotate rows with the last live
    # probe result. A tier assigned to a known-bad model is called out.
    results = verification.get("results") or {}
    for row in catalog:
        rec = results.get(row["alias"])
        row["verified"] = None if rec is None else bool(rec.get("ok"))
        row["verify_detail"] = "" if rec is None else str(rec.get("detail") or "")
    assigned_broken = sorted(
        {t: alias for t, alias in assigned.items() if results.get(alias, {}).get("ok") is False}
        .items()
    )

    return render(
        request,
        "models.html",
        catalog=catalog,
        discovery=discovery,
        tier_of=tier_of,
        seeded=seeded or request.query_params.get("seeded") == "1",
        verified_at=verification.get("checked_at"),
        assigned_broken=assigned_broken,
    )


@router.post("/api/tiers")
async def save_tier(request: Request):
    fields = await form_fields(request)
    ok, _msg = models_data.set_tier(
        str(fields.get("tier", "")), str(fields.get("model", ""))
    )
    return RedirectResponse(url="/models" + ("?saved=1" if ok else "?error=1"),
                            status_code=303)


@router.post("/api/tiers/batch")
async def save_tiers_batch(request: Request):
    body = (await request.body()).decode("utf-8", "replace")
    pairs = urllib.parse.parse_qs(body, keep_blank_values=True)

    # Collect tier -> model assignments
    assignments: dict[str, str] = {}
    for key, values in pairs.items():
        if key.startswith("tier_"):
            tier = key[5:]  # tier_lowest -> lowest
            assignments[tier] = values[0] if values else ""

    # Also handle agent overrides in the same batch
    agent_overrides: dict[str, str] = {}
    for key, values in pairs.items():
        if key.startswith("agent_"):
            agent = key[6:]
            agent_overrides[agent] = values[0] if values else ""

    # Save tier assignments through the single batch owner
    from pipa.model_registry import apply_tiers

    ok, _msg, _warnings = apply_tiers(assignments)

    # Save agent overrides
    for agent, tier in agent_overrides.items():
        agents_data.set_tier_override(agent, tier)

    # Push overrides + tier-resolution changes into the deployed agent files —
    # a save that only updates state is the bug where agents ignore it.
    try:
        from pipa.runtime import refresh_agents

        refresh_agents()
    except Exception:  # noqa: BLE001 — saved but not deployed; say so via flash
        return RedirectResponse(url="/models?error=1", status_code=303)

    # Restart gateway so new aliases take effect
    if ok:
        try:
            from data import services as services_data

            services_data.gateway_restart()
        except Exception:
            pass

    return RedirectResponse(
        url="/models" + ("?saved=1" if ok else "?error=1"),
        status_code=303,
    )


@router.post("/api/models/refresh")
async def refresh_models(request: Request):
    try:
        models_data.refresh_models()
        status = models_data.refresh_status()
        ok = bool(status["fetched_at"]) and any(p["ok"] for p in status["providers"])
    except Exception:
        ok = False
    return RedirectResponse(url="/models" + ("?refreshed=1" if ok else "?refresh-error=1"),
                            status_code=303)
