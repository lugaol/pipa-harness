"""LiteLLM gateway reader: model list + health probe.

Read-only HTTP against {LITELLM_URL}/v1/models. Every failure degrades to
an empty result so pages render an empty state instead of a 500.
"""
from __future__ import annotations

import json
import urllib.request
from typing import List

from pipa import config


def _get_models_json(timeout: float):
    url = f"{config.LITELLM_URL}/v1/models"
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {config.LITELLM_KEY}"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def list_models(timeout: float = 3.0) -> List[str]:
    """Sorted gateway model ids; [] when the gateway is unreachable."""
    try:
        data = _get_models_json(timeout)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    ids = [
        str(m.get("id"))
        for m in data.get("data", [])
        if isinstance(m, dict) and m.get("id")
    ]
    return sorted(ids)


def health(timeout: float = 2.0) -> bool:
    """True when /v1/models answers (any JSON body)."""
    try:
        _get_models_json(timeout)
        return True
    except Exception:
        return False
