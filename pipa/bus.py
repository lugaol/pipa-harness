"""Inter-agent message bus — a shared, append-only blackboard per project.

Why this exists
---------------
opencode gives an orchestrator exactly one communication primitive: `task()`,
which is parent → child with a single return value. That is enough to
delegate but not to coordinate. Three things are missing in practice:

1. **Sibling visibility.** Two agents exploring different halves of a repo
   cannot see each other's findings; the parent has to relay everything, which
   is precisely the context it was trying to avoid carrying.
2. **Durability across calls.** A subagent's result is prose in one tool
   result. If the parent compacts, or delegates again, that knowledge is gone.
3. **Addressability.** Nothing can say "this is for the implementer" and have
   it arrive there.

A file is the right primitive here, not a socket. Every agent already runs
with the same filesystem and the same CWD, so a shared NDJSON file needs no
daemon, no port, and no cleanup — and it is greppable, diffable, and
survives a crash. Sockets would add a failure mode to buy concurrency nobody
needs at this scale.

Design constraints
------------------
- Append-only. Concurrent `post` calls from parallel agents interleave lines;
  NDJSON keeps each message atomic on its own line, so a reader never sees a
  half-written record.
- Never raises into an agent's session. A communication failure must not fail
  the task, so every error path here degrades to a warning.
- Cheap to read. `read` is O(lines) with an offset cursor, so an agent can
  poll for "what's new since I looked" without re-reading history.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

from pipa import config

BUS_FILE = "bus.ndjson"
MAX_BODY = 4000
VALID_KINDS = ("note", "finding", "question", "blocker", "handoff", "done")


def bus_path(project: Path | None = None) -> Path:
    project = project or config.find_project() or Path.cwd()
    return config.pipa_dir(project) / "state" / BUS_FILE


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def post(
    *,
    frm: str,
    body: str,
    to: str = "all",
    kind: str = "note",
    topic: str = "",
    project: Path | None = None,
) -> tuple[bool, str]:
    """Append one message. Returns (ok, message). Never raises."""
    try:
        body = (body or "").strip()
        if not body:
            return False, "empty body — pass --body"
        if kind not in VALID_KINDS:
            return False, f"unknown kind '{kind}' (choose: {', '.join(VALID_KINDS)})"
        if len(body) > MAX_BODY:
            body = body[:MAX_BODY] + f"… [truncated, {len(body)} chars total]"
        path = bus_path(project)
        path.parent.mkdir(parents=True, exist_ok=True)
        rec: Dict[str, Any] = {
            "id": uuid.uuid4().hex[:8],
            "ts": _now(),
            "from": frm or "unknown",
            "to": to or "all",
            "kind": kind,
        }
        if topic:
            rec["topic"] = topic
        rec["body"] = body
        # One write() of one line: atomic enough for concurrent appenders on
        # POSIX (O_APPEND writes below PIPE_BUF do not interleave).
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True, f"posted {rec['id']} ({kind}) to {rec['to']}"
    except Exception as exc:  # noqa: BLE001 — a bus failure must not fail a task
        return False, f"bus unavailable: {type(exc).__name__}: {exc}"


def read(
    *,
    since: int = 0,
    to: str | None = None,
    frm: str | None = None,
    kind: str | None = None,
    limit: int = 20,
    project: Path | None = None,
) -> tuple[List[dict], int]:
    """[(record)] plus the next cursor. Never raises.

    `to` filters by addressee, and "all" always matches: a message broadcast
    to the board is readable by everyone, which is what makes sibling
    discovery work.
    """
    path = bus_path(project)
    if not path.is_file():
        return [], 0
    out: List[dict] = []
    try:
        with path.open(encoding="utf-8", errors="ignore") as fh:
            for idx, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                if idx <= since:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue  # a torn line from a killed writer; skip it
                if to and to != "all":
                    if rec.get("to") not in (to, "all"):
                        continue
                if frm and rec.get("from") != frm:
                    continue
                if kind and rec.get("kind") != kind:
                    continue
                rec["_line"] = idx
                out.append(rec)
    except Exception as exc:  # noqa: BLE001
        print(f"  bus read failed: {type(exc).__name__}: {exc}")
        return [], since
    total = _line_count(path)
    if limit and len(out) > limit:
        out = out[-limit:]
    return out, total


def _line_count(path: Path) -> int:
    try:
        with path.open("rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def clear(project: Path | None = None) -> tuple[bool, str]:
    """Reset the board. Used by tests and `pipa bus clear`."""
    path = bus_path(project)
    try:
        if path.exists():
            path.unlink()
        return True, f"cleared {path}"
    except Exception as exc:  # noqa: BLE001
        return False, f"could not clear: {exc}"
