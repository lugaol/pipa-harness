"""Session-bus NDJSON contract: hooks.emit <-> session.iter_events.

Every record must carry an ISO-parseable `ts` and a canonical `event`;
unknown events are rejected at emit time.
"""
import datetime as dt
from pathlib import Path

import pytest

from pipa import config, hooks, session


@pytest.fixture
def project(tmp_path, monkeypatch) -> Path:
    p = tmp_path / "hooked-proj"
    (p / ".pipa" / "state").mkdir(parents=True)
    monkeypatch.setattr(config, "find_project", lambda start=None: p)
    return p


def test_emit_every_event_roundtrips(project):
    for event in sorted(hooks.EVENTS):
        hooks.emit(event, runtime="test-runtime")
    hooks.emit("pre-tool", tool="Bash", payload="ls")

    records = list(session.iter_events(config.session_log_path(project)))
    assert len(records) == len(hooks.EVENTS) + 1

    seen = set()
    for rec in records:
        assert rec["event"] in hooks.EVENTS
        ts = dt.datetime.fromisoformat(rec["ts"])
        assert ts.tzinfo is not None
        seen.add(rec["event"])
    assert seen == set(hooks.EVENTS)

    last = records[-1]
    assert last["tool"] == "Bash"
    assert last["payload"] == "ls"


def test_log_lands_in_project_state_dir(project):
    log = hooks.emit("note", text="hello")
    assert log.parent == project / ".pipa" / "state"
    assert log.name == config.SESSION_LOG
    assert list(session.iter_events(log))[0]["text"] == "hello"


def test_unknown_event_raises_value_error(project):
    with pytest.raises(ValueError, match="unknown hook event"):
        hooks.emit("definitely-not-an-event")
