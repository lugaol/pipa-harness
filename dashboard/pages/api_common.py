"""Shared helpers for the JSON API routers (no routes here).

Split out of api.py (Phase A.3): one owner per helper, imported by the
per-domain api_*.py routers. No behavior change.
"""
from __future__ import annotations

from data import models as models_data


def _catalog() -> list:
    try:
        rows = models_data.catalog()
    except Exception:
        return []
    return [{"id": r["alias"], "name": r["display"],
             "provider": r["provider"]} for r in rows]


def _known_aliases() -> set:
    return {c["id"] for c in _catalog()}


def _verify_effective() -> None:
    """Fail closed: the composed gateway config must parse with a model_list.

    A bad write must never take the running gateway down — verify before
    any restart (ia save_registry discipline).
    """
    import yaml

    from pipa import config

    effective = config.models_dir() / ".effective.yaml"
    data = yaml.safe_load(effective.read_text())
    if not isinstance(data, dict) or not data.get("model_list"):
        raise ValueError(".effective.yaml has no model_list after compose")
