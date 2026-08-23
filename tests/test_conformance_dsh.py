"""Conformance: the dsh (DeepSeek Harness) patch contract.

Encodes real dsh schema rules: a flat list of loader entries targeting rows
by id, one OpenAI-compatible route per provider, env-based API keys (a bare
`apiKey` key is forbidden), and LiteLLM compat flags (no developer role, no
max_completion_tokens).
"""
import re
from pathlib import Path

import pytest
import yaml

from pipa import config

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "clis" / "deepseek-harness" / "cordis.patch.yml"
CORE_ALIASES = {"primary", "fast", "deep", "explore"}


@pytest.fixture(scope="module")
def entries() -> list[dict]:
    # The raw template holds @LITELLM_URL@, which is not YAML-safe; parse it
    # the way wire_deepseek_harness consumes it: after placeholder rendering.
    rendered = TEMPLATE.read_text().replace("@LITELLM_URL@", config.LITELLM_URL)
    data = yaml.safe_load(rendered)
    assert isinstance(data, list), "patch must be a flat list of loader entries"
    return data


def _entry(entries: list[dict], id_: str) -> dict:
    matches = [e for e in entries if e.get("id") == id_]
    assert matches, f"no patch entry with id {id_!r}"
    return matches[0]


def _litellm_route(entries: list[dict]) -> dict:
    providers = _entry(entries, "llm-pi-ai")["config"]["providers"]
    assert isinstance(providers, dict) and "litellm" in providers
    return providers["litellm"]


def test_patch_is_nonempty_list_of_entries(entries):
    assert len(entries) >= 2


def test_llm_pi_ai_route_shape(entries):
    route = _litellm_route(entries)
    assert route["api"] == "openai-completions"
    assert route["baseURL"] == f"{config.LITELLM_URL}/v1"
    assert route["apiKeyEnv"]


def test_no_literal_apikey_key_anywhere():
    # \bapiKey\b does not match apiKeyEnv; any bare key would leak secrets.
    assert not re.search(r"\bapiKey\b", TEMPLATE.read_text())


def test_litellm_compat_keys(entries):
    compat = _litellm_route(entries)["compat"]
    assert compat["supportsDeveloperRole"] is False
    assert compat["maxTokensField"] == "max_tokens"


def test_models_cover_core_aliases(entries):
    models = _litellm_route(entries)["models"]
    assert models, "route must declare at least one model"
    ids = {m["id"] for m in models}
    assert CORE_ALIASES <= ids


def test_agent_default_model_uses_litellm(entries):
    entry = _entry(entries, "agent-default-model")
    assert entry["config"]["provider"] == "litellm"


def test_template_has_placeholder():
    assert "@LITELLM_URL@" in TEMPLATE.read_text()
