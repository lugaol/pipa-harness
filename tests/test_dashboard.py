"""Tests for the modular dashboard/ architecture.

Covers: every page module exposes a non-empty router; data readers fail
soft (unreachable gateway, missing registry); templates exist; no
hardcoded user paths anywhere under dashboard/.
"""
import json
import sys
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi", reason="dashboard tests need fastapi")

HARNESS_ROOT = Path(__file__).resolve().parents[1]
ROOT_DASH = HARNESS_ROOT / "dashboard"
DASHBOARD_DIR = HARNESS_ROOT / "dashboard"

# Same bootstrap as dashboard/server.py: repo root for `pipa`, dashboard
# dir for the flat `pages` / `data` packages.
for _p in (str(HARNESS_ROOT), str(DASHBOARD_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PAGES = [
    "overview", "sessions", "spend", "models",
    "agents", "projects", "memory", "evals", "context", "graph",
]


@pytest.mark.parametrize("name", PAGES)
def test_page_module_exposes_router_with_routes(name):
    import importlib

    module = importlib.import_module(f"pages.{name}")
    assert hasattr(module, "router"), f"pages/{name}.py must expose `router`"
    assert len(module.router.routes) > 0, f"pages/{name}.py router has no routes"


def test_gateway_list_models_unreachable_returns_empty(monkeypatch):
    from pipa import config
    from data import gateway

    monkeypatch.setattr(config, "LITELLM_URL", "http://127.0.0.1:1")
    assert gateway.list_models() == []
    assert gateway.health() is False


def test_projects_reader_tolerates_missing_registry(monkeypatch, tmp_path):
    from pipa import config
    from data import projects

    monkeypatch.setattr(
        config, "projects_registry_path", lambda: tmp_path / "missing.json"
    )
    assert projects.list_projects() == []


def test_agents_reader_tolerates_missing_overrides(monkeypatch, tmp_path):
    from pipa import config
    from data import agents

    monkeypatch.setattr(config, "state_dir", lambda: tmp_path)
    assert agents.load_overrides() == {}
    assert agents.overrides_path() == tmp_path / "agent_llm_overrides.json"

    agents.set_tier_override("qa", "low")
    assert agents.override_for("qa") == "low"
    agents.set_tier_override("qa", "")  # empty tier clears the override
    assert agents.load_overrides() == {}


def test_templates_and_fragments_exist():
    for name in (
        "base.html", "overview.html", "sessions.html", "session_detail.html",
        "spend.html", "models.html", "agents.html", "projects.html",
        "evals.html", "context.html", "context_edit.html",
        "_entry_table.html",
    ):
        assert (DASHBOARD_DIR / "templates" / name).is_file(), name
    for name in ("stat_card.html", "table.html",
                 "timeline.html", "empty_state.html"):
        assert (DASHBOARD_DIR / "fragments" / name).is_file(), name
    assert (DASHBOARD_DIR / "static" / "style.css").is_file()


def test_no_hardcoded_user_paths():
    offenders = []
    for pattern in ("*.py", "*.html", "*.css"):
        for f in DASHBOARD_DIR.rglob(pattern):
            if "__pycache__" in f.parts:
                continue
            if "/Users/" in f.read_text(errors="replace"):
                offenders.append(str(f))
    assert offenders == []


def test_run_evals_parses_runner_json(monkeypatch, tmp_path):
    import pages.evals as evals_page

    fake_script = tmp_path / "run.py"
    report = {
        "total": 2,
        "failed": 1,
        "results": [
            {"file": "agents/a.md", "gate": {"pass": True}},
            {"file": "agents/b.md", "gate": {"pass": False}, "extra": "ignored"},
        ],
    }
    fake_script.write_text(
        "import json\n"
        f"print(json.dumps({report!r}))\n"  # repr → valid Python literals
    )
    monkeypatch.setattr(evals_page, "EVAL_SCRIPT", fake_script)

    result = evals_page.run_evals()
    assert result["ok"] is True
    assert result["total"] == 2
    assert result["failed"] == 1
    assert [r["file"] for r in result["rows"]] == ["agents/a.md", "agents/b.md"]
    assert result["rows"][0]["ok"] is True
    assert result["rows"][1]["ok"] is False


def test_system_checks_shape():
    from data import system

    checks = system.checks()
    assert len(checks) >= 4
    names = {c["name"] for c in checks}
    assert {"litellm gateway", "ollama"} <= names
    for check in checks:
        assert isinstance(check["ok"], bool)


def _client():
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    import server

    return TestClient(server.app)


def test_app_serves_pages():
    client = _client()
    for path, marker in (
        ("/", "Overview"),
        ("/sessions", "Sessions"),
        ("/spend", "Spend"),
        ("/models", "Tier configuration"),
        ("/agents", "Agents"),
        ("/projects", "registered project"),
        ("/memory", "expiry-aware ranking"),
        ("/graph", "Code graph"),
        ("/evals", "Evals"),
    ):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert marker in resp.text, path


def test_old_extensions_url_redirects_to_projects():
    client = _client()
    resp = client.get("/extensions", follow_redirects=False)
    assert resp.status_code in (301, 302, 307)
    assert resp.headers["location"].startswith("/projects")


def test_agent_tier_post_roundtrip(monkeypatch, tmp_path):
    client = _client()
    from pipa import config

    monkeypatch.setattr(config, "state_dir", lambda: tmp_path)
    resp = client.post(
        "/api/agent-tier",
        data={"agent": "@dev", "tier": "mid"},
        follow_redirects=False,
    )
    assert resp.status_code == 303  # PRG redirect back to /agents
    assert resp.headers["location"].startswith("/agents")
    stored = json.loads((tmp_path / "agent_llm_overrides.json").read_text())
    assert stored == {"@dev": {"tier": "mid"}}


# ── context page (v2) ───────────────────────────────────────────────────────

def _ctx_env(monkeypatch, tmp_path):
    """Tmp global install ($PIPA_ROOT) + tmp active pipa project."""
    from pipa import config

    proj = tmp_path / "proj"
    (proj / ".pipa").mkdir(parents=True)
    glob = tmp_path / "global"
    glob.mkdir()
    monkeypatch.setenv("PIPA_ROOT", str(glob))
    monkeypatch.setattr(config, "find_project", lambda *a, **k: proj)
    return proj, glob


def test_context_roundtrip_create_edit_delete(monkeypatch, tmp_path):
    client = _client()
    proj, _glob = _ctx_env(monkeypatch, tmp_path)

    resp = client.post(
        "/context/save",
        data={"tier": "project", "tab": "rules", "path": "new",
              "name": "x", "content": "# X\nhello"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/context")
    assert "saved=1" in resp.headers["location"]
    target = proj / ".pipa" / "rules" / "x.md"
    assert target.read_text() == "# X\nhello"

    listing = client.get("/context?tier=project&tab=rules")
    assert listing.status_code == 200
    assert "rules/x.md" in listing.text

    edit_page = client.get("/context/edit?tier=project&tab=rules&path=rules/x.md")
    assert edit_page.status_code == 200
    assert "<textarea" in edit_page.text
    assert "# X" in edit_page.text

    resp = client.post(
        "/context/save",
        data={"tier": "project", "tab": "rules", "path": "rules/x.md",
              "content": "# X\nchanged"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert target.read_text() == "# X\nchanged"

    resp = client.post(
        "/context/delete",
        data={"tier": "project", "tab": "rules", "path": "rules/x.md"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "deleted=1" in resp.headers["location"]
    assert not target.exists()


def test_context_jail_rejects_escape_and_absolute(monkeypatch, tmp_path):
    from data import context as ctx

    proj, glob = _ctx_env(monkeypatch, tmp_path)

    ok, msg = ctx.write_entry("project", None, "rules", "../evil.md", "evil")
    assert ok is False and msg
    assert not (proj / ".pipa" / "evil.md").exists()
    assert not (glob / "evil.md").exists()

    ok2, msg2 = ctx.write_entry("project", None, "rules", "/etc/pipa-evil-test.md", "evil")
    assert ok2 is False and msg2
    assert not Path("/etc/pipa-evil-test.md").exists()

    assert ctx.read_entry("project", None, "rules", "../evil.md") is None
    ok3, _ = ctx.delete_entry("project", None, "rules", "../evil.md")
    assert ok3 is False

    # pattern mismatch: agents rel under the memory tab is rejected
    ok4, _ = ctx.write_entry("project", None, "memory", "memory/../agents/a.md", "x")
    assert ok4 is False

    # memory tier is read-only
    ok5, _ = ctx.write_entry("global", None, "memory", "vault/notes.md", "x")
    assert ok5 is False

    # oversized payloads are refused before any FS write
    big = "x" * (200 * 1024 + 1)
    ok6, _ = ctx.write_entry("project", None, "rules", "big.md", big)
    assert ok6 is False
    assert not (proj / ".pipa" / "rules" / "big.md").exists()


def test_skills_create_makes_folder_and_slug(monkeypatch, tmp_path):
    client = _client()
    proj, _glob = _ctx_env(monkeypatch, tmp_path)

    resp = client.post(
        "/context/save",
        data={"tier": "project", "tab": "skills", "path": "new",
              "name": "code-review", "content": "# code-review"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    skill_file = proj / ".pipa" / "skills" / "code-review" / "SKILL.md"
    assert skill_file.is_file()

    bad = client.post(
        "/context/save",
        data={"tier": "project", "tab": "skills", "path": "new",
              "name": "Bad Skill!", "content": "nope"},
        follow_redirects=False,
    )
    assert bad.status_code == 303
    assert "error=" in bad.headers["location"]
    assert not (proj / ".pipa" / "skills" / "Bad Skill!").exists()


def test_agents_tab_override_single_source(monkeypatch, tmp_path):
    """Overrides are managed on /agents only; the context agents tab is
    read-only and links there."""
    client = _client()
    _proj, _glob = _ctx_env(monkeypatch, tmp_path)
    state = tmp_path / "state"
    state.mkdir()
    from pipa import config

    monkeypatch.setattr(config, "state_dir", lambda: state)

    resp = client.post(
        "/api/agent-tier",
        data={"agent": "qa", "tier": "low"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/agents")
    stored = json.loads((state / "agent_llm_overrides.json").read_text())
    assert stored["qa"] == {"tier": "low"}

    # the context page no longer carries its own override endpoint
    listing = client.get("/context?tier=global&tab=agents")
    assert listing.status_code == 200
    assert "/api/context/override" not in listing.text
    assert 'href="/agents"' in listing.text


def test_agent_reset_override_helper(monkeypatch, tmp_path):
    from pipa import config
    from data import agents

    monkeypatch.setattr(config, "state_dir", lambda: tmp_path)
    agents.set_tier_override("explorer", "lowest")
    assert agents.override_for("explorer") == "lowest"
    agents.reset_override("explorer")
    assert agents.load_overrides() == {}
    assert agents.override_for("explorer") is None


def _seed_cache(state, providers):
    payload = {
        "version": 1,
        "fetched_at": "2026-08-23T00:00:00Z",
        "providers": {
            slug: {"ok": True, "error": None, "models": models}
            for slug, models in providers.items()
        },
    }
    state.mkdir(parents=True, exist_ok=True)
    (state / "model_catalog.json").write_text(json.dumps(payload))


def test_catalog_and_missing_keys_without_kilo_key(monkeypatch, tmp_path):
    from pipa import config
    from data import models as models_data

    monkeypatch.setattr(config, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(config, "load_dotenv", lambda: None)  # isolate from real .env
    monkeypatch.delenv("KILO_API_KEY", raising=False)
    _seed_cache(tmp_path, {
        "ollama": [{"id": "qwen2.5-coder:14b", "name": ""},
                   {"id": "qwen2.5-coder:7b", "name": ""}],
        "kilo": [{"id": "kilo-auto/free", "name": ""}],
    })

    cat = {c["alias"]: c for c in models_data.catalog()}
    assert cat["kilo-auto/free"]["active"] is False
    assert cat["kilo-auto/free"]["provider"] == "Kilo"
    assert cat["qwen2.5-coder:14b"]["active"] is True  # no requirement → always on

    assert models_data.missing_keys_for("kilo-auto/free") == ["KILO_API_KEY"]
    assert models_data.missing_keys_for("qwen2.5-coder:14b") == []

    keys = {k["name"]: k["present"] for k in models_data.env_keys()}
    assert keys["KILO_API_KEY"] is False
    monkeypatch.setenv("KILO_API_KEY", "dummy-not-a-real-secret")
    assert keys["KILO_API_KEY"] is False  # env_keys() re-evaluates on call


def test_tier_assignment_endpoint_roundtrip(monkeypatch, tmp_path):
    client = _client()
    state = tmp_path / "state"
    mdir = tmp_path / "models"
    mdir.mkdir(parents=True)
    (mdir / "settings.yaml").write_text("litellm_settings: {}\n")
    _seed_cache(state, {
        "ollama": [{"id": "qwen2.5-coder:14b", "name": ""}],
    })
    from pipa import config
    from pipa.model_registry import tier_assignments as read_assignments

    monkeypatch.setattr(config, "models_dir", lambda: mdir)
    monkeypatch.setattr(config, "state_dir", lambda: state)
    monkeypatch.setattr(config, "load_dotenv", lambda: None)  # isolate real .env

    resp = client.post(
        "/api/tiers",
        data={"tier": "mid", "model": "qwen2.5-coder:14b"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "saved=1" in resp.headers["location"]
    assert read_assignments() == {"mid": "qwen2.5-coder:14b"}
    # the assignment is projected into the composed gateway config
    composed = (mdir / ".effective.yaml").read_text()
    assert "model_name: mid" in composed

    # unknown tier -> flash error, nothing persisted beyond prior state
    bad = client.post(
        "/api/tiers",
        data={"tier": "ultra", "model": "qwen2.5-coder:14b"},
        follow_redirects=False,
    )
    assert bad.status_code == 303
    assert "error=1" in bad.headers["location"]
    assert read_assignments() == {"mid": "qwen2.5-coder:14b"}

    # clearing with an empty model removes the assignment
    clear = client.post(
        "/api/tiers",
        data={"tier": "mid", "model": ""},
        follow_redirects=False,
    )
    assert clear.status_code == 303
    assert read_assignments() == {}
    assert "model_name: mid" not in (mdir / ".effective.yaml").read_text()


def test_models_refresh_endpoint(monkeypatch, tmp_path):
    client = _client()
    from pipa import config
    import pages.models as models_page

    monkeypatch.setattr(config, "state_dir", lambda: tmp_path)

    calls = []

    def fake_refresh(timeout=8):
        calls.append(timeout)
        _seed_cache(tmp_path, {"ollama": [{"id": "x", "name": "X"}]})
        return {"providers": {"ollama": {"ok": True, "models": [{"id": "x"}]}}}

    monkeypatch.setattr(models_page.models_data, "refresh_models", fake_refresh)
    resp = client.post("/api/models/refresh", follow_redirects=False)
    assert resp.status_code == 303
    assert "refreshed=1" in resp.headers["location"]
    assert len(calls) == 1

    def failing_refresh(timeout=8):
        raise OSError("offline")

    monkeypatch.setattr(models_page.models_data, "refresh_models", failing_refresh)
    bad = client.post("/api/models/refresh", follow_redirects=False)
    assert "refresh-error=1" in bad.headers["location"]


def test_projects_runtime_setter_writes_marker(monkeypatch, tmp_path):
    from pipa import config
    from data import projects as projects_data

    state = tmp_path / "state"
    state.mkdir()
    proj = tmp_path / "myrepo"
    proj.mkdir()
    (state / "projects.json").write_text(
        json.dumps([{"path": str(proj), "runtime": "auto"}])
    )
    monkeypatch.setattr(config, "state_dir", lambda: state)

    ok, msg = projects_data.set_runtime(str(proj), "deepseek-harness")
    assert ok, msg
    marker = proj / ".pipa" / "runtime"
    assert marker.is_file()
    assert marker.read_text().startswith("deepseek-harness")
    registry = json.loads((state / "projects.json").read_text())
    assert registry[0]["runtime"] == "deepseek-harness"

    ok2, _ = projects_data.set_runtime(str(tmp_path / "not-registered"), "opencode")
    assert ok2 is False
    ok3, _ = projects_data.set_runtime(str(proj), "bogus-runtime")
    assert ok3 is False


def test_memory_page_serves_notes_and_recall():
    client = _client()
    resp = client.get("/memory")
    assert resp.status_code == 200
    assert "Memory" in resp.text
    assert "Recall" in resp.text
    # scope switcher present
    assert "/memory?scope=project" in resp.text


def test_memory_note_crud_roundtrip(monkeypatch, tmp_path):
    client = _client()
    glob = tmp_path / "global"
    glob.mkdir()
    from pipa import config

    monkeypatch.setenv("PIPA_ROOT", str(glob))

    resp = client.post(
        "/memory/save",
        data={"tier": "global", "path": "new",
              "name": "gateway-choice", "content": "# Gateway choice\nlitellm"},
        follow_redirects=False,
    )
    assert resp.status_code == 303, resp.headers.get("location")
    note = glob / "vault" / "notes" / "gateway-choice.md"
    assert note.is_file()

    listing = client.get("/memory?scope=global")
    assert "notes/gateway-choice.md" in listing.text
    assert "Gateway choice" in listing.text

    # expiry: extend writes a future valid_until into the frontmatter
    ok = client.post(
        "/memory/expiry",
        data={"tier": "global", "path": "notes/gateway-choice.md",
              "action": "extend"},
        follow_redirects=False,
    )
    assert ok.status_code == 303
    assert "valid_until:" in note.read_text()

    resp = client.post(
        "/memory/delete",
        data={"tier": "global", "path": "notes/gateway-choice.md"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert not note.exists()


def test_memory_jail_rejects_escape(monkeypatch, tmp_path):
    from data import memory as mem

    glob = tmp_path / "global"
    (glob / "vault").mkdir(parents=True)
    monkeypatch.setenv("PIPA_ROOT", str(glob))

    ok, _msg = mem.write_note("global", "../evil.md", "evil")
    assert ok is False
    assert not (glob / "evil.md").exists()

    ok2, _ = mem.write_note("global", "/etc/pipa-evil-mem.md", "evil")
    assert ok2 is False

    ok3, _ = mem.write_note("global", "notes/sub/../../x.md", "evil")
    assert ok3 is False


def test_mcp_toggle_flips_enabled_key(monkeypatch, tmp_path):
    import json as _json
    from pipa import config
    from data import mcp as mcp_data

    mcp_root = tmp_path / "mcp"
    server_dir = mcp_root / "context7"
    server_dir.mkdir(parents=True)
    cfg = server_dir / "config.json"
    cfg.write_text(_json.dumps(
        {"name": "context7", "enabled": True,
         "mcp": {"type": "remote", "url": "https://x"}}))
    monkeypatch.setattr(config, "mcp_dir", lambda: mcp_root)

    servers = mcp_data.list_servers()
    assert len(servers) == 1 and servers[0]["enabled"] is True

    ok, msg = mcp_data.set_enabled("context7", False)
    assert ok, msg
    assert _json.loads(cfg.read_text())["enabled"] is False

    ok2, _ = mcp_data.set_enabled("../evil", False)
    assert ok2 is False
    ok3, _ = mcp_data.set_enabled("missing-server", True)
    assert ok3 is False


def test_graph_status_and_query_degrade_without_graph(monkeypatch, tmp_path):
    from data import graph as graph_data

    root = tmp_path / "proj-root"
    root.mkdir()
    st = graph_data.status(str(root))
    assert st["has_graph"] is False
    assert st["nodes"] == 0

    result = graph_data.query("anything", str(root))
    assert result["hits"] == []
    assert result["status"]["has_graph"] is False


def test_stylesheet_is_valid_and_unpoisoned():
    """Regression: extraction once left <style> wrappers + a stray brace in
    style.css — browsers then discarded the whole token block (unstyled UI)."""
    css = (ROOT_DASH / "static" / "style.css").read_text()
    assert "<style>" not in css and "</style>" not in css
    depth = 0; in_comment = False; i = 0; went_negative = False
    while i < len(css):
        if css.startswith("/*", i):
            in_comment = True; i += 2; continue
        if in_comment:
            if css.startswith("*/", i): in_comment = False; i += 2
            else: i += 1
            continue
        if css[i] == "{": depth += 1
        elif css[i] == "}":
            depth -= 1
            if depth < 0: went_negative = True
        i += 1
    assert depth == 0 and not went_negative, "unbalanced braces in style.css"
    assert ":root" in css and "--accent-primary" in css, "design tokens missing"
