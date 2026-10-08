"""System status for the dashboard — a thin adapter over `pipa status`.

Thin adapter, deliberately. This module used to re-implement health probing
("mirrors `pipa status` essentials", per its own docstring) with no severity
concept at all, which produced the worst outcome in the harness: the same dead
gateway read FAIL in `pipa status`, WARN in `pipa doctor`, and red on the
Status page, and subsystem names drifted apart across the three ("litellm" vs
"litellm gateway" vs "gateway") so string-keyed lookups broke silently on any
rename.

Now: pipa.commands.status.collect_checks() owns what is probed and how it is
classified; this only reshapes the result for the page, and preserves
`status` so the dashboard can finally render warn as warn.
"""
from __future__ import annotations

from typing import Optional

from pipa import config
from pipa.commands.status import collect_checks


def checks() -> list[dict]:
    """[{name, status, ok, detail}] — status is pass|warn|fail.

    `ok` is retained for the sidebar pill and existing callers, and means
    "not a failure": warn counts as up, because an unindexed code graph is a
    choice, not an outage.
    """
    rows = collect_checks()
    return [
        {
            "name": r["name"],
            "status": r["status"],
            "ok": r["status"] != "fail",
            "detail": r["detail"],
        }
        for r in rows
    ]



def project_info() -> Optional[dict]:
    """Active project: path, name, runtime.

    The runtime marker is read through pipa.runtime's owner rather than by
    opening the file here — three modules did that independently.
    """
    from pipa import runtime as runtimes

    try:
        project = config.find_project()
    except Exception:
        project = None
    if project is None:
        return None
    runtime = ""
    try:
        runtime = runtimes.read_project_runtime(project) or ""
    except Exception:
        runtime = ""
    return {
        "path": str(project),
        "name": project.name,
        "runtime": runtime or "auto",
    }