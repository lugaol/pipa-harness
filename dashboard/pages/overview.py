"""Overview page: stat cards + service checks."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Request

from data import gateway, sessions as session_data, spend as spend_data, system
from . import render

router = APIRouter()


@router.get("/")
def overview(request: Request):
    try:
        models = gateway.list_models()
        models_error = False
    except Exception:
        models, models_error = [], True

    sessions_all = session_data.all_sessions()
    today = date.today().isoformat()
    sessions_today = sum(
        1 for s in sessions_all if str(s.get("start") or "").startswith(today)
    )

    spend_summary = spend_data.summary()

    try:
        checks = system.checks()
        updown = system.up_down(checks)
        project = system.project_info()
    except Exception:
        checks, updown, project = [], {"up": 0, "total": 0}, None

    cards = [
        {
            "label": "Gateway models",
            "value": len(models) if not models_error else "—",
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
        eval_error=False,
    )
