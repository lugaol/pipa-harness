"""pipa doctor (Phase 3 of the ia_harness port): tier-system diagnostics."""
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

HARNESS_ROOT = Path(__file__).resolve().parents[1]

for _p in (str(HARNESS_ROOT),):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _env(monkeypatch, tmp_path):
    """Isolated models dir (real tiers.yaml) + empty state dir."""
    from pipa import config

    mdir = tmp_path / "models"
    mdir.mkdir()
    shutil.copy(HARNESS_ROOT / "models" / "tiers.yaml", mdir / "tiers.yaml")
    (mdir / "providers.yaml").write_text(
        "providers:\n"
        "  - slug: ollama\n"
        "    label: Ollama\n"
        "    kind: local\n"
        "    requires: []\n"
        "    list_url: http://localhost:11434/v1/models\n"
        "    needs_key_for_list: false\n"
        "    litellm:\n"
        "      model: 'openai/{id}'\n"
        "      api_base: http://localhost:11434/v1\n"
        "      api_key: ollama\n"
    )
    (mdir / "settings.yaml").write_text("litellm_settings: {}\n")
    state = tmp_path / "state"
    state.mkdir()
    # Point the provider registry at one local provider (no module reload —
    # reloading would leak tmp state into unrelated tests).
    import pipa.providers as providers

    ollama = providers.Provider(
        slug="ollama", label="Ollama", kind="local", requires=(),
        list_url="http://localhost:11434/v1/models",
        needs_key_for_list=False,
        litellm_params=lambda mid: {
            "model": f"openai/{mid}",
            "api_base": "http://localhost:11434/v1",
            "api_key": "ollama",
        },
    )
    monkeypatch.setattr(providers, "PROVIDERS", {"ollama": ollama})
    monkeypatch.setattr(config, "models_dir", lambda: mdir)
    monkeypatch.setattr(config, "state_dir", lambda: state)
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    monkeypatch.setattr(config, "LITELLM_URL", "http://127.0.0.1:1")
    monkeypatch.setattr(config, "OLLAMA_URL", "http://127.0.0.1:1")
    return mdir, state


def _seed_catalog(state, models):
    (state / "model_catalog.json").write_text(json.dumps({
        "version": 1,
        "fetched_at": "2026-01-01T00:00:00Z",
        "providers": {"ollama": {"ok": True, "error": None, "models": models}},
    }))


def test_doctor_clean_setup_passes(monkeypatch, tmp_path, capsys):
    from pipa.commands.doctor import cmd_doctor

    _mdir, state = _env(monkeypatch, tmp_path)
    _seed_catalog(state, [{"id": "qwen3:8b", "name": ""}])
    (state / "tier_assignments.json").write_text(json.dumps({"low": "qwen3:8b"}))
    # pre-generate so gateway-config is in sync
    from pipa import config

    config.compose_litellm_config()
    rc = cmd_doctor(SimpleNamespace(json=False))
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "[FAIL]" not in out


def test_doctor_fails_on_broken_tiers(monkeypatch, tmp_path, capsys):
    from pipa.commands.doctor import cmd_doctor

    mdir, _state = _env(monkeypatch, tmp_path)
    (mdir / "tiers.yaml").write_text("tiers:\n  low:\n    label: Low\n")
    rc = cmd_doctor(SimpleNamespace(json=False))
    out = capsys.readouterr().out
    assert rc == 1
    assert "tiers.yaml" in out


def test_doctor_fails_on_stale_gateway_config(monkeypatch, tmp_path, capsys):
    from pipa.commands.doctor import cmd_doctor

    mdir, state = _env(monkeypatch, tmp_path)
    _seed_catalog(state, [{"id": "qwen3:8b", "name": ""}])
    (state / "tier_assignments.json").write_text(json.dumps({"low": "qwen3:8b"}))
    (mdir / ".effective.yaml").write_text("# stale placeholder\n")
    rc = cmd_doctor(SimpleNamespace(json=False))
    out = capsys.readouterr().out
    assert rc == 1
    assert "stale" in out


def test_doctor_json_shape(monkeypatch, tmp_path, capsys):
    from pipa.commands.doctor import cmd_doctor

    _mdir, _state = _env(monkeypatch, tmp_path)
    rc = cmd_doctor(SimpleNamespace(json=True))
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0  # warnings only on a fresh box
    assert set(payload["summary"]) == {"pass", "warn", "fail"}
    assert all(set(c) == {"name", "status", "detail"} for c in payload["checks"])


def test_tier_policy_loader(monkeypatch, tmp_path):
    from pipa import config
    from pipa.model_registry import agent_tier_defaults, tier_policy

    _mdir, _state = _env(monkeypatch, tmp_path)
    policy = tier_policy()
    assert set(policy) == {"lowest", "low", "mid", "high", "xhigh"}
    assert policy["mid"]["label"] == "Mid"
    defaults = agent_tier_defaults()
    assert defaults["dev"] == "mid"
    # unknown tier names in agent_tiers are dropped, never crash
    assert all(v in policy for v in defaults.values())
