"""Agents — ia-style tier assignment screen (JS + JSON API)."""
from __future__ import annotations

from fastapi import APIRouter, Request

from . import form_fields, render

from data import agents as agents_data

router = APIRouter()


@router.get("/agents")
def agents_view(request: Request):
    return render(request, "agents.html")


@router.post("/api/agent-tier")
async def save_agent_tier(request: Request):
    """Legacy form endpoint (Models page batch flow) — kept for compat."""
    from fastapi.responses import RedirectResponse

    fields = await form_fields(request)
    agents_data.set_tier_override(
        str(fields.get("agent", "")), str(fields.get("tier", ""))
    )
    nxt = str(fields.get("next") or "/models")
    if not nxt.startswith("/") or nxt.startswith("//"):
        nxt = "/models"
    return RedirectResponse(url=f"{nxt}?saved=1", status_code=303)
