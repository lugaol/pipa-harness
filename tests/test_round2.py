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
    from browser_client import browser_client

    import server

    client = browser_client(server.app)
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


def test_agent_tier_defaults_have_a_single_owner():
    """models/tiers.yaml is the only place an agent's default tier is written.

    This replaces an older test that compared runtime.AGENT_MODEL_MAP against
    tiers.yaml and failed on drift — a test that only existed because the fact
    was written twice. With one owner there is nothing to drift, so the
    assertion is now that the owner is readable, complete, and routable.
    """
    from pipa.model_registry import TIER_ALIASES, undeclared_agent_tiers
    from pipa.runtime import agent_tiers

    declared = agent_tiers()
    assert declared, "tiers.yaml must declare agent defaults"
    assert not undeclared_agent_tiers(), (
        "every agent_tiers row must name a tier the gateway can route"
    )
    for agent, tier in declared.items():
        assert tier in TIER_ALIASES, f"{agent} -> {tier!r}"


def test_agent_frontmatter_pins_a_tier_not_a_model_id():
    """agents/*.md must reference a tier alias, never a concrete model id.

    A hardcoded id is a future HTTP 400, and it silently defeated every tier
    reassignment: the dashboard moved tiers, the gateway followed, and the
    agents kept running the id written in their frontmatter.
    """
    import re
    from pathlib import Path

    from pipa.model_registry import TIER_ALIASES
    from pipa.runtime import agent_tiers

    agents_dir = Path(__file__).resolve().parent.parent / "agents"
    declared = agent_tiers()
    checked = 0
    for md in sorted(agents_dir.glob("*.md")):
        text = md.read_text()
        m = re.search(r"(?m)^model:\s*(\S+)", text)
        if not m:
            continue
        checked += 1
        bare = m.group(1).split("/", 1)[-1]
        assert bare in TIER_ALIASES, (
            f"{md.name} pins model {m.group(1)!r}; expected litellm/<tier>"
        )
        if md.stem in declared:
            assert bare == declared[md.stem], (
                f"{md.name} declares tier {bare!r} but tiers.yaml says "
                f"{declared[md.stem]!r}"
            )
    assert checked, "expected agents/*.md to declare a model"


def test_version_and_update_commands(capsys):
    import pipa.commands.lifecycle as lifecycle

    assert lifecycle.cmd_version(SimpleNamespace()) == 0
    assert "pipa " in capsys.readouterr().out
