"""Redirect: /sessions -> /observability?tab=sessions (backwards compat)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from data import sessions as session_data
from . import render
from datetime import datetime

router = APIRouter()

_DETAIL_KEYS = ("tool", "model", "payload", "text")
_META_KEYS = ("tokens_in", "tokens_out", "cost_usd")


def _parse_ts(value):
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except ValueError:
        return 0.0


def _clip(value, n=70):
    value = str(value).replace("\n", " ")
    return value[:n] + "…" if len(value) > n else value


def _replay_rows(events):
    t0 = _parse_ts(events[0].get("ts")) if events else 0.0
    rows = []
    for e in events:
        off = max(_parse_ts(e.get("ts")) - t0, 0.0)
        detail_parts = [str(e[k]) for k in _DETAIL_KEYS if e.get(k)]
        meta = ", ".join(f"{k}={e[k]}" for k in _META_KEYS if e.get(k) is not None)
        if meta:
            detail_parts.append(meta)
        rows.append({
            "offset": f"+{off:.1f}s",
            "event": e.get("event") or "?",
            "detail": "  ".join(_clip(p) for p in detail_parts),
        })
    return rows


@router.get("/sessions")
def sessions_list(request: Request):
    return RedirectResponse(url="/observability?tab=sessions", status_code=307)


@router.get("/sessions/{sid}")
def session_detail(request: Request, sid: str):
    events = session_data.events_for(sid)
    known = session_data.all_sessions()
    summary = next((s for s in known if s["id"] == sid), None)
    tools = ",".join(sorted(summary["tools"])) if summary else "-"
    models = ",".join(sorted(summary["models"])) if summary else "-"
    duration = 0.0
    if summary and summary.get("end"):
        duration = max(
            _parse_ts(summary["end"]) - _parse_ts(summary.get("start")), 0.0)
    return render(
        request, "session_detail.html",
        sid=sid, found=bool(events),
        header={
            "runtime": summary.get("runtime") or "?" if summary else "?",
            "events": len(events), "duration": f"{duration:.0f}s",
            "tools": tools, "models": models,
        },
        rows=_replay_rows(events),
    )
