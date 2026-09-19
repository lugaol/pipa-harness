"""Round-2 refactor: memory plugin, verify stage, freshness, orchestrator."""
import sys
from pathlib import Path
from types import SimpleNamespace

HARNESS_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = HARNESS_ROOT / "dashboard"

for _p in (str(HARNESS_ROOT), str(DASHBOARD_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def test_memory_plugin_renders_with_bin():
    from pipa.runtime import _render_memory_plugin

    src = _render_memory_plugin(HARNESS_ROOT)
    assert "@@PIPA_BIN@@" not in src
    assert "pipa recall" in src and "--digest" in src
    assert "MEMORY_CONTEXT_DISABLED" in src


def test_memory_plugin_wired_create_only(tmp_path, monkeypatch):
    import json

    import pipa.runtime as runtime

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(runtime.Path, "home", classmethod(lambda cls: home))
    gdir = home / ".config" / "opencode"
    (gdir / "plugin").mkdir(parents=True)
    (gdir / "opencode.jsonc").write_text("{}")
    (gdir / "agent").mkdir()
    actions = runtime.wire_opencode(tmp_path, HARNESS_ROOT)
    mem = gdir / "plugin" / "pipa-memory-context.js"
    assert mem.is_file()
    assert "@@PIPA_BIN@@" not in mem.read_text()
    assert any("pipa-memory-context.js" in a for a in actions)
    # second run keeps the user's file
    mem.write_text("// user edit")
    actions2 = runtime.wire_opencode(tmp_path, HARNESS_ROOT)
    assert mem.read_text() == "// user edit"
    assert any("kept existing" in a and "memory-context" in a for a in actions2)


def test_install_verify_component_present():
    from pipa.commands.install import INSTALL_COMPONENTS

    assert "verify" in INSTALL_COMPONENTS


def test_install_state_includes_verify():
    from fastapi.testclient import TestClient

    import server

    client = TestClient(server.app, raise_server_exceptions=False)
    slugs = [s["slug"] for s in client.get("/api/install/state").json()["stages"]]
    assert "verify" in slugs


def test_freshness_note_silent_offline(monkeypatch):
    import pipa.commands.lifecycle as lifecycle

    monkeypatch.setattr(lifecycle, "_git", lambda args, timeout=10: (False, ""))
    assert lifecycle.freshness_note() is None


def test_freshness_note_flags_ahead(monkeypatch):
    import pipa.commands.lifecycle as lifecycle

    def fake_git(args, timeout=10):
        if args[:2] == ["rev-parse", "HEAD"]:
            return True, "aaa"
        return True, "bbb HEAD"

    monkeypatch.setattr(lifecycle, "_git", fake_git)
    note = lifecycle.freshness_note()
    assert note and "pipa update" in note


def test_orchestrator_default_in_sync():
    from pipa.model_registry import agent_tier_defaults
    from pipa.runtime import AGENT_MODEL_MAP

    assert AGENT_MODEL_MAP["orchestrator"] == "xhigh"
    assert agent_tier_defaults()["orchestrator"] == "xhigh"


def test_version_and_update_commands(capsys):
    import pipa.commands.lifecycle as lifecycle

    assert lifecycle.cmd_version(SimpleNamespace()) == 0
    assert "pipa " in capsys.readouterr().out
