"""Gateway conformance: models/ fragment architecture.

The effective gateway config is COMPOSED from models/{local,cloud}/*.yaml
fragments + models/settings.yaml. These tests pin the fragment contracts.
"""
from pathlib import Path

import pytest
import yaml

from pipa import config

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"

CORE_ALIASES = {"primary", "fast", "deep", "explore"}


def _fragments(sub: str) -> list[Path]:
    return sorted((MODELS / sub).glob("*.yaml"))


def test_fragments_exist():
    assert _fragments("local"), "models/local/ must define the fallback tier"
    assert _fragments("cloud"), "models/cloud/ must define the cloud tiers"
    assert (MODELS / "settings.yaml").exists()


@pytest.mark.parametrize("frag", [str(p) for p in (*_fragments("local"), *_fragments("cloud"))])
def test_fragment_structure(frag):
    data = yaml.safe_load(Path(frag).read_text()) or {}
    assert isinstance(data.get("models"), list) and data["models"], frag
    for m in data["models"]:
        assert m.get("model_name"), frag
        params = m.get("litellm_params") or {}
        assert params.get("api_key"), f"{frag}: {m.get('model_name')} missing api_key"


def test_settings_identity_and_spend_callback():
    data = yaml.safe_load((MODELS / "settings.yaml").read_text())
    assert data["general_settings"]["master_key"] == config.LITELLM_KEY
    cbs = data["litellm_settings"]["callbacks"]
    assert any("spend_callback" in str(c) and "proxy_handler_instance" in str(c) for c in cbs)
    # LiteLLM resolves custom callbacks relative to the config file's dir,
    # so the hook must live at models/tools/litellm_hooks/.
    hook = MODELS / "tools" / "litellm_hooks" / "spend_callback.py"
    assert hook.exists()


def test_local_tier_is_ollama_and_covers_core_aliases():
    models: dict[str, dict] = {}
    for frag in _fragments("local"):
        for m in (yaml.safe_load(frag.read_text()) or {}).get("models", []):
            models[m["model_name"]] = m
    assert CORE_ALIASES <= set(models), f"local tier missing: {CORE_ALIASES - set(models)}"
    for name, m in models.items():
        base = m["litellm_params"]["api_base"]
        assert base.startswith("http://localhost:11434"), f"{name} not local: {base}"


def test_cloud_roles_upgrade_only_with_keys(monkeypatch):
    monkeypatch.delenv("KILO_API_KEY", raising=False)
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    path, warning = config.compose_litellm_config(root=ROOT)
    text = path.read_text()
    assert "qwen2.5-coder" in text, "local tier must survive with no keys"
    assert warning is not None

    monkeypatch.setenv("KILO_API_KEY", "x")
    monkeypatch.setenv("KIMI_API_KEY", "x")
    path2, warning2 = config.compose_litellm_config(root=ROOT)
    text2 = path2.read_text()
    assert "kilo-auto/free" in text2
    assert "moonshot.cn" in text2
    assert warning2 is not None and "kilo.yaml" not in warning2 \
        and "kimi.yaml" not in warning2  # only keyless fragments are skipped


def test_composed_aliases_superset_of_opencode_declarations():
    """Every alias opencode declares must be producible by some fragment."""
    declared: set[str] = set()
    jsonc_candidates = [
        ROOT / "clis" / "opencode" / "global.jsonc",
        *sorted((ROOT / "clis" / "opencode" / "extension").glob("*.jsonc")),
    ]
    import re
    for p in jsonc_candidates:
        if not p.exists():
            continue
        text = p.read_text()
        block = text.split('"models"', 1)[-1].split("}", 1)[0]
        declared |= set(re.findall(r'"([A-Za-z0-9_.-]+)"\s*:\s*\{\}', block))
    producible: set[str] = set()
    for sub in ("local", "cloud"):
        for frag in _fragments(sub):
            for m in (yaml.safe_load(frag.read_text()) or {}).get("models", []):
                producible.add(m["model_name"])
    missing = declared - producible
    assert not missing, f"opencode declares aliases no fragment provides: {missing}"
