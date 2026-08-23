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
DASHBOARD_DIR = HARNESS_ROOT / "dashboard"

# Same bootstrap as dashboard/server.py: repo root for `pipa`, dashboard
# dir for the flat `pages` / `data` packages.
for _p in (str(HARNESS_ROOT), str(DASHBOARD_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PAGES = [
    "overview", "sessions", "spend", "models",
    "agents", "extensions", "memory", "evals",
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

    agents.set_override("qa", "fast")
    assert agents.override_for("qa") == "fast"
    agents.set_override("qa", "")  # empty model clears the override
    assert agents.load_overrides() == {}


def test_templates_and_fragments_exist():
    for name in (
        "base.html", "overview.html", "sessions.html", "session_detail.html",
        "spend.html", "models.html", "agents.html", "extensions.html",
        "memory.html", "evals.html",
    ):
        assert (DASHBOARD_DIR / "templates" / name).is_file(), name
    for name in ("nav.html", "stat_card.html", "table.html",
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
        ("/models", "Agent overrides"),
        ("/agents", "Agents"),
        ("/extensions", "Projects"),
        ("/memory", "Memory recall"),
        ("/evals", "Evals"),
    ):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert marker in resp.text, path


def test_override_post_roundtrip(monkeypatch, tmp_path):
    client = _client()
    from pipa import config

    monkeypatch.setattr(config, "state_dir", lambda: tmp_path)
    resp = client.post(
        "/api/overrides",
        data={"agent": "@dev", "model": "primary"},
        follow_redirects=False,
    )
    assert resp.status_code == 303  # PRG redirect back to /models
    assert resp.headers["location"] == "/models"
    stored = json.loads((tmp_path / "agent_llm_overrides.json").read_text())
    assert stored == {"@dev": {"model": "primary"}}
