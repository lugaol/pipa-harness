"""Team — who uses the harness: adoption, durations, alerts.

Server-rendered (Observability pattern). Composes pipa.metrics (same
rollup as `pipa usage-report`), session durations, and the L1 triage
alerts strip — no new readers.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from pipa import config
from . import render

router = APIRouter()


def _durations(summaries: list) -> list:
    """[(id, seconds, events, runtime)] for sessions with parseable bounds."""
    from datetime import datetime

    def parse(raw):
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
        return dt

    out = []
    for s in summaries or []:
        t0, t1 = parse(s.get("start")), parse(s.get("end"))
        if t0 is None or t1 is None:
            continue
        secs = max((t1 - t0).total_seconds(), 0.0)
        out.append({"id": s.get("id") or "?", "seconds": secs,
                    "events": s.get("events", 0),
                    "runtime": s.get("runtime") or "?"})
    return out


def _fmt_secs(secs: float) -> str:
    if secs < 60:
        return f"{secs:.0f}s"
    if secs < 3600:
        return f"{secs / 60:.1f}m"
    return f"{secs / 3600:.1f}h"


@router.get("/team")
def team_view(request: Request):
    from pipa import metrics as metrics_lib
    from pipa import session as session_mod
    from pipa import spend as spend_mod
    from pipa import triage as triage_lib
    from pipa import __version__

    project = config.find_project()
    log = config.session_log_path(project) if project else None
    try:
        summaries = session_mod.sessions(log) if log and log.exists() else []
    except Exception:
        summaries = []
    try:
        spend = spend_mod.summarize()
    except Exception:
        spend = {"rows": 0, "cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0}
    try:
        usage = metrics_lib.build_report(summaries, spend)
    except Exception:
        usage = {"sessions": 0, "per_day": [], "top_tools": [],
                 "top_models": [], "runtimes": [], "spend": spend}
    durations = sorted(_durations(summaries), key=lambda d: -d["seconds"])
    secs = sorted(d["seconds"] for d in durations)
    if secs:
        avg = sum(secs) / len(secs)
        median = secs[len(secs) // 2]
    else:
        avg = median = 0.0
    try:
        signals = triage_lib.collect_signals(project)
        alerts = triage_lib.needs_human(signals)
    except Exception:
        alerts = []
    longest = [{
        "id": d["id"], "duration": _fmt_secs(d["seconds"]),
        "events": d["events"], "runtime": d["runtime"],
    } for d in durations[:5]]
    return render(
        request, "team.html",
        version=__version__,
        usage=usage,
        cards=[
            {"label": "Sessions", "value": usage["sessions"], "detail": "recorded"},
            {"label": "Active days", "value": len(usage.get("per_day") or []),
             "detail": "with sessions"},
            {"label": "Cost", "value": f"${usage['spend'].get('cost_usd', 0.0):.4f}",
             "detail": f"{usage['spend'].get('rows', 0)} calls"},
            {"label": "Avg session", "value": _fmt_secs(avg),
             "detail": f"median {_fmt_secs(median)}"},
        ],
        alerts=alerts,
        longest=longest,
    )
