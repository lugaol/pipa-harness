"""Model registry + dynamic discovery wiring.

Pins the user-facing contract: the catalog comes from provider discovery
(state/model_catalog.json) — never a static list; tiers resolve only to
what the user assigned; opencode/dsh configs inject readable model lists.
"""
import io
import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipa import config, model_registry as mr
from pipa.runtime import render_opencode_config


def test_pretty_model_name_versions_and_sizes():
    assert mr.pretty_model_name("kimi-k2.7-code") == "Kimi K2.7 Code"
    assert mr.pretty_model_name("qwen2.5-coder:14b") == "Qwen2.5 Coder 14B"
    assert mr.pretty_model_name("step-3.7-flash") == "Step 3.7 Flash"
    assert mr.pretty_model_name("gemma-4-31b-it") == "Gemma 4 31B"


def test_pretty_model_name_free_flag():
    assert (
        mr.pretty_model_name("nemotron-3-ultra-550b-a55b:free")
        == "Nemotron 3 Ultra 550B A55B Free"
    )


def test_pretty_model_name_trailing_free_and_overrides():
    assert mr.pretty_model_name("mimo-v2.5-free") == "MiMo V2.5 Free"
    assert mr.pretty_model_name("hy3-free") == "Hy3 Free"
    assert mr.pretty_model_name("big-pickle") == "Big Pickle"
    assert mr.pretty_model_name("x-preview-f-free") == "Ox Alpha Free"


@pytest.fixture
def registry_env(monkeypatch, tmp_path):
    """Tmp state (discovery cache + assignments) so tests never touch the
    real install or the network."""
    mdir = tmp_path / "models"
    mdir.mkdir()
    (mdir / "settings.yaml").write_text("litellm_settings: {}\n")
    state = tmp_path / "state"
    state.mkdir()
    payload = {
        "version": 1,
        "fetched_at": "2026-08-23T00:00:00Z",
        "providers": {
            "ollama": {"ok": True, "error": None, "models": [
                {"id": "qwen2.5-coder:14b", "name": ""},
                {"id": "qwen2.5-coder:7b", "name": ""},
            ]},
            "opencode-zen": {"ok": True, "error": None, "models": [
                {"id": "x-preview-f-free", "name": "Ox Alpha Free"},
                {"id": "mimo-v2.5-free", "name": "MiMo V2.5 Free"},
            ]},
        },
    }
    (state / "model_catalog.json").write_text(json.dumps(payload))
    monkeypatch.setattr(config, "models_dir", lambda: mdir)
    monkeypatch.setattr(config, "state_dir", lambda: state)
    monkeypatch.setattr(config, "load_dotenv", lambda: None)  # isolate real .env
    # scrub provider keys — earlier tests / the real shell may have set them
    from pipa.providers import PROVIDERS

    for p in PROVIDERS.values():
        for k in p.requires:
            monkeypatch.delenv(k, raising=False)
    return mdir


def _fake_urlopen(payload_by_url_part):
    def fake(req, timeout=0):
        for part, body in payload_by_url_part.items():
            if part in req.full_url:
                return io.BytesIO(json.dumps(body).encode())
        raise AssertionError(f"unexpected probe {req.full_url}")
    return fake


def test_discovery_reads_openai_style_listing(monkeypatch):
    from pipa.providers import discover

    monkeypatch.setattr("pipa.providers.urlopen", _fake_urlopen({
        "opencode.ai": {"data": [
            {"id": "mimo-v2.5-free", "name": "MiMo V2.5 Free"},
            {"id": "", "name": "skipped"},
        ]},
    }))
    result = discover("opencode-zen")
    assert result["ok"] and result["models"] == [
        {"id": "mimo-v2.5-free", "name": "MiMo V2.5 Free"}
    ]


def test_discovery_error_is_soft(monkeypatch):
    from pipa.providers import discover

    def boom(req, timeout=0):
        raise OSError("no route to host")

    monkeypatch.setattr("pipa.providers.urlopen", boom)
    result = discover("opencode-zen")
    assert result["ok"] is False and result["models"] == []
    assert "no route to host" in result["error"]


def test_registry_classifies_and_names_discovered_models(registry_env):
    by_alias = {e.alias: e for e in mr.entries()}
    ox = by_alias["x-preview-f-free"]
    assert ox.display == "OpenCode - Ox Alpha Free"
    assert ox.slug == "opencode/ox-alpha-free"
    assert ox.kind == "cloud"
    assert not ox.active, "zen models must be inactive without OPENCODE_ZEN_API_KEY"
    qwen = by_alias["qwen2.5-coder:14b"]
    assert qwen.display == "Ollama - Qwen2.5 Coder 14B"
    assert qwen.active, "local provider needs no keys"


def test_normalize_tier_maps_legacy_names():
    assert mr.normalize_tier("primary") == "mid"
    assert mr.normalize_tier("fast") == "low"
    assert mr.normalize_tier("deep") == "high"
    assert mr.normalize_tier("explore") == "lowest"
    assert mr.normalize_tier("xhigh") == "xhigh"
    assert mr.normalize_tier("bogus") == ""


def test_no_auto_classification_without_user_assignments(registry_env):
    """Models are never sorted into tiers automatically: with an empty
    assignment store, no tier resolves."""
    assert mr.tier_assignments() == {}
    assert mr.tier_resolution() == {}
    assert mr.entries(), "catalog must still list discovered models"


