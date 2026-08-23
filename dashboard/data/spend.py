"""Spend-ledger reader bound to the harness state dir.

Delegates aggregation to pipa.spend.summarize; a missing ledger yields
the zeroed summary shape so pages never see exceptions.
"""
from __future__ import annotations

from typing import Optional

from pipa import config
from pipa import spend as spend_ledger


def ledger_path() -> Optional[str]:
    path = config.state_dir() / "spend.ndjson"
    return str(path) if path.exists() else None


def _empty_summary() -> dict:
    return {
        "rows": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
        "by_model": {},
        "by_alias": {},
        "first_ts": None,
        "last_ts": None,
    }


def summary(since: str | None = None) -> dict:
    """Aggregate totals + by-model/by-alias buckets since ISO ts (optional)."""
    try:
        return spend_ledger.summarize(ledger_path(), since=since)
    except Exception:
        return _empty_summary()


def recent_rows(since: str | None = None, limit: int = 50) -> list[dict]:
    """Raw ledger rows (newest last → returned newest first), capped."""
    try:
        rows = spend_ledger.load(ledger_path())
    except Exception:
        return []
    if since:
        # ISO timestamps from one writer compare correctly as strings.
        rows = [r for r in rows if str(r.get("ts") or "") >= since]
    return list(reversed(rows[-limit:]))
