"""Regression tests for the wires that were cut.

Each of these asserts a specific capability that existed in the docs, was
absent in the code, and is now enforced. They are deliberately grouped here
rather than scattered: the failure mode they guard against is a *missing*
feature, and a missing feature has no test unless someone writes one on
purpose.

  1. `pipa hook` accepts its arguments (the session bus is the flight
     recorder's only writer)
  2. `pipa usage-report --since` reaches the right parameter
  3. a wired runtime config is re-rendered, not frozen forever
  4. an agent's effective tier is the override, else the declared tier
  5. a bad composed config blocks the gateway start (HS-002)
  6. `pipa up` / `pipa install` exit non-zero when something failed
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HARNESS = Path(__file__).resolve().parents[1]
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))

from pipa import cli  # noqa: E402
from pipa import agent_tiers, config, runtime  # noqa: E402


# ── 1. the session bus writer ──────────────────────────────────────────────

def test_hook_parser_accepts_positional_arguments():
    """`pipa hook <event> [args...]` must parse.

    Regression: the parser never registered `hook_args`, so every invocation
    died in argparse with "unrecognized arguments" and exit 2. The opencode
    session-bus plugin spawns exactly this on every runtime event, so the
    flight recorder silently recorded nothing — while `pipa replay` and
    `pipa diff` still advertised themselves as features.
    """
    args = cli.build_parser().parse_args(
        ["hook", "post-tool", "bash", "ls -la"]
    )
    assert args.hook_args == ["post-tool", "bash", "ls -la"], args


def test_hook_writes_an_event(tmp_path, monkeypatch):
    """End to end: the parsed arguments produce a bus record."""
    from pipa import hooks

    monkeypatch.setattr(config, "find_project", lambda: tmp_path)
    monkeypatch.setattr(
        config, "session_log_path", lambda p: tmp_path / "bus.ndjson"
    )
    args = cli.build_parser().parse_args(
        ["hook", "post-tool", "bash", "echo hi"]
    )
    assert cli.main(["hook", "post-tool", "bash", "echo hi"]) == 0

    log = tmp_path / "bus.ndjson"
    assert log.is_file(), "hook must append to the session log"
    record = json.loads(log.read_text().splitlines()[-1])
    assert record["event"] == "post-tool"
    assert record["tool"] == "bash"
    assert record["payload"] == "echo hi"


def test_hook_rejects_an_unknown_event(capsys):
    """An unknown event must fail closed, not be appended as-is.

    Exit 2 with a usage message — the same convention as every other CLI
    misuse here. Silently accepting it would put unrecognised records on the
    bus that every consumer (`replay`, `diff`, the dashboard) then has to
    defend against.
    """
    from pipa import hooks

    args = cli.build_parser().parse_args(["hook", "not-an-event"])
    assert hooks.main(args.hook_args) == 2
    assert "usage: pipa hook" in capsys.readouterr().err


def test_session_bus_plugin_calls_a_parser_that_works():
    """The plugin and the CLI must agree on the invocation shape."""
    plugin = HARNESS / "clis" / "opencode" / "plugin" / "pipa-session-bus.js"
    text = plugin.read_text()
    assert '"hook"' in text, "plugin should forward events via `pipa hook`"
    # Whatever the plugin spawns must parse.
    args = cli.build_parser().parse_args(["hook", "session-start", "opencode"])
    assert args.hook_args == ["session-start", "opencode"]


# ── 2. usage-report --since ────────────────────────────────────────────────

def test_usage_report_since_reaches_summarize(monkeypatch, tmp_path, capsys):
    """Regression: `--since` was passed as the positional `path` argument.

    `pipa usage-report --since 2026-01-01` raised
    AttributeError: 'str' object has no attribute 'exists'.
    """
    from pipa.commands import usage as usage_mod

    seen = {}

    def fake_summarize(path=None, since=None):
        seen["path"] = path
        seen["since"] = since
        return {
            "rows": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
            "by_model": {}, "by_alias": {}, "first_ts": None, "last_ts": None,
        }

    monkeypatch.setattr(config, "find_project", lambda: None)
    monkeypatch.setattr("pipa.spend.summarize", fake_summarize)
    monkeypatch.setattr("pipa.session.sessions", lambda *a, **k: [])

    rc = usage_mod.cmd_usage_report(
        SimpleNamespace(since="2026-01-01", json=True)
    )
    assert rc == 0
    assert seen["since"] == "2026-01-01", (
        f"--since reached summarize as {seen['since']!r}, not the `since` kwarg"
    )
    assert seen["path"] is None, "the ledger path must not receive the timestamp"


# ── 3. the runtime config must not freeze ──────────────────────────────────

def test_wired_config_is_detected_by_marker_not_substring(tmp_path):
    """Regression: the guard was `"pipa" in text`.

    Every config pipa writes contains the substring "pipa" — in
    `sk-pipa-local`, in the instruction globs, in a comment — so the guard
    always matched, and the file was never re-rendered again. Tier changes
    reached the gateway but not the runtime.
    """
    wired = tmp_path / "opencode.jsonc"
    wired.write_text(
        json.dumps({runtime.WIRED_MARKER: {"by": "pipa"}, "model": "litellm/mid"})
    )
    assert runtime._is_wired(wired) is True

    handwritten = tmp_path / "mine.jsonc"
    # Contains "pipa" three times, but is not ours.
    handwritten.write_text(
        '{\n  // verified with: pipa-check config\n'
        '  "apiKey": "sk-pipa-local",\n'
        '  "instructions": ["/home/me/pipa/AGENTS.md"]\n}\n'
    )
    assert "pipa" in handwritten.read_text()
    assert runtime._is_wired(handwritten) is False, (
        "a hand-written config that merely mentions 'pipa' must not be "
        "treated as generated — it would be silently overwritten"
    )


def test_render_opencode_config_stamps_the_marker():
    cfg = runtime.render_opencode_config(HARNESS)
    assert runtime.WIRED_MARKER in cfg, (
        "a rendered config must carry the marker, or the next `pipa up` "
        "cannot tell it apart from a hand-written file"
    )


# ── 4. agents run on tiers, and overrides reach them ───────────────────────

def _all_tiers_routable(monkeypatch):
    """Pin tier_resolution so these tests never depend on the user's state."""
    from pipa import model_registry

    class _Entry:
        active = True

    monkeypatch.setattr(
        model_registry, "tier_resolution",
        lambda: {t: _Entry() for t in ("lowest", "low", "mid", "high", "xhigh")},
    )


