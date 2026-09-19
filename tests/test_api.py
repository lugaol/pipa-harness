"""JSON API screens (ia framework parity): status, env-keys, dashboard,
tiers, agents, install state, graph, docs."""
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


def _client():
    from fastapi.testclient import TestClient

    import server

    return TestClient(server.app, raise_server_exceptions=False)


def _seed_catalog(state, providers):
    state.mkdir(parents=True, exist_ok=True)
    (state / "model_catalog.json").write_text(json.dumps({
        "version": 1,
        "fetched_at": "2026-08-23T00:00:00Z",
        "providers": {
            slug: {"ok": True, "error": None, "models": models}
            for slug, models in providers.items()
        },
    }))


def _models_env(monkeypatch, tmp_path):
    """Isolated models dir (real tiers.yaml) + state dir + stubbed gateway."""
    from pipa import config
    import data.services as services_data

    mdir = tmp_path / "models"
    mdir.mkdir()
    shutil.copy(HARNESS_ROOT / "models" / "tiers.yaml", mdir / "tiers.yaml")
    (mdir / "settings.yaml").write_text("litellm_settings: {}\n")
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setattr(config, "models_dir", lambda: mdir)
    monkeypatch.setattr(config, "state_dir", lambda: state)
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    monkeypatch.setattr(services_data, "gateway_restart",
                        lambda: (True, "restarted (test)"))
    return mdir, state


# ── status ────────────────────────────────────────────────────────────────

def test_api_status_shape():
    resp = _client().get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "litellm gateway" in data and "ollama" in data
    for info in data.values():
        assert set(info) == {"up", "detail"}
        assert isinstance(info["up"], bool)


# ── env keys ──────────────────────────────────────────────────────────────

def test_env_keys_masked_no_values(monkeypatch, tmp_path):
    client = _client()
    monkeypatch.setenv("PIPA_ROOT", str(tmp_path))
    monkeypatch.setenv("KILO_API_KEY", "sk-dummy-secret-abcdef")
    resp = client.get("/api/env-keys")
    assert resp.status_code == 200
    data = resp.json()
    assert data["groups"] and data["keys"]
    assert "sk-dummy-secret-abcdef" not in resp.text
    kilo = next(k for k in data["keys"] if k["key"] == "KILO_API_KEY")
    assert kilo["set"] is True and kilo["value"] == "" and kilo["masked"]


def test_env_keys_post_validations(monkeypatch, tmp_path):
    client = _client()
    monkeypatch.setenv("PIPA_ROOT", str(tmp_path))
    assert client.post("/api/env-keys", json={"key": "NOPE", "value": "x"}).status_code == 400
    assert client.post("/api/env-keys", json={"key": "KILO_API_KEY", "value": "has space"}).status_code == 400
    assert client.post("/api/env-keys", json={"key": "KILO_API_KEY", "value": "your-key-here"}).status_code == 400
    assert client.post("/api/env-keys", json={"key": "KILO_API_KEY"}).status_code == 400