def test_set_tier_assignment_roundtrip_recomposes_gateway(registry_env):
    # assign an ACTIVE (keyless-local) model -> tier becomes routable
    ok, _ = mr.set_tier_assignment("mid", "qwen2.5-coder:14b")
    assert ok
    assert mr.tier_assignments() == {"mid": "qwen2.5-coder:14b"}

    composed = (registry_env / ".effective.yaml").read_text()
    assert "model_name: mid" in composed, "assignment must be projected into gateway"

    resolved = mr.tier_resolution()
    assert resolved["mid"].alias == "qwen2.5-coder:14b"
    assert resolved["mid"].active

    # an INACTIVE model can still be chosen — it just cannot route yet
    ok2, _ = mr.set_tier_assignment("high", "mimo-v2.5-free")
    assert ok2
    assert "model_name: high" not in (registry_env / ".effective.yaml").read_text()
    assert not mr.tier_resolution()["high"].active

    ok3, _ = mr.set_tier_assignment("mid", "")
    assert ok3
    assert "model_name: mid" not in (registry_env / ".effective.yaml").read_text()


def test_set_tier_assignment_rejects_unknown_inputs(registry_env):
    ok, _ = mr.set_tier_assignment("ultra", "mimo-v2.5-free")
    assert not ok
    ok2, _ = mr.set_tier_assignment("mid", "not-discovered-anywhere")
    assert not ok2
    assert mr.tier_assignments() == {}


def test_runtime_model_list_ordered_and_named(registry_env):
    ok, _ = mr.set_tier_assignment("mid", "qwen2.5-coder:14b")
    assert ok
    rows = mr.runtime_model_list()
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate picker ids"
    assigned = [t for t in mr.TIER_ALIASES if t in mr.tier_resolution()]
    assert assigned and ids[: len(assigned)] == assigned, \
        "assigned tiers must come first"
    for r in rows:
        assert r["name"] and " - " in r["name"], r


def test_runtime_model_list_excludes_inactive_models(registry_env):
    active_aliases = {e.alias for e in mr.entries(active_only=True)}
    rows = mr.runtime_model_list()
    inactive = {e.alias for e in mr.entries()} - active_aliases
    assert inactive, "seeded cache must include a keyless provider"
    ids = {r["id"] for r in rows}
    leaked = inactive & ids
    assert not leaked, f"inactive models leaked into picker: {sorted(leaked)}"


def test_composer_emits_descriptive_aliases(registry_env):
    path, warn = config.compose_litellm_config()
    data = yaml.safe_load(path.read_text())
    names = {m["model_name"] for m in data["model_list"]}
    assert any("/" in n and n not in mr.TIER_ALIASES for n in names), (
        f"no descriptive aliases composed: {sorted(names)[:5]}"
    )


def test_opencode_config_models_have_display_names(registry_env):
    cfg = render_opencode_config(config.harness_root())
    models = cfg["provider"]["litellm"]["models"]
    assert models
    for mid, meta in models.items():
        assert meta.get("name"), mid


def test_opencode_default_models_follow_user_assignments(registry_env):
    """No assignment -> template defaults untouched; assignments win after."""
    root = config.harness_root()
    cfg = render_opencode_config(root)
    assert cfg["model"] == "litellm/mid"  # static template default

    ok, _ = mr.set_tier_assignment("mid", "qwen2.5-coder:14b")
    assert ok
    cfg2 = render_opencode_config(root)
    assert cfg2["model"] == "litellm/mid"
    assert cfg2["small_model"] == "litellm/mid"  # only tier assigned so far
    assert cfg2["provider"]["litellm"]["models"]["mid"]["name"]


def test_dsh_models_render_with_names(registry_env):
    from pipa.runtime import _render_dsh_models

    root = config.harness_root()
    raw = (root / "clis" / "deepseek-harness" / "cordis.patch.yml").read_text()
    out = _render_dsh_models(raw.replace("@LITELLM_URL@", config.LITELLM_URL), root)
    data = yaml.safe_load(out)
    models = None
    for entry in data:
        provs = (entry.get("config") or {}).get("providers")
        if provs and "litellm" in provs:
            models = provs["litellm"]["models"]
    assert models and len(models) >= 4
    for m in models:
        assert m.get("name"), m.get("id")


def test_seed_default_tiers_fills_every_tier_when_unset(registry_env):
    """First-run: all five tiers get working defaults from discovery."""
    assert mr.tier_assignments() == {}
    seeded = mr.seed_default_tiers()
    assert set(seeded) == {"lowest", "low", "mid", "high", "xhigh"}
    # every seeded target must be a real discovered model
    known = {e.alias for e in mr.entries()}
    assert all(alias in known for alias in seeded.values())
    # persisted exactly as configured
    assert mr.tier_assignments() == seeded
    # user owns the store afterwards — seeding never fires again
    assert mr.seed_default_tiers() == {}


def test_seed_default_tiers_skips_when_user_assigned_anything(registry_env):
    ok, _ = mr.set_tier_assignment("mid", "qwen2.5-coder:14b")
    assert ok
    assert mr.seed_default_tiers() == {}
    assert mr.tier_assignments() == {"mid": "qwen2.5-coder:14b"}


def test_dashboard_models_page_renders_discovered_catalog(registry_env):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from dashboard.server import app

    client = TestClient(app)
    resp = client.get("/models")
    assert resp.status_code == 200
    text = resp.text
    assert "Tier configuration" in text
    assert "Ollama - Qwen2.5 Coder 14B" in text, "pretty names must appear"