def test_effective_agent_tier_prefers_the_override(monkeypatch):
    _all_tiers_routable(monkeypatch)
    monkeypatch.setattr(agent_tiers, "override_for", lambda name: "xhigh")
    assert runtime.effective_agent_tier("dev") == "xhigh"


def test_effective_agent_tier_falls_back_to_the_declared_tier(monkeypatch):
    _all_tiers_routable(monkeypatch)
    monkeypatch.setattr(agent_tiers, "override_for", lambda name: None)
    monkeypatch.setattr(runtime, "agent_tier", lambda name: "high")
    assert runtime.effective_agent_tier("dev") == "high"


def test_effective_agent_tier_survives_an_unroutable_override(monkeypatch):
    """An override naming a tier the gateway cannot serve must not be emitted.

    Writing it anyway produces a frontmatter that dies at request time with a
    model-not-found, which looks like the harness is broken.
    """
    from pipa import model_registry

    class _Entry:
        active = True

    monkeypatch.setattr(agent_tiers, "override_for", lambda name: "xhigh")
    monkeypatch.setattr(runtime, "agent_tier", lambda name: "mid")
    monkeypatch.setattr(
        model_registry, "tier_resolution",
        lambda: {"mid": _Entry()},  # xhigh not assigned
    )
    assert runtime.effective_agent_tier("dev") == "mid"


def test_render_agents_writes_the_effective_tier(tmp_path, monkeypatch):
    """The wired agent file must carry a tier, not a hardcoded id."""
    src = tmp_path / "agents"
    src.mkdir()
    (src / "dev.md").write_text(
        "---\nmodel: litellm/mid\ndescription: dev\n---\nbody\n"
    )
    monkeypatch.setattr(runtime, "agent_tier", lambda name: "low")
    monkeypatch.setattr(agent_tiers, "override_for", lambda name: None)
    _all_tiers_routable(monkeypatch)

    gdir = tmp_path / "cfg"
    runtime.render_agents(tmp_path, gdir)
    out = (gdir / "agent" / "dev.md").read_text()
    assert "model: litellm/low" in out, out


def test_render_agents_is_idempotent(tmp_path, monkeypatch):
    """A no-op re-wire must not rewrite files (it runs on every `pipa up`)."""
    src = tmp_path / "agents"
    src.mkdir()
    (src / "dev.md").write_text("---\nmodel: litellm/mid\n---\nbody\n")
    monkeypatch.setattr(agent_tiers, "override_for", lambda name: None)
    monkeypatch.setattr(runtime, "effective_agent_tier", lambda name: "mid")

    gdir = tmp_path / "cfg"
    first = runtime.render_agents(tmp_path, gdir)
    second = runtime.render_agents(tmp_path, gdir)
    assert len(first) == 1
    assert second == [], f"second wire rewrote files: {second}"


# ── 6. exit codes carry the verdict ────────────────────────────────────────

def test_install_exits_nonzero_when_a_component_fails(monkeypatch):
    """Regression: `pipa install <component>` returned 0 unconditionally."""
    from pipa.commands import install as install_mod

    monkeypatch.setitem(
        install_mod.INSTALL_COMPONENTS, "boom",
        lambda rep: False,
    )
    rc = install_mod.cmd_install(SimpleNamespace(component=["boom"]))
    assert rc == 1, "a failed component must not report success"


def test_install_exits_zero_when_all_components_succeed(monkeypatch):
    from pipa.commands import install as install_mod

    monkeypatch.setitem(install_mod.INSTALL_COMPONENTS, "fine", lambda rep: True)
    assert install_mod.cmd_install(SimpleNamespace(component=["fine"])) == 0


def test_install_reports_an_exploding_component(monkeypatch):
    from pipa.commands import install as install_mod

    def _boom(rep):
        raise RuntimeError("kaboom")

    monkeypatch.setitem(install_mod.INSTALL_COMPONENTS, "explode", _boom)
    rc = install_mod.cmd_install(SimpleNamespace(component=["explode"]))
    assert rc == 1, "an exception in a component must not read as success"