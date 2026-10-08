"""Structured delegation contract — what a subagent reports back.

`## Harness usage` was emitted by nine agent files and parsed by nothing. It
cost tokens on every delegation and produced no machine-checkable value.

This replaces it with a single line of NDJSON that the parent can parse and
`pipa` can aggregate:

    {"event":"delegation","agent":"dev","tier":"mid","skills":["debugging"],
     "files":["src/auth.py"],"verified":true,"outcome":"done"}

Field meanings, chosen so a parent can act without re-reading prose:

- `agent`   who ran, so the parent can attribute a result
- `tier`    which model tier served it, so cost is attributable
- `skills`  which skills loaded, so skill triggers can be tuned
- `files`   what was touched, so the parent can diff or review precisely
- `verified` whether the agent actually ran its verification command; a
            false here is the signal that a result is unconfirmed
- `outcome` done | partial | blocked | failed, so the parent can decide
            whether to delegate again or escalate to the user

Deliberately one line: it is appended to a log, and multi-line JSON breaks
NDJSON. `outcome: blocked` plus a `note` is the honest way to say "I could
not finish" instead of claiming success.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

OUTCOMES = ("done", "partial", "blocked", "failed")
CONTRACT_FILE = "delegations.ndjson"


def build(
    *,
    agent: str,
    outcome: str = "done",
    tier: str = "",
    skills: Iterable[str] = (),
    files: Iterable[str] = (),
    verified: bool | None = None,
    note: str = "",
) -> Dict[str, Any]:
    """Build one contract record. Never raises on bad input — it clamps."""
    if outcome not in OUTCOMES:
        outcome = "partial" if outcome not in OUTCOMES else outcome
    rec: Dict[str, Any] = {
        "event": "delegation",
        "agent": agent or "unknown",
        "outcome": outcome,
    }
    if tier:
        rec["tier"] = tier
    skills_l: List[str] = [s for s in (skills or []) if s]
    if skills_l:
        rec["skills"] = skills_l
    files_l: List[str] = [f for f in (files or []) if f]
    if files_l:
        rec["files"] = files_l
    if verified is not None:
        rec["verified"] = bool(verified)
    if note:
        rec["note"] = str(note)[:500]
    return rec


def line(**kwargs: Any) -> str:
    """One NDJSON line, ready to paste. Compact and ASCII-safe."""
    return json.dumps(build(**kwargs), ensure_ascii=False, separators=(",", ":"))


def record(path: Path, **kwargs: Any) -> str:
    """Append a contract to a log and return the line written."""
    rec_line = line(**kwargs)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(rec_line + "\n")
    except OSError:
        pass
    return rec_line


def read_log(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8", errors="ignore") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    out.append(json.loads(raw))
                except ValueError:
                    continue
    except OSError:
        return []
    return out


def summarize(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate a run: counts by agent/outcome, unverified work, touched files."""
    by_agent: Dict[str, int] = {}
    by_outcome: Dict[str, int] = {}
    files: List[str] = []
    unverified: List[str] = []
    skills: List[str] = []
    for r in records:
        a = str(r.get("agent", "unknown"))
        by_agent[a] = by_agent.get(a, 0) + 1
        o = str(r.get("outcome", "done"))
        by_outcome[o] = by_outcome.get(o, 0) + 1
        for f in r.get("files") or []:
            if f not in files:
                files.append(f)
        for s in r.get("skills") or []:
            if s not in skills:
                skills.append(s)
        if r.get("verified") is False and a not in unverified:
            unverified.append(a)
    return {
        "total": len(records),
        "by_agent": by_agent,
        "by_outcome": by_outcome,
        "files": files,
        "skills": skills,
        "unverified": unverified,
        "needs_attention": bool(by_outcome.get("blocked") or by_outcome.get("failed")
                                or unverified),
    }
