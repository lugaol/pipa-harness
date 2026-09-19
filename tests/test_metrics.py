"""Usage rollups (Phase 5): pipa.metrics + `pipa usage-report`."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

HARNESS_ROOT = Path(__file__).resolve().parents[1]

if str(HARNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(HARNESS_ROOT))

from pipa import metrics as metrics_lib


SUMMARIES = [
    {"id": "a", "runtime": "opencode", "start": "2026-09-01T10:00:00",
     "tools": {"read": 5, "edit": 2}, "models": {"mid": 3}},
    {"id": "b", "runtime": "opencode", "start": "2026-09-01T12:00:00",
     "tools": {"read": 1}, "models": {"low": 2}},
    {"id": "c", "runtime": "dsh", "start": "2026-09-02T09:00:00",
     "tools": {"grep": 4}, "models": {"mid": 1}},
]

SPEND = {"rows": 10, "cost_usd": 0.5, "tokens_in": 1000, "tokens_out": 200,
         "by_model": {}, "by_alias": {}}


def test_sessions_per_day_oldest_first():
    assert metrics_lib.sessions_per_day(SUMMARIES) == [
        ("2026-09-01", 2), ("2026-09-02", 1)]


def test_top_counts_merge_across_sessions():
    assert metrics_lib.top_counts(SUMMARIES, "tools")[:2] == [
        ("read", 6), ("grep", 4)]
    assert metrics_lib.top_counts(SUMMARIES, "models") == [
        ("mid", 4), ("low", 2)]


def test_runtime_mix():
    assert dict(metrics_lib.runtime_mix(SUMMARIES)) == {
        "opencode": 2, "dsh": 1}


def test_empty_inputs_never_crash():
    report = metrics_lib.build_report([], {})
    assert report["sessions"] == 0
    assert report["per_day"] == []
    text = metrics_lib.format_report(report)
    assert "0 sessions" in text


def test_build_report_shape_is_jsonable():
    report = metrics_lib.build_report(SUMMARIES, SPEND)
    json.dumps(report)  # must survive `pipa usage-report --json`
    assert report["spend"]["cost_usd"] == 0.5
    assert "2 sessions" in metrics_lib.format_report(report) or \
        "3 sessions" in metrics_lib.format_report(report)


def test_usage_report_cli_reads_project_log(monkeypatch, tmp_path, capsys):
    from pipa import config
    from pipa.commands.usage import cmd_usage_report

    proj = tmp_path / "proj"
    (proj / ".pipa" / "state").mkdir(parents=True)
    log = proj / ".pipa" / "state" / "session.log.ndjson"
    log.write_text(json.dumps(
        {"event": "session-start", "session_id": "s1",
         "runtime": "opencode", "ts": "2026-09-03T08:00:00",
         "tool": "read", "model": "mid"}) + "\n")
    monkeypatch.setattr(config, "find_project", lambda *a, **k: proj)
    monkeypatch.setattr(config, "state_dir", lambda: tmp_path / "state")
    (tmp_path / "state").mkdir(exist_ok=True)
    monkeypatch.delenv("PIPA_SPEND_LOG", raising=False)

    assert cmd_usage_report(SimpleNamespace(since=None, json=False)) == 0
    out = capsys.readouterr().out
    assert "1 sessions" in out

    assert cmd_usage_report(SimpleNamespace(since=None, json=True)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["sessions"] == 1
    assert payload["runtimes"] == [["opencode", 1]]
