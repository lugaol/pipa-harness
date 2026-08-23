"""Sessions pages: summary table + single-session replay timeline."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request

from data import sessions as session_data
from . import render

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
    """Port of pipa.cli._replay_lines, rendered as template rows."""
    t0 = _parse_ts(events[0].get("ts")) if events else 0.0
    rows = []
    for e in events:
        off = max(_parse_ts(e.get("ts")) - t0, 0.0)
        detail_parts = [str(e[k]) for k in _DETAIL_KEYS if e.get(k)]
        meta = ", ".join(
            f"{k}={e[k]}" for k in _META_KEYS if e.get(k) is not None
        )
        if meta:
            detail_parts.append(meta)
        rows.append({
            "offset": f"+{off:.1f}s",
            "event": e.get("event") or "?",
            "detail": "  ".join(_clip(p) for p in detail_parts),
        })
    return rows


def _fmt_counts(counts: dict, limit: int = 3) -> str:
    ranked = sorted((counts or {}).items(), key=lambda kv: (-kv[1], kv[0]))
    return ", ".join(f"{k}×{v}" for k, v in ranked[:limit])


def _summary_row(s: dict) -> dict:
    sid = str(s.get("id") or "")
    return {
        "id": sid,
        "href": f"/sessions/{sid}",
        "runtime": s.get("runtime") or "?",
        "start": str(s.get("start") or "")[:19],
        "end": str(s.get("end") or "")[:19],
        "events": s.get("events", 0),
        "tools": _fmt_counts(s.get("tools")),
        "models": _fmt_counts(s.get("models")),
    }


@router.get("/sessions")
def sessions_list(request: Request):
    try:
        summaries = session_data.all_sessions()
    except Exception:
        summaries = []
    newest_first = [_summary_row(s) for s in reversed(summaries)]
    columns = ["id", "runtime", "start", "end", "events", "tools", "models"]
    return render(
        request,
        "sessions.html",
        columns=columns,
        rows=newest_first,
        count=len(newest_first),
    )


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
            _parse_ts(summary["end"]) - _parse_ts(summary.get("start")), 0.0
        )
    return render(
        request,
        "session_detail.html",
        sid=sid,
        found=bool(events),
        header={
            "runtime": summary.get("runtime") or "?" if summary else "?",
            "events": len(events),
            "duration": f"{duration:.0f}s",
            "tools": tools,
            "models": models,
        },
        rows=_replay_rows(events),
    )
