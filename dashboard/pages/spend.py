"""Spend page: totals cards, by-model table, recent rows; ?since= filter."""
from __future__ import annotations

from fastapi import APIRouter, Request

from data import spend as spend_data
from . import render

router = APIRouter()


@router.get("/spend")
def spend_view(request: Request, since: str = ""):
    since = (since or "").strip() or None
    summary = spend_data.summary(since)
    columns = ["ts", "alias", "model", "tokens in", "tokens out", "cost"]
    rows = [
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
        [
            name[:44],
            stats["calls"],
            f"{stats['tokens_in']:,}",
            f"{stats['tokens_out']:,}",
            f"${stats['cost_usd']:.4f}",
        ]
        for name, stats in sorted(
            summary["by_model"].items(),
            key=lambda kv: -kv[1]["cost_usd"],
        )
    ]
    cards = [
        {"label": "Calls", "value": summary["rows"], "detail": "in window"},
        {"label": "Cost", "value": f"${summary['cost_usd']:.4f}", "detail": "total USD"},
        {"label": "Tokens in", "value": f"{summary['tokens_in']:,}", "detail": "prompt tokens"},
        {"label": "Tokens out", "value": f"{summary['tokens_out']:,}", "detail": "completion tokens"},
    ]
    return render(
        request,
        "spend.html",
        cards=cards,
        by_model_columns=["model", "calls", "tokens in", "tokens out", "cost"],
        by_model_rows=by_model_rows,
        columns=columns,
        rows=rows,
        since=since or "",
        window=(f"{summary['first_ts']} → {summary['last_ts']}"
                if summary.get("first_ts") else ""),
    )
