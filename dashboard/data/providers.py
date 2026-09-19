"""Provider catalog for the dashboard Providers page.

One row per provider in models/providers.yaml: key requirements (NAMES
only — values are never read), discovered-model counts, readiness.
Live network calls are limited to the local Ollama probe; cloud providers
are reported as ready/missing-keys without spending API calls.
"""
from __future__ import annotations

import os
import urllib.request
from typing import Dict, List, Tuple

from pipa import config


def _http_up(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except Exception:
        return False


def list_providers() -> List[dict]:
    """[{slug, label, kind, key_rows:[{name, present}], models, ready, live}].

    `live` is True only when actually probed over HTTP (Ollama); cloud
    rows are config-state, never live-called.
    """
    from pipa.providers import PROVIDERS, cached_catalog

    cat = cached_catalog()
    rows = []
    for slug, p in PROVIDERS.items():
        entry = cat.get(slug) or {}
        key_rows = [{"name": k, "present": bool(os.environ.get(k))} for k in p.requires]
        missing = [k["name"] for k in key_rows if not k["present"]]
        live = False
        if slug == "ollama":
            live = _http_up(config.OLLAMA_URL)
        ready = not missing and (live if slug == "ollama" else True)
        rows.append({
            "slug": slug,
            "label": p.label,
            "kind": p.kind,
            "key_rows": key_rows,
            "missing": missing,
            "models": len(entry.get("models") or []),
            "discovered": bool(entry.get("ok")),
            "live": live,
            "ready": ready,
        })
    return sorted(rows, key=lambda r: (r["kind"] != "local", r["label"].lower()))


def test_provider(slug: str) -> Tuple[bool, str]:
    """Best-effort check for one provider; never spends cloud API calls."""
    from pipa.providers import PROVIDERS

    p = PROVIDERS.get(slug)
    if p is None:
        return False, f"unknown provider '{slug}'"
    missing = [k for k in p.requires if not os.environ.get(k)]
    if missing:
        return False, f"missing keys: {', '.join(missing)}"
    if slug == "ollama":
        if _http_up(config.OLLAMA_URL):
            return True, "ollama is reachable"
        return False, "ollama not reachable — start it (`pipa install ollama`)"
    return True, f"{p.label}: keys present (cloud endpoints are not live-called)"


def provider_summary() -> Dict[str, int]:
    rows = list_providers()
    return {
        "total": len(rows),
        "ready": sum(1 for r in rows if r["ready"]),
    }
