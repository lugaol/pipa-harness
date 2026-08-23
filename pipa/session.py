"""Reader for the shared NDJSON session log.

Both runtimes append to <project>/.pipa/state/session.log.ndjson (OpenCode
via pipa hooks, DeepSeek Harness natively). This module reads it back for
`pipa status`, the dashboard, and resume/fork tooling.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator


def iter_events(path: Path) -> Iterator[dict]:
    if not path.exists():
        return
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def tail(path: Path, n: int = 20) -> list[dict]:
    events = list(iter_events(path))
    return events[-n:]


def stats(path: Path) -> dict:
    """Aggregate counts for a session log."""
    out = {
        "events": 0,
        "by_event": {},
        "tools": {},
        "models": {},
        "runtimes": {},
        "first_ts": None,
        "last_ts": None,
    }
    for e in iter_events(path):
        out["events"] += 1
        ev = e.get("event", "?")
        out["by_event"][ev] = out["by_event"].get(ev, 0) + 1
        if e.get("tool"):
            out["tools"][e["tool"]] = out["tools"].get(e["tool"], 0) + 1
        if e.get("model"):
            out["models"][e["model"]] = out["models"].get(e["model"], 0) + 1
        if e.get("runtime"):
            out["runtimes"][e["runtime"]] = out["runtimes"].get(e["runtime"], 0) + 1
        ts = e.get("ts")
        if ts:
            out["first_ts"] = out["first_ts"] or ts
            out["last_ts"] = ts
    return out


# ── sessions (flight recorder) ──────────────────────────────────────────────

def _tagged(path: Path):
    """Yield (session_key, event) pairs, grouping the log chronologically.

    Grouping rule: an explicit session_id wins ("id:<sid>"); otherwise a
    session-start opens a fresh auto bucket ("s<n>", n = open order); any
    other event joins the current bucket (an implicit head bucket 's0'
    holds pre-first-session strays).
    """
    cur: str | None = None
    counter = 0
    for e in iter_events(path):
        sid = e.get("session_id")
        if sid:
            key = f"id:{sid}"
        elif e.get("event") == "session-start" or cur is None:
            key = f"s{counter}"
            counter += 1
        else:
            key = cur
        cur = key
        yield key, e


def sessions(path: Path) -> list[dict]:
    """Group the log into session summaries, oldest first.

    Each summary: {id, runtime, start, end, events, tools{}, models{}}.
    """
    out: list[dict] = []
    by_key: dict[str, dict] = {}
    for key, e in _tagged(path):
        s = by_key.get(key)
        if s is None:
            s = {
                "id": key.removeprefix("id:"),
                "runtime": e.get("runtime"),
                "start": e.get("ts"),
                "end": None,
                "events": 0,
                "tools": {},
                "models": {},
            }
            by_key[key] = s
            out.append(s)
        s["events"] += 1
        if e.get("ts"):
            s["end"] = e["ts"]
        if e.get("runtime"):
            s["runtime"] = e["runtime"]
        if e.get("tool"):
            s["tools"][e["tool"]] = s["tools"].get(e["tool"], 0) + 1
        if e.get("model"):
            s["models"][e["model"]] = s["models"].get(e["model"], 0) + 1
    return out


def load_session(path: Path, sid: str) -> list[dict]:
    """All events of one session, chronological. Empty when absent."""
    return [e for key, e in _tagged(path) if key in (sid, f"id:{sid}")]
