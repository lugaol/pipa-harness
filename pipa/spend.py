"""Reader/aggregator for the LiteLLM spend ledger (NDJSON).

The gateway callback (tools/litellm_hooks/spend_callback.py) appends one
metadata-only row per completion. This module reads it back for `pipa status`
and reporting. Rows never contain message content, so reports are safe to
print; a missing or half-written ledger is never an error.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def default_path() -> Path:
    env = os.environ.get("PIPA_SPEND_LOG")
    if env:
        return Path(env)
    return Path.home() / ".pipa" / "spend.ndjson"


def iter_rows(path: Path):
    if not path.exists():
        return
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def load(path: Path | None = None) -> list[dict]:
    return list(iter_rows(path or default_path()))


def _num(value) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def _parse_ts(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _on_or_after(ts, floor: datetime | None, since_raw: str) -> bool:
    if not ts:
        return False
    if floor is None:
        return True
    parsed = _parse_ts(ts)
    if parsed is None:
        return str(ts) >= since_raw
    return parsed >= floor


def summarize(path: Path | None = None, since: str | None = None) -> dict:
    """Aggregate the ledger; `since` (ISO timestamp) keeps rows at/after it."""
    out = {
        "rows": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": 0.0,
        "by_model": {},
        "by_alias": {},
        "first_ts": None,
        "last_ts": None,
    }
    floor = _parse_ts(since)
    for row in iter_rows(path or default_path()):
        if since and not _on_or_after(row.get("ts"), floor, since):
            continue
        ti, to, cost = int(_num(row.get("tokens_in"))), int(_num(row.get("tokens_out"))), _num(row.get("cost_usd"))
        out["rows"] += 1
        out["tokens_in"] += ti
        out["tokens_out"] += to
        out["cost_usd"] += cost
        ts = row.get("ts")
        if ts:
            out["first_ts"] = out["first_ts"] or ts
            out["last_ts"] = ts
        for bucket, key in (("by_model", row.get("model")), ("by_alias", row.get("alias"))):
            b = out[bucket].setdefault(key or "?", {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0})
            b["calls"] += 1
            b["tokens_in"] += ti
            b["tokens_out"] += to
            b["cost_usd"] += cost
    return out


def format_report(summary: dict) -> str:
    lines = [
        f"spend · {summary['rows']} calls · ${summary['cost_usd']:.4f}",
        f"  tokens: {summary['tokens_in']:,} in / {summary['tokens_out']:,} out",
    ]
    if summary.get("first_ts"):
        lines.append(f"  window: {summary['first_ts']} → {summary['last_ts']}")

    def section(title: str, bucket: dict) -> None:
        if not bucket:
            return
        lines.append(f"  {title}:")
        for name, s in sorted(bucket.items()):
            lines.append(
                f"    {str(name)[:28]:<28} {s['calls']:>5} calls"
                f" {s['tokens_in']:>10,} in {s['tokens_out']:>10,} out ${s['cost_usd']:.4f}"
            )

    section("by model", summary.get("by_model") or {})
    section("by alias", summary.get("by_alias") or {})
    return "\n".join(lines)
