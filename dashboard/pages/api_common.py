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
