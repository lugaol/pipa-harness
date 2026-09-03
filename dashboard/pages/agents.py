"""Agents page: one card per discovered agent + per-agent tier assignment."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from pipa.model_registry import TIER_ALIASES, normalize_tier, tier_resolution
from pipa.runtime import AGENT_MODEL_MAP

from data import agents as agents_data
from . import form_fields, render

router = APIRouter()


def _tier_of(name: str, frontmatter_model: str) -> tuple[str, str]:
    """-> (tier, source). Priority: dashboard override > frontmatter >
    runtime default. Never guesses from providers — only tier names count."""
    ov = agents_data.override_for(name)
    tier = normalize_tier(ov or "")
    if tier:
        return tier, "your pick"
    fm = (frontmatter_model or "").strip()
    if "litellm/" in fm:
        fm = fm.split("/")[-1].strip()
    tier = normalize_tier(fm)
    if tier:
        return tier, "frontmatter"
    tier = normalize_tier(AGENT_MODEL_MAP.get(name, ""))
    return (tier, "default") if tier else ("", "unset")


@router.get("/agents")
def agents_view(request: Request):
    try:
        discovered = agents_data.discover_agents()
    except Exception:
        discovered = []
    resolved = tier_resolution()
    rows = []
    for a in discovered:
        ov = agents_data.override_for(a["name"]) or ""
        tier, source = _tier_of(a["name"], a.get("model") or "")
        e = resolved.get(tier)
        if tier and e is not None:
            display = f"{tier} · {e.display}"
            if not e.active:
                display += " (needs API key)"
        else:
            display = f"{tier} · tier not set" if tier else "— unset —"
        rows.append({
            **a,
            "tier": tier,
            "override_tier": normalize_tier(ov),
            "effective_display": display,
            "source": source,
        })
    return render(request, "agents.html", agents=rows)


@router.post("/api/agent-tier")
async def save_agent_tier(request: Request):
    fields = await form_fields(request)
    agents_data.set_tier_override(
        str(fields.get("agent", "")), str(fields.get("tier", ""))
    )
    nxt = str(fields.get("next") or "/agents")
    if not nxt.startswith("/") or nxt.startswith("//"):
        nxt = "/agents"
    return RedirectResponse(url=f"{nxt}?saved=1", status_code=303)
