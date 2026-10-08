"""Tests for the inter-agent bus and the delegation contract.

These two modules are the only new runtime surface: the bus is how agents
talk, and the contract is how a parent knows what a child claims. Both are
append-only files, so the tests focus on the properties that actually matter
under concurrency: addressing, cursor semantics, and tolerance of a torn
line written by a killed process.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipa import bus, contract  # noqa: E402


@pytest.fixture()
def project(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    from pipa import config

    monkeypatch.setattr(config, "find_project", lambda: tmp_path)
    return tmp_path


# ── bus ──────────────────────────────────────────────────────────────────────

def test_post_then_read_round_trip(project):
    ok, msg = bus.post(frm="explorer", body="found it", to="dev", project=project)
    assert ok, msg
    recs, total = bus.read(to="dev", project=project)
    assert len(recs) == 1
    assert recs[0]["from"] == "explorer"
    assert recs[0]["body"] == "found it"
    assert total == 1


def test_addressing_is_selective(project):
    bus.post(frm="a", to="dev", body="for dev only", project=project)
    bus.post(frm="b", to="qa", body="for qa only", project=project)
    dev, _ = bus.read(to="dev", project=project)
    qa, _ = bus.read(to="qa", project=project)
    assert [m["body"] for m in dev] == ["for dev only"]
    assert [m["body"] for m in qa] == ["for qa only"]


def test_broadcast_is_readable_by_everyone(project):
    bus.post(frm="architect", to="all", body="shared concern", project=project)
    for who in ("dev", "qa", "explorer"):
        recs, _ = bus.read(to=who, project=project)
        assert len(recs) == 1, f"{who} should see the broadcast"


def test_cursor_returns_only_new_messages(project):
    bus.post(frm="a", body="one", project=project)
    _, cursor = bus.read(project=project)
    bus.post(frm="b", body="two", project=project)
    new, cursor2 = bus.read(since=cursor, project=project)
    assert [m["body"] for m in new] == ["two"]
    assert cursor2 == cursor + 1


def test_kind_filter(project):
    bus.post(frm="a", body="x", kind="finding", project=project)
    bus.post(frm="a", body="y", kind="blocker", project=project)
    recs, _ = bus.read(kind="blocker", project=project)
    assert [m["body"] for m in recs] == ["y"]


def test_empty_body_rejected(project):
    ok, msg = bus.post(frm="a", body="   ", project=project)
    assert not ok
    assert "empty body" in msg


def test_unknown_kind_rejected(project):
    ok, msg = bus.post(frm="a", body="x", kind="nonsense", project=project)
    assert not ok
    assert "unknown kind" in msg


def test_long_body_is_truncated_not_dropped(project):
    ok, _ = bus.post(frm="a", body="x" * (bus.MAX_BODY + 500), project=project)
    assert ok
    recs, _ = bus.read(project=project)
    assert len(recs) == 1
    assert "truncated" in recs[0]["body"]


def test_torn_line_from_killed_writer_is_skipped(project):
    bus.post(frm="a", body="good", project=project)
    path = bus.bus_path(project)
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"id":"x","from":"ghost","to":"dev","ki')  # no newline
    recs, _ = bus.read(project=project)
    assert [m["body"] for m in recs] == ["good"]


def test_read_on_missing_board_is_not_an_error(project):
    recs, total = bus.read(project=project)
    assert recs == []
    assert total == 0


def test_every_record_is_one_line(project):
    """NDJSON invariant: a record must never span lines, or readers break."""
    bus.post(frm="a", body="line one\nline two", project=project)
    raw = bus.bus_path(project).read_text(encoding="utf-8")
    assert len(raw.strip().splitlines()) == 1
    recs, _ = bus.read(project=project)
    assert "line one" in recs[0]["body"]


# ── contract ─────────────────────────────────────────────────────────────────

def test_contract_is_single_line_json():
    out = contract.line(agent="dev", outcome="done", tier="mid", verified=True)
    assert "\n" not in out
    rec = json.loads(out)
    assert rec["event"] == "delegation"
    assert rec["agent"] == "dev"
    assert rec["verified"] is True


def test_bad_outcome_is_clamped_not_dropped():
    rec = contract.build(agent="x", outcome="totally-made-up")
    assert rec["outcome"] in contract.OUTCOMES


def test_summarize_flags_unverified_and_blocked(tmp_path):
    log = tmp_path / "d.ndjson"
    contract.record(log, agent="a", outcome="done", verified=True)
    contract.record(log, agent="b", outcome="blocked", verified=False, note="nope")
    contract.record(log, agent="c", outcome="done", verified=False)
    s = contract.summarize(contract.read_log(log))
    assert s["total"] == 3
    assert set(s["unverified"]) == {"b", "c"}
    assert s["needs_attention"] is True


def test_summarize_deduplicates_files(tmp_path):
    log = tmp_path / "d.ndjson"
    contract.record(log, agent="a", files=["f1", "f2"])
    contract.record(log, agent="b", files=["f1"])
    s = contract.summarize(contract.read_log(log))
    assert s["files"].count("f1") == 1


def test_read_log_tolerates_garbage(tmp_path):
    log = tmp_path / "d.ndjson"
    contract.record(log, agent="a", outcome="done")
    with log.open("a", encoding="utf-8") as fh:
        fh.write("not json at all\n")
    recs = contract.read_log(log)
    assert len(recs) == 1
    assert recs[0]["agent"] == "a"


# ── status severity: optional subsystems must not read as failures ──────────

def test_optional_check_is_warn_not_fail(tmp_path, monkeypatch, capsys):
    """A fresh project with no code graph is a choice, not a fault.

    Reporting it as FAIL makes the first health check look broken, which
    trains the reader to ignore red output — the failure mode this harness
    spent a whole refactor removing.

    Hermetic: the two genuinely-external probes (the gateway over HTTP, and
    graphify on PATH) are stubbed. This test used to assert a global
    `fail == 0` while depending on both, so it passed or failed according to
    whether the developer's machine happened to have a gateway running.
    """
    import json as _json
    import types
    from pipa.commands import status as status_mod

    # A complete, healthy project except for the optional code graph.
    (tmp_path / ".git").mkdir()
    (tmp_path / ".pipa").mkdir()
    (tmp_path / ".pipa" / "AGENTS.md").write_text("- Build: `make`\n")
    (tmp_path / ".pipa" / "runtime").write_text("opencode\n")
    (tmp_path / "AGENTS.md").write_text("# project\n")

    monkeypatch.setattr(status_mod.config, "find_project", lambda: tmp_path)
    # status treats project == harness_root as "not inside a project".
    monkeypatch.setattr(status_mod.config, "harness_root", lambda: tmp_path / "_harness")
    monkeypatch.setattr(status_mod.config, "git_root", lambda *a, **k: tmp_path)
    monkeypatch.setattr(
        status_mod.config, "session_log_path", lambda p=None: tmp_path / "nope.ndjson",
    )
    # External probes: gateway answers, and every binary resolves.
    # collect_checks probes binaries via shutil.which, so stub that rather
    # than the old services.have indirection.
    monkeypatch.setattr(status_mod.runtimes, "installed", lambda: ["opencode"])
    import shutil
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/local/bin/{name}")

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return _json.dumps({"data": [{"id": "mid"}, {"id": "high"}]}).encode()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Resp())

    status_mod.cmd_status(types.SimpleNamespace(json=True))
    data = _json.loads(capsys.readouterr().out)

    graph = [c for c in data["checks"] if c["name"] == "graphify-graph"]
    assert graph, "graphify check should still be reported"
    assert graph[0]["status"] == "warn", graph[0]
    assert "optional" in graph[0]["detail"]
    # The invariant is about the OPTIONAL class specifically: nothing reported
    # as optional may ever be a failure.
    assert data["summary"]["fail"] == 0, data["checks"]


def test_optional_checks_never_count_as_failures(tmp_path, monkeypatch, capsys):
    """No check carrying an 'optional' detail may be a FAIL, whatever the machine.

    The machine-independent form of the rule above: assert against the shape of
    the output rather than against a live environment.
    """
    import json as _json
    import types
    from pipa.commands import status as status_mod

    monkeypatch.setattr(status_mod.config, "find_project", lambda: None)
    monkeypatch.setattr(status_mod.config, "harness_root", lambda: tmp_path / "_h")
    monkeypatch.setattr(status_mod.config, "git_root", lambda *a, **k: None)

    status_mod.cmd_status(types.SimpleNamespace(json=True))
    data = _json.loads(capsys.readouterr().out)
    offenders = [
        c for c in data["checks"]
        if "optional" in c["detail"] and c["status"] == "fail"
    ]
    assert not offenders, f"optional checks reported as failures: {offenders}"
