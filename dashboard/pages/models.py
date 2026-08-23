"""Models page: gateway aliases grouped local/cloud + agent override editor."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from data import agents as agents_data
from data import gateway
from . import form_fields, render

router = APIRouter()

_CLOUD_PREFIXES = ("or-", "kilo", "kimi")


def group_of(model_id: str) -> str:
    """Prefix heuristic: or-* openrouter, kilo*/kimi* cloud, else local."""
    mid = model_id.lower()
    return "cloud" if mid.startswith(_CLOUD_PREFIXES) else "local"


@router.get("/models")
def models_view(request: Request):
    try:
        model_ids = gateway.list_models()
    except Exception:
        model_ids = []
    groups = {
        "local": [m for m in model_ids if group_of(m) == "local"],
        "cloud": [m for m in model_ids if group_of(m) == "cloud"],
    }
    try:
        discovered = agents_data.discover_agents()
        overrides = agents_data.load_overrides()
    except Exception:
        discovered, overrides = [], {}

    def _override_for(name: str):
        row = overrides.get(name) or {}
        if isinstance(row, dict):
            return str(row.get("model") or "")
        return ""

    agent_rows = [
        {
            "name": a["name"],
            "base_model": a["model"],
            "override": _override_for(a["name"]),
        }
        for a in discovered
    ]
    return render(
        request,
        "models.html",
        groups=groups,
        total=len(model_ids),
        agent_rows=agent_rows,
    )


@router.post("/api/overrides")
async def save_override(request: Request):
    fields = await form_fields(request)
    agents_data.set_override(
        str(fields.get("agent", "")), str(fields.get("model", ""))
    )
    return RedirectResponse(url="/models", status_code=303)
