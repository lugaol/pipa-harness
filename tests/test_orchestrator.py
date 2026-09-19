"""Orchestrator (primary-agent) tier: wire fallback matrix + API routes."""
import json
import shutil
import sys
from pathlib import Path

import pytest

HARNESS_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = HARNESS_ROOT / "dashboard"

for _p in (str(HARNESS_ROOT), str(DASHBOARD_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytest.importorskip("httpx")

import pipa.runtime as rt
from pipa import agent_tiers, config


def _client():
    from fastapi.testclient import TestClient

    import server

    return TestClient(server.app, raise_server_exceptions=False)


def _isolated_state(monkeypatch, tmp_path):
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "state_dir", lambda: state)
    return state


def _stub_resolution(monkeypatch, mapping):
    from types import SimpleNamespace

    def fake():
        return {t: SimpleNamespace(active=True, display=t, alias=t)
                for t in mapping}
    monkeypatch.setattr("pipa.model_registry.tier_resolution", fake)


def test_primary_tier_default_from_map(monkeypatch, tmp_path):
    _isolated_state(monkeypatch, tmp_path)
    assert rt.primary_tier() == rt.AGENT_MODEL_MAP["orchestrator"]


def test_primary_tier_override_wins(monkeypatch, tmp_path):
    _isolated_state(monkeypatch, tmp_path)
    agent_tiers.set_tier_override("orchestrator", "low")
    assert rt.primary_tier() == "low"
    agent_tiers.reset_override("orchestrator")
    assert rt.primary_tier() == rt.AGENT_MODEL_MAP["orchestrator"]


def test_primary_tier_rejects_unknown(monkeypatch, tmp_path):
    _isolated_state(monkeypatch, tmp_path)
    agent_tiers.set_tier_override("orchestrator", "ultra")
    assert rt.primary_tier() == rt.AGENT_MODEL_MAP["orchestrator"]


def test_render_uses_orchestrator_when_resolvable(monkeypatch, tmp_path):
    _isolated_state(monkeypatch, tmp_path)
    _stub_resolution(monkeypatch, ("low", "xhigh"))
    agent_tiers.set_tier_override("orchestrator", "low")
    cfg = rt.render_opencode_config(HARNESS_ROOT)
    assert cfg["model"] == "litellm/low", "override pins the primary"
    agent_tiers.reset_override("orchestrator")
    cfg = rt.render_opencode_config(HARNESS_ROOT)
    assert cfg["model"] == "litellm/xhigh", "default orchestrator tier applies"


def test_render_falls_back_to_strongest(monkeypatch, tmp_path):
    _isolated_state(monkeypatch, tmp_path)
    _stub_resolution(monkeypatch, ("low", "mid"))
    monkeypatch.setattr(rt, "primary_tier", lambda: "")
    cfg = rt.render_opencode_config(HARNESS_ROOT)
    assert cfg["model"] == "litellm/mid", "unresolvable primary falls back"


def test_orchestrator_routes(monkeypatch, tmp_path):
    _isolated_state(monkeypatch, tmp_path)
    client = _client()
    r = client.put("/api/orchestrator", json={"tier": "low"})
    assert r.status_code == 200, r.text
    assert r.json()["tier"] == "low"
    r = client.put("/api/orchestrator", json={"tier": "ultra"})
    assert r.status_code == 400
    r = client.put("/api/orchestrator", json={})
    assert r.status_code == 400
    r = client.post("/api/orchestrator/reset")
    assert r.status_code == 200, r.text
    assert r.json()["tier"] == rt.AGENT_MODEL_MAP["orchestrator"]
    payload = client.get("/api/dashboard").json()
    orch = next(a for a in payload["agents"] if a["name"] == "orchestrator")
    assert orch["source"] == "primary"
    assert orch["recommended"] == rt.AGENT_MODEL_MAP["orchestrator"]