def test_env_keys_post_writes_env_and_restarts(monkeypatch, tmp_path):
    import data.services as services_data

    client = _client()
    monkeypatch.setenv("PIPA_ROOT", str(tmp_path))
    monkeypatch.delenv("KILO_API_KEY", raising=False)
    monkeypatch.setattr(services_data, "gateway_restart", lambda: (True, "ok"))
    (tmp_path / ".env").write_text("OTHER=1\n")
    resp = client.post("/api/env-keys", json={"key": "KILO_API_KEY", "value": "sk-live-test-value"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True and body["restarted"] is True
    text = (tmp_path / ".env").read_text()
    assert "KILO_API_KEY=sk-live-test-value" in text and "OTHER=1" in text
    import os

    assert oct(os.stat(tmp_path / ".env").st_mode)[-3:] == "600"


# ── dashboard bootstrap ───────────────────────────────────────────────────

def test_api_dashboard_shape(monkeypatch, tmp_path):
    from pipa import config

    client = _client()
    monkeypatch.setattr(config, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tiers"]["tier_order"] == ["lowest", "low", "mid", "high", "xhigh"]
    assert isinstance(data["agents"], list) and isinstance(data["catalog"], list)
    if data["agents"]:
        row = data["agents"][0]
        assert {"name", "tier", "override", "model", "drift"} <= set(row)


# ── tiers ─────────────────────────────────────────────────────────────────

def test_tier_models_validations(monkeypatch, tmp_path):
    client = _client()
    _models_env(monkeypatch, tmp_path)
    assert client.put("/api/tier-models", json={}).status_code == 400
    assert client.put("/api/tier-models",
                      json={"tiers": {"ultra": {"model": "x"}}}).status_code == 400
    assert client.put("/api/tier-models",
                      json={"tiers": {"mid": {"model": ""}}}).status_code == 400
    assert client.put("/api/tiers/nope", json={"model": "x"}).status_code == 404


def test_tier_models_roundtrip(monkeypatch, tmp_path):
    from pipa import config
    from pipa.model_registry import tier_assignments

    client = _client()
    _mdir, state = _models_env(monkeypatch, tmp_path)
    _seed_catalog(state, {"ollama": [{"id": "qwen3:8b", "name": ""}]})
    resp = client.put("/api/tier-models",
                      json={"tiers": {"low": {"model": "qwen3:8b", "max_steps": 7}}})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True and body["restarted"] is True
    assert tier_assignments()["low"] == "qwen3:8b"

    single = client.put("/api/tiers/mid", json={"model": "qwen3:8b"})
    assert single.status_code == 200
    assert tier_assignments()["mid"] == "qwen3:8b"

    bad_model = client.put("/api/tiers/mid", json={"model": "ghost-model"})
    assert bad_model.status_code == 400


# ── agents ────────────────────────────────────────────────────────────────

def test_agent_tier_roundtrip(monkeypatch, tmp_path):
    from pipa import config
    from data import agents as agents_data

    client = _client()
    monkeypatch.setattr(config, "state_dir", lambda: tmp_path)
    assert client.put("/api/agents/dev", json={}).status_code == 400
    assert client.put("/api/agents/dev", json={"model": "x"}).status_code == 400
    assert client.put("/api/agents/dev", json={"tier": "ultra"}).status_code == 400
    resp = client.put("/api/agents/dev", json={"tier": "high"})
    assert resp.status_code == 200
    assert agents_data.override_for("dev") == "high"
    reset = client.post("/api/agents/dev/reset")
    assert reset.status_code == 200
    assert agents_data.override_for("dev") in (None, "")


def test_agent_tiers_batch(monkeypatch, tmp_path):
    from pipa import config
    from data import agents as agents_data

    client = _client()
    monkeypatch.setattr(config, "state_dir", lambda: tmp_path)
    assert client.put("/api/agent-tiers", json={}).status_code == 400
    assert client.put("/api/agent-tiers",
                      json={"agent_tiers": {"qa": "ultra"}}).status_code == 400
    resp = client.put("/api/agent-tiers",
                      json={"agent_tiers": {"qa": "low", "sm": "mid"}})
    assert resp.status_code == 200
    assert agents_data.override_for("qa") == "low"


# ── install state ─────────────────────────────────────────────────────────

def test_install_state_shape():
    resp = _client().get("/api/install/state")
    assert resp.status_code == 200
    stages = resp.json()["stages"]
    assert len(stages) >= 8
    for s in stages:
        assert {"slug", "ready", "detail"} <= set(s)
        assert isinstance(s["ready"], bool)


def test_install_run_json_contract():
    client = _client()
    resp = client.post("/api/install/run", json={"component": "nope"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is False


# ── graph ─────────────────────────────────────────────────────────────────

def test_graph_stats_empty_project(monkeypatch, tmp_path):
    from pipa import config

    client = _client()
    proj = tmp_path / "proj"
    proj.mkdir()
    monkeypatch.setattr(config, "find_project", lambda *a, **k: proj)
    resp = client.get("/api/graph/stats")
    assert resp.status_code == 200
    assert resp.json()["has_graph"] is False


def test_graph_search_requires_q_and_degrades():
    client = _client()
    assert client.get("/api/graph/search").status_code == 400
    resp = client.get("/api/graph/search?q=zzz-no-such-symbol")
    assert resp.status_code == 200
    assert resp.json()["hits"] == []


def test_graph_refresh_without_cli(monkeypatch):
    import shutil as _shutil

    client = _client()
    monkeypatch.setattr(_shutil, "which", lambda *a, **k: None)
    resp = client.post("/api/graph/refresh")
    assert resp.status_code == 200
    assert resp.json()["ok"] is False


# ── docs ──────────────────────────────────────────────────────────────────

def _docs_env(monkeypatch, tmp_path):
    glob = tmp_path / "global"
    (glob / "rules").mkdir(parents=True)
    (glob / "rules" / "a.md").write_text("# A\n")
    (glob / "skills" / "s").mkdir(parents=True)
    (glob / "skills" / "s" / "SKILL.md").write_text("# S\n")
    monkeypatch.setenv("PIPA_ROOT", str(glob))
    return glob


def test_docs_list_get_put_roundtrip(monkeypatch, tmp_path):
    client = _client()
    _docs_env(monkeypatch, tmp_path)
    listing = client.get("/api/docs")
    assert listing.status_code == 200
    paths = [d["path"] for d in listing.json()]
    assert "rules/a.md" in paths
    assert "skills/s/SKILL.md" in paths

    got = client.get("/api/docs/content", params={"path": "rules/a.md"})
    assert got.status_code == 200 and got.json()["content"] == "# A\n"

    put = client.put("/api/docs/content",
                     json={"path": "rules/a.md", "content": "# A\nchanged\n"})
    assert put.status_code == 200
    assert client.get("/api/docs/content", params={"path": "rules/a.md"}).json()["content"] == "# A\nchanged\n"


def test_docs_rejects_escape_and_missing(monkeypatch, tmp_path):
    client = _client()
    _docs_env(monkeypatch, tmp_path)
    assert client.get("/api/docs/content", params={"path": "../evil.md"}).status_code in (400, 404)
    assert client.get("/api/docs/content", params={"path": "rules/nope.md"}).status_code == 404
    assert client.put("/api/docs/content",
                      json={"path": "rules/a.md"}).status_code == 400
    assert client.put("/api/docs/content",
                      json={"path": "rules/a.md", "content": "x" * (200 * 1024 + 1)}).status_code == 400


# ── new screens serve ─────────────────────────────────────────────────────

def test_new_screens_serve():
    client = _client()
    for path, marker in (
        ("/tiers", "tier-tbody"),
        ("/agents", "tier-agents-tbody"),
        ("/graphify", "graph-results"),
        ("/docs", "docs-list"),
        ("/install", "install-stages-tbody"),
    ):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert marker in resp.text, path


def test_tier_models_guard_blocks_restart_on_bad_compose(monkeypatch, tmp_path):
    import data.services as services_data
    import pages.api_models as api_module

    _models_env(monkeypatch, tmp_path)
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "model_catalog.json").write_text(json.dumps({
        "version": 1, "fetched_at": "2026-08-23T00:00:00Z",
        "providers": {"ollama": {"ok": True, "error": None,
                                 "models": [{"id": "qwen3:8b", "name": ""}]}},
    }))
    calls = []
    monkeypatch.setattr(services_data, "gateway_restart",
                        lambda: (calls.append(1), (True, "restarted"))[1])
    monkeypatch.setattr(api_module, "_verify_effective",
                        lambda: (_ for _ in ()).throw(ValueError("no model_list")))
    client = _client()
    resp = client.put("/api/tier-models", json={"tiers": {"low": {"model": "qwen3:8b"}}})
    assert resp.status_code == 500
    assert calls == [], "gateway must stay untouched on invalid compose"
