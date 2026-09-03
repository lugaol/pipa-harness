"""Conformance: opencode JSONC configs (extension template + global).

JSONC must survive a comment/trailing-comma strip and parse as strict JSON;
the gateway endpoint, key, and declared models must match the model
fragments under models/{local,cloud}/.
"""
import json
import re
from pathlib import Path

import pytest
import yaml

from pipa import config

ROOT = Path(__file__).resolve().parents[1]
GLOBAL_JSONC = ROOT / "clis" / "opencode" / "global.jsonc"

PLACEHOLDERS = {"@PIPA_ROOT@": "/pipa-root"}


def _strip_jsonc(text: str) -> str:
    """Remove // comments (outside strings) and trailing commas."""
    out: list[str] = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        out.append(ch)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def _load_jsonc(path: Path) -> dict:
    text = path.read_text()
    for key, value in PLACEHOLDERS.items():
        text = text.replace(key, value)
    return json.loads(_strip_jsonc(text))


def _gateway_aliases() -> set[str]:
    """Every alias any model fragment can provide."""
    names: set[str] = set()
    for sub in ("local", "cloud"):
        for frag in sorted((ROOT / "models" / sub).glob("*.yaml")):
            data = yaml.safe_load(frag.read_text()) or {}
            names |= {e["model_name"] for e in data.get("models", [])}
    return names


def test_jsonc_parses_as_json():
    assert isinstance(_load_jsonc(GLOBAL_JSONC), dict)


def test_gateway_endpoint_and_key():
    opts = _load_jsonc(GLOBAL_JSONC)["provider"]["litellm"]["options"]
    assert opts["baseURL"] == f"http://localhost:{config.LITELLM_PORT}/v1"
    assert opts["apiKey"] == config.LITELLM_KEY


def test_declared_models_subset_of_gateway_aliases():
    models = _load_jsonc(GLOBAL_JSONC)["provider"]["litellm"]["models"]
    # Tier ids are exempt: injected at wire time from the user's dashboard
    # assignments, so no static fragment has to provide them.
    tier_ids = {"lowest", "low", "mid", "high", "xhigh"}
    assert set(models) - tier_ids <= _gateway_aliases()


def test_global_instructions_cover_both_tiers():
    instructions = _load_jsonc(GLOBAL_JSONC)["instructions"]
    assert len(instructions) >= 3
    # global tier: first entries point into the install (substituted at render)
    assert instructions[0].endswith("AGENTS.md")
    assert "/rules/*.md" in instructions[1]
    # per-project overlay tier loads thin-project rules at launch time
    assert ".pipa/rules/*.md" in instructions


def test_render_injects_mcp_registry_and_permissions():
    from pipa import runtime

    cfg = runtime.render_opencode_config(ROOT)
    assert "@PIPA_ROOT@" not in json.dumps(cfg)
    mcp_cfg = ROOT / "mcp" / "context7" / "config.json"
    if mcp_cfg.exists():
        assert "context7" in cfg["mcp"]
        assert "context7_*" in cfg["permission"]
