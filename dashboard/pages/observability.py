"""Observability — sessions (flight recorder) + spend (ledger), tab strip."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request

from data import sessions as session_data
from data import spend as spend_data
from . import render

router = APIRouter()


def _usage_report(summaries, spend_summary):
    """Shared rollup via pipa.metrics (same code as the CLI)."""
    from pipa import metrics as metrics_lib

    try:
        return metrics_lib.build_report(summaries, spend_summary)
    except Exception:
        return {"sessions": len(summaries or []), "per_day": [],
                "top_tools": [], "top_models": [], "runtimes": [],
                "spend": {"rows": 0, "cost_usd": 0.0,
                          "tokens_in": 0, "tokens_out": 0}}

_DETAIL_KEYS = ("tool", "model", "payload", "text")
_META_KEYS = ("tokens_in", "tokens_out", "cost_usd")


def _parse_ts(value):
    try:
        return datetime.fromisoformat(str(value)).timestamp()
    except ValueError:
        return 0.0


def _clip(value, n=70):
    value = str(value).replace("\n", " ")
    return value[:n] + "\u2026" if len(value) > n else value


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


def _fmt_counts(counts: dict, limit: int = 3) -> str:
    ranked = sorted((counts or {}).items(), key=lambda kv: (-kv[1], kv[0]))
    return ", ".join(f"{k}\u00d7{v}" for k, v in ranked[:limit])


def _summary_row(s: dict) -> dict:
    sid = str(s.get("id") or "")
    return {
        "id": sid,
        "href": f"/observability/session/{sid}",
        "runtime": s.get("runtime") or "?",
        "start": str(s.get("start") or "")[:19],
        "end": str(s.get("end") or "")[:19],
        "events": s.get("events", 0),
        "tools": _fmt_counts(s.get("tools")),
        "models": _fmt_counts(s.get("models")),
    }


@router.get("/observability")
def observability_view(request: Request, tab: str = "sessions", since: str = ""):
    tab = tab if tab in ("sessions", "spend", "usage") else "sessions"

    # Sessions data
    try:
        summaries = session_data.all_sessions()
    except Exception:
        summaries = []
    session_rows = [_summary_row(s) for s in reversed(summaries)]
    session_columns = ["id", "runtime", "start", "end", "events", "tools", "models"]

    # Spend data
    since = (since or "").strip() or None
    summary = spend_data.summary(since)
    spend_columns = ["ts", "alias", "model", "tokens in", "tokens out", "cost"]
    spend_rows = [
        [
            str(r.get("ts") or "")[:19],
            str(r.get("alias") or "?"),
            str(r.get("model") or "?")[:40],
            int(r.get("tokens_in") or 0),
            int(r.get("tokens_out") or 0),
            f"${float(r.get('cost_usd') or 0):.4f}",
        ]
        for r in spend_data.recent_rows(since, limit=50)
    ]
    by_model_rows = [
        [name[:44], stats["calls"], f"{stats['tokens_in']:,}",
         f"{stats['tokens_out']:,}", f"${stats['cost_usd']:.4f}"]
        for name, stats in sorted(
            summary["by_model"].items(), key=lambda kv: -kv[1]["cost_usd"])
    ]
    spend_cards = [
        {"label": "Calls", "value": summary["rows"], "detail": "in window"},
        {"label": "Cost", "value": f"${summary['cost_usd']:.4f}", "detail": "total USD"},
        {"label": "Tokens in", "value": f"{summary['tokens_in']:,}", "detail": "prompt tokens"},
        {"label": "Tokens out", "value": f"{summary['tokens_out']:,}", "detail": "completion tokens"},
    ]

    return render(
        request, "observability.html",
        tab=tab,
        # sessions
        session_columns=session_columns, session_rows=session_rows,
        session_count=len(session_rows),
        # spend
        spend_columns=spend_columns, spend_rows=spend_rows,
        by_model_columns=["model", "calls", "tokens in", "tokens out", "cost"],
        by_model_rows=by_model_rows,
        spend_cards=spend_cards,
        since=since or "",
        window=(f"{summary['first_ts']} \u2192 {summary['last_ts']}"
                if summary.get("first_ts") else ""),
        # usage (shared rollup with `pipa usage-report`)
        usage=_usage_report(summaries, summary),
    )


@router.get("/observability/session/{sid}")
def observability_session_detail(request: Request, sid: str):
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
