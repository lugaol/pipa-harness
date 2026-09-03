"""Models page: user-owned tier configuration + plain model list, one page."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from pipa.model_registry import TIER_ALIASES

from data import models as models_data
from . import form_fields, render

router = APIRouter()


@router.get("/models")
def models_view(request: Request):
    try:
        tiers = models_data.tier_rows()
    except Exception:
        tiers = [{"alias": t, "label": t.capitalize(), "assigned_alias": "",
                  "display": "", "status": "unset"} for t in TIER_ALIASES]
    try:
        catalog = models_data.catalog()
        env_keys = models_data.env_keys()
        discovery = models_data.refresh_status()
    except Exception:
        catalog, env_keys, discovery = [], [], {"fetched_at": None, "providers": []}
    return render(
        request,
        "models.html",
        tiers=tiers,
        catalog=catalog,
        env_keys=env_keys,
        discovery=discovery,
    )


@router.post("/api/tiers")
async def save_tier(request: Request):
    fields = await form_fields(request)
    ok, _msg = models_data.set_tier(
        str(fields.get("tier", "")), str(fields.get("model", ""))
    )
    return RedirectResponse(url="/models" + ("?saved=1" if ok else "?error=1"),
                            status_code=303)


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
