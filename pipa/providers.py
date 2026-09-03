"""Dynamic model discovery from providers.

There is NO static model list anywhere in the harness. Each provider
exposes an OpenAI-style listing endpoint; this module queries it,
normalizes the result and caches it in state/model_catalog.json. The
gateway composer, the model registry and the dashboard all read that
cache — never hardcoded ids — because providers (especially their free
tiers) change constantly.

Only the *provider wiring* (endpoint, env key, litellm template) is code;
the models themselves always come from the wire. FREE-TIER ONLY by policy:
every provider's `keep` filter drops paid models so the catalog never
lists anything that costs money.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional
from urllib.request import Request, urlopen

from pipa import config

CATALOG_FILE = "model_catalog.json"
TIMEOUT_SECS = 8


def _free_only(model_id: str) -> bool:
    return model_id.endswith(":free")


def _zen_free_only(model_id: str) -> bool:
    return model_id.endswith("-free")


def _kilo_free_only(model_id: str) -> bool:
    return model_id.endswith(":free") or model_id == "kilo-auto/free"


def _ollama_local_only(model_id: str) -> bool:
    # ":cloud" models run on Ollama's servers and can cost money — local
    # installs are the free tier.
    return not model_id.endswith(":cloud")


@dataclass(frozen=True)
class Provider:
    """Static wiring for one provider; its model list is always dynamic."""

    slug: str
    label: str
    kind: str  # "local" | "cloud"
    requires: tuple[str, ...]  # env keys needed to CALL models (not to list)
    list_url: str
    litellm_params: Callable[[str], dict]
    keep: Callable[[str], bool] = lambda mid: True
    needs_key_for_list: bool = True


PROVIDERS: Dict[str, Provider] = {
    p.slug: p
    for p in [
        Provider(
            slug="ollama",
            label="Ollama",
            kind="local",
            requires=(),
            list_url="http://localhost:11434/v1/models",
            needs_key_for_list=False,
            keep=_ollama_local_only,
            litellm_params=lambda mid: {
                "model": f"openai/{mid}",
                "api_base": "http://localhost:11434/v1",
                "api_key": "ollama",
                "custom_llm_provider": "openai",
            },
        ),
        Provider(
            slug="opencode-zen",
            label="OpenCode Zen Free",
            kind="cloud",
            requires=("OPENCODE_ZEN_API_KEY",),
            list_url="https://opencode.ai/zen/v1/models",
            keep=_zen_free_only,
            litellm_params=lambda mid: {
                "model": f"openai/{mid}",
                "api_base": "https://opencode.ai/zen/v1",
                "api_key": "os.environ/OPENCODE_ZEN_API_KEY",
            },
        ),
        Provider(
            slug="openrouter",
            label="OpenRouter Free",
            kind="cloud",
            requires=("OPENROUTER_API_KEY",),
            list_url="https://openrouter.ai/api/v1/models",
            needs_key_for_list=False,  # listing is public; calls need the key
            keep=_free_only,
            litellm_params=lambda mid: {
                "model": f"openrouter/{mid}",
                "api_key": "os.environ/OPENROUTER_API_KEY",
            },
        ),
        Provider(
            slug="kilo",
            label="Kilo Free",
            kind="cloud",
            requires=("KILO_API_KEY",),
            list_url="https://api.kilo.ai/api/gateway/v1/models",
            keep=_kilo_free_only,
            litellm_params=lambda mid: {
                "model": mid,
                "custom_llm_provider": "openai",
                "api_base": "https://api.kilo.ai/api/gateway",
                "api_key": "os.environ/KILO_API_KEY",
            },
        ),
    ]
}


def cache_path():
    return config.state_dir() / CATALOG_FILE


def _headers(p: Provider) -> dict:
    key = next((os.environ[k] for k in p.requires if os.environ.get(k)), "")
    return {"Authorization": f"Bearer {key}"} if key else {}


def discover(slug: str, timeout: int = TIMEOUT_SECS) -> dict:
    """Live-query one provider -> {ok, error, models:[{id, name}]}."""
    result: dict = {"ok": False, "error": None, "models": []}
    try:
        p = PROVIDERS[slug]
        req = Request(p.list_url, headers={"User-Agent": "pipa-harness", **_headers(p)})
        with urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
        rows = data.get("data") if isinstance(data, dict) else data
        models: List[dict] = []
        seen: set[str] = set()
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            mid = str(row.get("id") or "").strip()
            if not mid or mid in seen or not p.keep(mid):
                continue
            seen.add(mid)
            models.append({"id": mid, "name": str(row.get("name") or "").strip()})
        result.update(ok=True, models=models)
    except Exception as e:  # noqa: BLE001 — discovery must never raise
        result["error"] = f"{type(e).__name__}: {e}"[:200]
    return result


def refresh(timeout: int = TIMEOUT_SECS) -> dict:
    """Discover models from every provider and persist the cache."""
    out = {
        "version": 1,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "providers": {slug: discover(slug, timeout) for slug in PROVIDERS},
    }
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n")
    return out


def cached_catalog() -> dict:
    """{slug -> {ok, error, models[]}} from cache; {} when absent/corrupt."""
    try:
        data = json.loads(cache_path().read_text())
    except Exception:
        return {}
    provs = data.get("providers") if isinstance(data, dict) else None
    return provs if isinstance(provs, dict) else {}


def fetched_at() -> Optional[str]:
    try:
        return str(json.loads(cache_path().read_text()).get("fetched_at")) or None
    except Exception:
        return None


def missing_keys(alias: str) -> List[str]:
    """Env keys the owning provider needs but that are unset ([] when ready)."""
    for slug, entry in cached_catalog().items():
        if any(m["id"] == alias for m in entry.get("models") or []):
            p = PROVIDERS.get(slug)
            if p is None:
                return []
            return [k for k in p.requires if not os.environ.get(k)]
    return []
