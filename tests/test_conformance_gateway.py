"""Gateway conformance: dynamic model discovery + composition.

There are no static model fragments. The gateway config is COMPOSED from
the provider discovery cache (state/model_catalog.json) + models/settings.yaml.
These tests pin that contract.
"""
from pathlib import Path

import pytest
import yaml

from pipa import config

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"


def _seed_cache(state: Path, providers: dict) -> None:
    import json

    state.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "fetched_at": "2026-08-23T00:00:00Z",
        "providers": {
            slug: {"ok": True, "error": None, "models": models}
            for slug, models in providers.items()
        },
    }
    (state / "model_catalog.json").write_text(json.dumps(payload))


@pytest.fixture
def gateway_env(monkeypatch, tmp_path):
    """Tmp state (cache + assignments) and models dir (settings only)."""
    from pipa.providers import PROVIDERS

    mdir = tmp_path / "models"
    mdir.mkdir()
    (mdir / "settings.yaml").write_text(
        "litellm_settings:\n  drop_params: true\n"
    )
    monkeypatch.setattr(config, "models_dir", lambda: mdir)
    monkeypatch.setattr(config, "state_dir", lambda: tmp_path / "state")
    monkeypatch.setattr(config, "load_dotenv", lambda: None)  # isolate real .env
    # scrub provider keys — earlier tests / the real shell may have set them
    for p in PROVIDERS.values():
        for k in p.requires:
            monkeypatch.delenv(k, raising=False)
    return mdir


def _compose(gateway_env):
    return config.compose_litellm_config()


def test_no_static_model_fragments():
    """Model lists must come from providers — nothing hardcoded on disk."""
    strays = [
        str(p) for sub in ("local", "cloud")
        for p in (MODELS / sub).glob("*.yaml")
    ] if (MODELS / "local").exists() or (MODELS / "cloud").exists() else []
    assert strays == [], f"static model fragments found: {strays}"
    assert (MODELS / "settings.yaml").exists()


def test_providers_define_wiring_not_models():
    from pipa.providers import PROVIDERS

    assert {"ollama", "openrouter", "kilo", "opencode-zen"} <= set(PROVIDERS)
    for p in PROVIDERS.values():
        assert p.list_url.startswith(("http://localhost", "https://")), p.slug
        assert p.slug == p.slug.lower(), p.slug
        params = p.litellm_params("whatever-id")
        assert params.get("model"), p.slug
        if p.kind == "cloud":
            assert p.requires, f"cloud provider {p.slug} must declare required keys"
        # free-tier policy: nothing that can cost money is ever listed
        if p.slug == "ollama":
            assert not p.keep("glm-5.1:cloud"), "ollama would list a hosted model"
        else:
            assert not p.keep("paid/model-x"), f"{p.slug} would list a paid model"


def test_free_only_filters_per_provider():
    from pipa.providers import PROVIDERS

    assert PROVIDERS["openrouter"].keep("nvidia/nemo:free")
    assert not PROVIDERS["openrouter"].keep("nvidia/nemo")          # paid
    assert PROVIDERS["opencode-zen"].keep("mimo-v2.5-free")
    assert not PROVIDERS["opencode-zen"].keep("glm-5")              # paid
    assert PROVIDERS["kilo"].keep("kilo-auto/free")
    assert PROVIDERS["kilo"].keep("stepfun/step-3.7-flash:free")
    assert not PROVIDERS["kilo"].keep("kilo-auto/frontier")         # paid
    assert PROVIDERS["ollama"].keep("qwen2.5-coder:14b")            # local = free
    assert not PROVIDERS["ollama"].keep("glm-5.1:cloud")            # hosted, paid


def test_composer_uses_discovery_cache_only(gateway_env):
    _seed_cache(gateway_env.parent / "state", {
        "ollama": [{"id": "qwen2.5-coder:14b", "name": "Qwen2.5 Coder 14B"}],
        "kilo": [{"id": "kilo-auto/free", "name": "Auto Free"}],
    })
    path, warning = _compose(gateway_env)
    text = path.read_text()
    assert "qwen2.5-coder:14b" in text, "local discovered models always route"
    assert "moonshot.cn" not in text, "undiscovered providers contribute nothing"
    assert warning and "not discovered yet" in warning
    assert ".effective.yaml" in path.name


