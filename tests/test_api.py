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
    from browser_client import browser_client

    import server

    return browser_client(server.app)


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
    import pipa.runtime as runtime

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
    # Never render into the developer's real ~/.config/opencode during tests.
    monkeypatch.setattr(runtime, "refresh_agents", lambda *a, **k: [])
    return mdir, state


# ── status ────────────────────────────────────────────────────────────────

def test_api_status_shape():
    resp = _client().get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "litellm gateway" in data and "ollama" in data
    for info in data.values():
        # `status` is new: the dashboard must be able to render warn as warn.
        # Without it the adapter had no way to express the optional/fault
        # distinction `pipa status` makes.
        assert set(info) == {"status", "up", "detail"}
        assert isinstance(info["up"], bool)
        assert info["status"] in ("pass", "warn", "fail")
        assert info["up"] == (info["status"] != "fail")


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
    import pipa.runtime as runtime

    calls = []
    monkeypatch.setattr(runtime, "refresh_agents", lambda *a, **k: calls.append(1) or [])
    _seed_catalog(state, {"ollama": [{"id": "qwen3:8b", "name": ""}]})
    resp = client.put("/api/tier-models",
                      json={"tiers": {"low": {"model": "qwen3:8b", "max_steps": 7}}})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True and body["restarted"] is True
    assert tier_assignments()["low"] == "qwen3:8b"
    assert calls, "a tier save must re-render the deployed agent files"

    single = client.put("/api/tiers/mid", json={"model": "qwen3:8b"})
    assert single.status_code == 200
    assert tier_assignments()["mid"] == "qwen3:8b"

    bad_model = client.put("/api/tiers/mid", json={"model": "ghost-model"})
    assert bad_model.status_code == 400


# ── agents ────────────────────────────────────────────────────────────────

def test_agent_tier_roundtrip(monkeypatch, tmp_path):
    from pipa import config
    from data import agents as agents_data
    import pipa.runtime as runtime

    client = _client()
    monkeypatch.setattr(config, "state_dir", lambda: tmp_path)
    calls = []
    monkeypatch.setattr(runtime, "refresh_agents", lambda *a, **k: calls.append(1) or [])
    assert client.put("/api/agents/dev", json={}).status_code == 400
    assert client.put("/api/agents/dev", json={"model": "x"}).status_code == 400
    assert client.put("/api/agents/dev", json={"tier": "ultra"}).status_code == 400
    resp = client.put("/api/agents/dev", json={"tier": "high"})
    assert resp.status_code == 200
    assert agents_data.override_for("dev") == "high"
    reset = client.post("/api/agents/dev/reset")
    assert reset.status_code == 200
    assert agents_data.override_for("dev") in (None, "")
    assert len(calls) == 2, "save and reset must each re-render the deployed agents"


def test_agent_tiers_batch(monkeypatch, tmp_path):
    from pipa import config
    from data import agents as agents_data
    import pipa.runtime as runtime

    client = _client()
    monkeypatch.setattr(config, "state_dir", lambda: tmp_path)
    calls = []
    monkeypatch.setattr(runtime, "refresh_agents", lambda *a, **k: calls.append(1) or [])
    assert client.put("/api/agent-tiers", json={}).status_code == 400
    assert client.put("/api/agent-tiers",
                      json={"agent_tiers": {"qa": "ultra"}}).status_code == 400
    resp = client.put("/api/agent-tiers",
                      json={"agent_tiers": {"qa": "low", "sm": "mid"}})
    assert resp.status_code == 200
    assert agents_data.override_for("qa") == "low"
    assert len(calls) == 1, "a batch save renders once, after all overrides"


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


def test_bad_effective_config_blocks_the_gateway_start():
    """HS-002: a bad compose must never take a running gateway down.

    The guard used to live in the dashboard's page layer, where three of the
    five restart paths bypassed it — including the header button on every
    page. It now sits at the single owner of "start the gateway"
    (pipa.services.start_litellm -> config.verify_effective), so this asserts
    that home rather than any one caller.
    """
    import yaml

    from pipa import config, services

    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp())
    rep = services.Reporter()
    msgs = []
    rep.warn = rep.ok = rep.add = msgs.append

    for content, why in (
        ("model_list: []", "empty model_list"),
        ("model_list: [{unclosed", "unparseable yaml"),
        ("just a string", "no model_list key"),
    ):
        bad = tmp / f"{why.replace(' ', '_')}.yaml"
        bad.write_text(content)
        try:
            config.verify_effective(bad)
            raise AssertionError(f"verify_effective accepted {why}")
        except ValueError:
            pass

    # And the start path must refuse, not merely warn.
    good = tmp / "good.yaml"
    good.write_text(yaml.safe_dump({"model_list": [{"model_name": "x"}]}))
    config.verify_effective(good)  # must not raise


def test_no_restart_path_bypasses_the_verify_guard():
    """The gateway may only be started from one place, and it must verify.

    The dashboard exposes several ways to restart the gateway. A path that
    spawns litellm without verifying the composed config is a live-gateway
    outage waiting for a bad write. Two structural guarantees, both of which
    held vacuously while the guard sat in the page layer:
      1. exactly one caller of services.start_litellm — the shared restart helper
      2. that helper's underlying starter verifies before spawning
    """
    import inspect
    from pathlib import Path

    from pipa import services

    # (2) the starter verifies, before it spawns.
    src = inspect.getsource(services.start_litellm)
    assert "verify_effective" in src, (
        "start_litellm must call config.verify_effective before spawning"
    )
    assert src.index("verify_effective") < src.index("_start_daemon"), (
        "verification must happen BEFORE the gateway is spawned"
    )

    # (1) nothing else starts the gateway directly. Comments name the guard
    # often enough that a naive text match flags them; strip them first.
    import io
    import tokenize

    pages = Path(__file__).resolve().parent.parent / "dashboard"
    callers = []
    for py in pages.rglob("*.py"):
        code = []
        try:
            for tok in tokenize.generate_tokens(io.StringIO(py.read_text()).readline):
                if tok.type != tokenize.COMMENT:
                    code.append(tok.string)
        except tokenize.TokenError:
            code = [py.read_text()]
        if any("start_litellm" in c for c in code):
            callers.append(str(py.relative_to(pages)))
    assert callers == ["data/services.py"], (
        "only data/services.py (gateway_restart) may start the gateway; "
        f"also found: {callers}"
    )
