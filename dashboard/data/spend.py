"""Spend-ledger reader bound to the harness state dir.

Thin adapter: aggregation and the `since` filter are owned by pipa.spend.

Two bugs lived here and both are fixed by delegating properly:

1. `ledger_path()` returned a **str**, but `pipa.spend.summarize` expects a
   `Path` and calls `path.exists()`. The resulting AttributeError was caught
   by the broad `except` and turned into an all-zero summary — so the
   dashboard's Spend tab reported 0 rows and $0.00 against a ledger holding
   hundreds of rows. A swallowed error that renders as a real number is worse
   than a crash: nothing looks broken.
2. `recent_rows` re-implemented the `since` filter as a raw string compare,
   while `pipa.spend` parses ISO timestamps with timezone. The summary and the
   table it summarises could disagree about which rows are in range.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from pipa import spend as spend_ledger


def ledger_path() -> Optional[Path]:
    """The ledger as a Path, or None when there is no ledger yet.

    A Path, not a str: every consumer here calls `.exists()` on it.
    """
    path = spend_ledger.default_path()
    return path if path.exists() else None


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
    except Exception as exc:
        # Degrade, but say so. Returning a confident all-zero summary for a
        # broken ledger is indistinguishable from "you have spent nothing".
        out = _empty_summary()
        out["error"] = f"{type(exc).__name__}: {exc}"[:200]
        return out


def recent_rows(since: str | None = None, limit: int = 50) -> list[dict]:
    """Raw ledger rows (newest last → returned newest first), capped.

    The `since` filter is pipa.spend's, so this table and `summary()` always
    agree about which rows are in range.
    """
    path = ledger_path()
    if path is None:
        return []
    try:
        rows = [
            r for r in spend_ledger.load(path)
            if not since or spend_ledger.on_or_after(r.get("ts"), since)
        ]
    except Exception:
        return []
    return list(reversed(rows[-limit:]))