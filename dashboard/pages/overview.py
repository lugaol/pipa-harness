"""Overview page: stat cards, service checks + control actions, env keys."""
from __future__ import annotations

from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from data import gateway, models as models_data, services as services_data
from data import sessions as session_data, spend as spend_data, system
from . import render

router = APIRouter()


@router.get("/api/health")
def health():
    """Lightweight probe for the sidebar status pill."""
    try:
        cks = {c["name"].lower(): bool(c["ok"]) for c in system.checks()}
    except Exception:
        cks = {}
    return {
        "gateway": cks.get("litellm gateway", False),
        "ollama": cks.get("ollama", False),
    }


@router.get("/")
def overview(request: Request, flash: str = "", ok: str = ""):
    # data-layer readers are fail-soft; no extra guards needed here
    models = gateway.list_models()

    sessions_all = session_data.all_sessions()
    today = date.today().isoformat()
    sessions_today = sum(
        1 for s in sessions_all if str(s.get("start") or "").startswith(today)
    )

    spend_summary = spend_data.summary()

    checks = system.checks()
    updown = system.up_down(checks)
    project = system.project_info()

    env_keys = models_data.env_keys()

    def _check_ok(name: str) -> bool:
        row = next((c for c in checks if c["name"] == name), None)
        return bool(row and row["ok"])

    cards = [
        {
            "label": "Gateway models",
            "value": len(models),
            "detail": f"{len(models)} aliases served" if models else "gateway down or empty",
        },
        {
            "label": "Sessions today",
            "value": sessions_today,
            "detail": f"{len(sessions_all)} total recorded",
        },
        {
            "label": "Spend (all time)",
            "value": f"${spend_summary['cost_usd']:.4f}",
            "detail": f"{spend_summary['rows']} calls",
        },
        {
            "label": "Services",
            "value": f"{updown['up']}/{updown['total']}",
            "detail": "up / checked",
        },
    ]

    return render(
        request,
        "overview.html",
        cards=cards,
        checks=checks,
        project=project,
        env_keys=env_keys,
        gateway_up=_check_ok("litellm gateway"),
        ollama_up=_check_ok("ollama"),
        flash=flash,
        flash_ok=ok != "0",
    )


@router.post("/api/services/gateway/restart")
def restart_gateway(request: Request):
    ok, msg = services_data.gateway_restart()
    return RedirectResponse(
        f"/?flash={quote(msg[:300])}&ok={'1' if ok else '0'}", status_code=303
    )


@router.post("/api/services/ollama/start")
def start_ollama(request: Request):
    ok, msg = services_data.ollama_start()
    return RedirectResponse(
        f"/?flash={quote(msg[:300])}&ok={'1' if ok else '0'}", status_code=303
    )
