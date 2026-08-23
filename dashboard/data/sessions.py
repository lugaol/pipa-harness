"""Session-log reader for the active project.

Thin wrapper over pipa.session bound to the active project's NDJSON log;
falls back to the harness-global state log when no project is detected.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pipa import config, session


def log_path() -> Path:
    """Active project's session log, else the harness state log path."""
    try:
        project = config.find_project()
    except Exception:
        project = None
    if project is not None:
        return config.session_log_path(project)
    return config.state_dir() / "session.log.ndjson"


def all_sessions() -> List[dict]:
    """Session summaries oldest-first: {id, runtime, start, end, events, tools, models}."""
    try:
        return session.sessions(log_path())
    except Exception:
        return []


def events_for(sid: str) -> List[dict]:
    """All events of one session, chronological; [] when absent."""
    try:
        return session.load_session(log_path(), sid)
    except Exception:
        return []


def tail(n: int = 20) -> List[dict]:
    """Last n raw events of the active log."""
    try:
        return session.tail(log_path(), n)
    except Exception:
        return []
