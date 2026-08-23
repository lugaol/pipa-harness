"""Hook system for observability.

Runtimes (or pipa itself) call `pipa hook <event> ...` to append events to
the shared per-project session log (<project>/.pipa/state/session.log.ndjson).
The NDJSON format is identical across runtimes, so the dashboard, resume and
fork tooling work regardless of which runtime produced the events.

Events:
  session-start [runtime]        mark the beginning of a session
  session-end                    mark the end of a session
  pre-tool <tool> [args]         before a tool call
  post-tool <tool> [output]      after a tool call
  pre-model <alias> [prompt]     before an LLM request
  post-model <alias> [response]  after an LLM response (cost/tokens optional)
  note <text>                    free-form annotation

DeepSeek Harness writes its own native session log; these hooks exist mainly
for OpenCode (wired via opencode.jsonc) and for manual instrumentation.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import config

EVENTS = {
    "session-start",
    "session-end",
    "pre-tool",
    "post-tool",
    "pre-model",
    "post-model",
    "note",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def emit(
    event: str,
    project: Path | None = None,
    runtime: str | None = None,
    **fields,
) -> Path:
    """Append one NDJSON event to the project's session log.

    Falls back to the harness-global state dir when no project is found.
    """
    if event not in EVENTS:
        raise ValueError(f"unknown hook event '{event}' (choose: {', '.join(sorted(EVENTS))})")
    project = project or config.find_project()
    if project:
        log = config.session_log_path(project)
    else:
        log = config.state_dir() / config.SESSION_LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": _now(), "event": event, **fields}
    if runtime:
        record["runtime"] = runtime
    with log.open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return log


def main(argv: list[str]) -> int:
    """CLI entry: pipa hook <event> [args...]"""
    if not argv or argv[0] not in EVENTS:
        print(
            f"usage: pipa hook <{'|'.join(sorted(EVENTS))}> [args...]",
            file=sys.stderr,
        )
        return 2
    event, rest = argv[0], argv[1:]
    fields: dict = {}
    if event in ("pre-tool", "post-tool", "pre-model", "post-model"):
        if not rest:
            print(f"usage: pipa hook {event} <name> [payload]", file=sys.stderr)
            return 2
        key = "tool" if "tool" in event else "model"
        fields[key] = rest[0]
        if len(rest) > 1:
            fields["payload"] = " ".join(rest[1:])
    elif event == "session-start":
        if rest:
            fields["runtime"] = rest[0]
    elif event == "note":
        fields["text"] = " ".join(rest)
    runtime = fields.pop("runtime", None) or os.environ.get("PIPA_RUNTIME")
    emit(event, runtime=runtime, **fields)
    return 0
