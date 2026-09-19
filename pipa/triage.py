"""L1 triage signals — report-only, best-effort, never fails loudly.

Single owner for loop signal-gathering. Every signal degrades to
"unknown" instead of raising: a missing log, absent graph, or broken
reader is a signal state, not an error. Composed by `pipa triage` (CLI)
and the Team page alerts strip — never duplicate these rollups.

Autonomy: L1 only. Collectors read; they never edit code, push, or
auto-fix. The only write in the loop is the STATE.md rewrite owned by
the CLI command, not this module.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

GRAPH_FRESH_DAYS = 7
SESSION_WINDOW_DAYS = 7


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(raw) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def doctor_signal() -> dict:
    """{status, fail[], warn[]} — fail closed on reader errors."""
    try:
        from pipa.commands.doctor import _collect

        checks = _collect()
    except Exception as exc:
        return {"status": "unknown", "fail": [], "warn": [],
                "detail": f"doctor unreadable: {exc}"}
    fail = [c["name"] for c in checks if c.get("status") == "fail"]
    warn = [c["name"] for c in checks if c.get("status") == "warn"]
    return {"status": "fail" if fail else "warn" if warn else "pass",
            "fail": fail, "warn": warn,
            "detail": f"{len(checks) - len(fail) - len(warn)} pass, "
                      f"{len(warn)} warn, {len(fail)} fail"}


def _graph_age(graph_file: Path) -> str:
    try:
        mtime = datetime.fromtimestamp(graph_file.stat().st_mtime,
                                       tz=timezone.utc)
    except OSError:
        return "missing"
    age = (_utcnow() - mtime).days
    if age <= GRAPH_FRESH_DAYS:
        return "fresh"
    return f"stale: {age}d"


def graph_signal() -> dict:
    """{harness, project} freshness — fresh | stale: Nd | missing | unknown."""
    from pipa import config

    out = {}
    try:
        root = config.harness_root()
        out["harness"] = _graph_age(root / "graphify-out" / "graph.json")
    except Exception:
        out["harness"] = "unknown"
    try:
        project = config.find_project()
        out["project"] = (_graph_age(project / "graphify-out" / "graph.json")
                          if project else "missing")
    except Exception:
        out["project"] = "unknown"
    return out


def memory_signal(project: Path | None = None) -> dict:
    """{stale_notes, gc} — counts only, details live in recall/memory-gc."""
    try:
        from pipa.recall import stale_report

        stale = stale_report(project=project)
    except Exception:
        stale = None
    try:
        from pipa import config
        from pipa.memory_gc import collect_candidates

        cands = collect_candidates(config.state_dir(),
                                   config.harness_root() / "vault")
        gc = {"rollup": 0, "prune": 0, "report": 0}
        for _, (action, _) in cands.items():
            if action in gc:
                gc[action] += 1
    except Exception:
        gc = None
    return {"stale_notes": None if stale is None else len(stale), "gc": gc}


def sessions_signal(project: Path | None = None) -> dict:
    """{sessions_7d, events_7d, errors_7d} from the project session bus."""
    try:
        from pipa import config
        from pipa import session as session_mod

        proj = project if project is not None else config.find_project()
        log = config.session_log_path(proj) if proj else None
        if not log or not log.exists():
            return {"sessions_7d": 0, "events_7d": 0, "errors_7d": 0,
                    "detail": "no session bus"}
        cutoff = _utcnow() - timedelta(days=SESSION_WINDOW_DAYS)
        summaries = session_mod.sessions(log)
        recent = [s for s in summaries
                  if (_parse_ts(s.get("start")) or _utcnow()) >= cutoff]
        errors = 0
        for e in session_mod.iter_events(log):
            ts = _parse_ts(e.get("ts"))
            if ts is not None and ts < cutoff:
                continue
            if e.get("event") == "error" or e.get("status") == "error":
                errors += 1
        return {"sessions_7d": len(recent),
                "events_7d": sum(s.get("events", 0) for s in recent),
                "errors_7d": errors,
                "detail": f"{len(recent)} sessions in {SESSION_WINDOW_DAYS}d"}
    except Exception as exc:
        return {"sessions_7d": 0, "events_7d": 0, "errors_7d": 0,
                "detail": f"unknown: {exc}"}


def collect_signals(project: Path | None = None) -> dict:
    """Full L1 signal snapshot. Never raises (each leg degrades)."""
    from pipa import __version__

    return {
        "at": _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "version": __version__,
        "doctor": doctor_signal(),
        "graph": graph_signal(),
        "memory": memory_signal(project),
        "sessions": sessions_signal(project),
    }


def needs_human(signals: dict) -> list[str]:
    """Signal lines a human should look at (empty = all quiet)."""
    out = []
    doc = signals.get("doctor") or {}
    for name in doc.get("fail") or []:
        out.append(f"doctor FAIL: {name}")
    graph = signals.get("graph") or {}
    for scope in ("harness", "project"):
        state = graph.get(scope, "")
        if state.startswith("stale"):
            out.append(f"graph {scope} {state}")
    mem = signals.get("memory") or {}
    if (mem.get("stale_notes") or 0) > 0:
        out.append(f"{mem['stale_notes']} stale note(s) — pipa recall --stale")
    gc = mem.get("gc") or {}
    if (gc.get("rollup", 0) + gc.get("prune", 0)) > 0:
        out.append(f"GC eligible: {gc.get('rollup', 0)} rollup + "
                   f"{gc.get('prune', 0)} prune — pipa memory-gc")
    sess = signals.get("sessions") or {}
    if (sess.get("errors_7d") or 0) > 0:
        out.append(f"{sess['errors_7d']} session error(s) in 7d")
    return out