def test_composer_skips_cloud_without_keys(monkeypatch, gateway_env):
    _seed_cache(gateway_env.parent / "state", {
        "ollama": [{"id": "qwen2.5-coder:7b", "name": ""}],
        "kilo": [{"id": "stepfun/step-3.7-flash:free", "name": "Step Flash"}],
    })
    path, warning = _compose(gateway_env)
    text = path.read_text()
    assert "qwen2.5-coder:7b" in text, "local tier survives without any keys"
    assert "stepfun/step-3.7-flash:free" not in text
    assert warning and "(needs KILO_API_KEY)" in warning

    monkeypatch.setenv("KILO_API_KEY", "x")
    path2, warning2 = _compose(gateway_env)
    assert "stepfun/step-3.7-flash:free" in path2.read_text()


def test_tier_aliases_projected_from_user_assignments(gateway_env):
    import json

    state = gateway_env.parent / "state"
    _seed_cache(state, {
        "ollama": [{"id": "qwen2.5-coder:14b", "name": ""}],
        "kilo": [{"id": "stepfun/step-3.7-flash:free", "name": "Step Flash"}],
    })
    (state / "tier_assignments.json").write_text(
        json.dumps({"mid": "qwen2.5-coder:14b"})
    )
    data = yaml.safe_load(_compose(gateway_env)[0].read_text())
    names = {m["model_name"] for m in data["model_list"]}
    assert "mid" in names, "user-assigned tier must appear as routable alias"
    assert "qwen2.5-coder:14b" in names


def test_settings_identity_and_spend_callback():
    data = yaml.safe_load((MODELS / "settings.yaml").read_text())
    assert data["general_settings"]["master_key"] == config.LITELLM_KEY
    cbs = data["litellm_settings"]["callbacks"]
    assert any("spend_callback" in str(c) and "proxy_handler_instance" in str(c) for c in cbs)
    # LiteLLM resolves custom callbacks relative to the config file's dir,
    # so the hook must live at models/tools/litellm_hooks/.
    hook = MODELS / "tools" / "litellm_hooks" / "spend_callback.py"
    assert hook.exists()


def test_discovery_normalizes_and_filters(monkeypatch):
    """OpenAI-style payloads are normalized; :free filters apply per provider."""
    import io
    import json

    from pipa.providers import discover

    def fake_urlopen(req, timeout=0):
        url = req.full_url
        if "openrouter.ai" in url:
            body = {"data": [
                {"id": "nvidia/nemo-3-ultra:free", "name": "Nemo Ultra (free)"},
                {"id": "paid/model", "name": "Paid"},
                {"id": "nvidia/nemo-3-ultra:free", "name": "dup"},
            ]}
        elif "kilo.ai" in url:
            body = {"data": [
                {"id": "stepfun/step-3.7-flash:free", "name": "Step Flash"},
                {"id": "kilo-auto/frontier", "name": "Auto Frontier"},  # paid -> dropped
                {"id": "kilo-auto/free", "name": "Auto Free"},          # kept
            ]}
        else:
            raise AssertionError(f"unexpected probe {url}")
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr("pipa.providers.urlopen", fake_urlopen)

    or_result = discover("openrouter")
    assert or_result["ok"]
    assert [m["id"] for m in or_result["models"]] == ["nvidia/nemo-3-ultra:free"]

    kilo = discover("kilo")
    assert [m["id"] for m in kilo["models"]] == [
        "stepfun/step-3.7-flash:free", "kilo-auto/free",
    ]


def test_discovery_failure_is_soft(monkeypatch):
    from pipa.providers import discover

    def boom(req, timeout=0):
        raise OSError("network down")

    monkeypatch.setattr("pipa.providers.urlopen", boom)
    result = discover("openrouter")
    assert result["ok"] is False
    assert result["error"] and "network down" in result["error"]
    assert result["models"] == []


def test_refresh_persists_cache(monkeypatch, tmp_path):
    from pipa import providers

    monkeypatch.setattr(config, "state_dir", lambda: tmp_path)
    monkeypatch.setattr(providers, "discover", lambda slug, timeout=8: {
        "ok": True, "error": None,
        "models": [{"id": f"{slug}-model", "name": slug}],
    })
    summary = providers.refresh(timeout=1)
    cached = providers.cached_catalog()
    assert set(cached) == set(providers.PROVIDERS)
    assert cached["ollama"]["models"] == [{"id": "ollama-model", "name": "ollama"}]
    assert summary["fetched_at"]
