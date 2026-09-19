#!/usr/bin/env python3
"""Shared usage-rollup parsing for team adoption reports.

Single implementation used by both `pipa usage-report` (CLI) and the
dashboard Observability → Usage tab — never duplicate these rollups.
Inputs are the session summaries (pipa.session.sessions) and the spend
summary (pipa.spend.summarize); both tolerate missing/partial data.
Ported from ia_harness tools/metrics_lib.py, adapted to pipa's
session NDJSON + spend ledger (no vault metrics shards here).
"""
from __future__ import annotations

from collections import Counter


def sessions_per_day(summaries: list) -> list:
    """[(day, count)] oldest-first from session `start` timestamps."""
    counts: Counter = Counter()
    for s in summaries or []:
        day = str(s.get("start") or "")[:10]
        if len(day) == 10 and day[4] == "-" and day[7] == "-":
            counts[day] += 1
    return sorted(counts.items())


def top_counts(summaries: list, key: str, limit: int = 8) -> list:
    """[(name, total)] merged across sessions for a counts dict key."""
    merged: Counter = Counter()
    for s in summaries or []:
        for name, n in (s.get(key) or {}).items():
            merged[name] += n
    return merged.most_common(limit)


def runtime_mix(summaries: list) -> list:
    """[(runtime, sessions)] — adoption across agent runners."""
    counts: Counter = Counter()
    for s in summaries or []:
        counts[str(s.get("runtime") or "?")] += 1
    return counts.most_common()


def build_report(summaries: list, spend: dict) -> dict:
    """One JSON-able rollup for CLI (`--json`) and dashboard alike."""
    return {
        "sessions": len(summaries or []),
        "per_day": sessions_per_day(summaries),
        "top_tools": top_counts(summaries, "tools"),
        "top_models": top_counts(summaries, "models"),
        "runtimes": runtime_mix(summaries),
        "spend": {
            "rows": (spend or {}).get("rows", 0),
            "cost_usd": (spend or {}).get("cost_usd", 0.0),
            "tokens_in": (spend or {}).get("tokens_in", 0),
            "tokens_out": (spend or {}).get("tokens_out", 0),
        },
    }


def format_report(report: dict) -> str:
    """Human-readable rendering for `pipa usage-report`."""
    lines = [f"usage · {report['sessions']} sessions"]
    per_day = report.get("per_day") or []
    if per_day:
        span = f"{per_day[0][0]} → {per_day[-1][0]}" if len(per_day) > 1 else per_day[0][0]
        lines.append(f"  span: {span} ({len(per_day)} active days)")
        for day, n in per_day[-14:]:
            lines.append(f"    {day}  {n}")

    def section(title, rows, money=False):
        if not rows:
            return
        lines.append(f"  {title}:")
        for name, n in rows:
            lines.append(f"    {str(name)[:36]:<36} {n}")

    section("top tools", report.get("top_tools"))
    section("top session models", report.get("top_models"))
    section("runtimes", report.get("runtimes"))
    sp = report.get("spend") or {}
    lines.append(f"  spend: {sp.get('rows', 0)} calls · "
                 f"${sp.get('cost_usd', 0.0):.4f} · "
                 f"{sp.get('tokens_in', 0):,} in / {sp.get('tokens_out', 0):,} out")
    return "\n".join(lines)
