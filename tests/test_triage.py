"""pipa.triage — L1 signals degrade gracefully, needs_human is exact."""
from pipa import triage


def test_collect_signals_shape():
    s = triage.collect_signals()
    assert set(s) == {"at", "version", "doctor", "graph", "memory", "sessions"}
    assert s["doctor"]["status"] in ("pass", "warn", "fail", "unknown")
    assert set(s["graph"]) == {"harness", "project"}
    assert "stale_notes" in s["memory"] and "gc" in s["memory"]
    assert "errors_7d" in s["sessions"]


def test_graph_age_states(tmp_path):
    import os
    import time

    fresh = tmp_path / "g.json"
    fresh.write_text("{}")
    assert triage._graph_age(fresh) == "fresh"
    old = tmp_path / "o.json"
    old.write_text("{}")
    ancient = time.time() - 30 * 86400
    os.utime(old, (ancient, ancient))
    assert triage._graph_age(old).startswith("stale")
    assert triage._graph_age(tmp_path / "nope.json") == "missing"


def test_needs_human_quiet():
    signals = {
        "doctor": {"status": "pass", "fail": [], "warn": []},
        "graph": {"harness": "fresh", "project": "missing"},
        "memory": {"stale_notes": 0, "gc": {"rollup": 0, "prune": 0}},
        "sessions": {"errors_7d": 0},
    }
    assert triage.needs_human(signals) == []


def test_needs_human_flags_all_legs():
    signals = {
        "doctor": {"status": "fail", "fail": ["tiers.yaml"], "warn": []},
        "graph": {"harness": "stale: 40d", "project": "fresh"},
        "memory": {"stale_notes": 3, "gc": {"rollup": 2, "prune": 1}},
        "sessions": {"errors_7d": 2},
    }
    needs = triage.needs_human(signals)
    assert len(needs) == 5
    assert any("tiers.yaml" in n for n in needs)
    assert any("stale" in n for n in needs)
    assert any("recall --stale" in n for n in needs)
    assert any("memory-gc" in n for n in needs)
    assert any("error" in n for n in needs)


def test_cmd_triage_writes_state(monkeypatch, tmp_path, capsys):
    from types import SimpleNamespace

    from pipa import config
    from pipa.commands.triage import cmd_triage

    monkeypatch.setattr(config, "harness_root", lambda: tmp_path)
    monkeypatch.setattr(config, "find_project", lambda *a: None)
    assert cmd_triage(SimpleNamespace(json=False, no_write=False)) == 0
    out = capsys.readouterr().out
    assert "triage ·" in out
    state = tmp_path / "vault" / "triage" / "STATE.md"
    assert state.exists()
    text = state.read_text()
    assert text.startswith("# Triage STATE — ") and "route: triage" in text


def test_cmd_triage_json_no_write(monkeypatch, tmp_path, capsys):
    import json
    from types import SimpleNamespace

    from pipa import config
    from pipa.commands.triage import cmd_triage

    monkeypatch.setattr(config, "harness_root", lambda: tmp_path)
    monkeypatch.setattr(config, "find_project", lambda *a: None)
    assert cmd_triage(SimpleNamespace(json=True, no_write=True)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "needs_human" in payload and "doctor" in payload
    assert not (tmp_path / "vault" / "triage" / "STATE.md").exists()
