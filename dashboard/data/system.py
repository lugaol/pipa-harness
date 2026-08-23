"""System status checks — mirrors `pipa status` essentials.

Reads live service state without importing pipa.cli: gateway/ollama HTTP
probes, litellm/graphify binaries on PATH, active-project info.
"""
from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path
from typing import List, Optional

from pipa import config

from . import gateway


def _http_up(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except Exception:
        return False


def checks() -> List[dict]:
    """[{name, ok, detail}] in the spirit of cmd_status."""
    gw_up = gateway.health()
    ollama_up = _http_up(config.OLLAMA_URL)
    litellm_bin = shutil.which("litellm")
    graphify_bin = shutil.which("graphify")
    return [
        {
            "name": "litellm gateway",
            "ok": gw_up,
            "detail": f"up at {config.LITELLM_URL}" if gw_up else "not reachable",
        },
        {
            "name": "ollama",
            "ok": ollama_up,
            "detail": "running" if ollama_up else "not running",
        },
        {
            "name": "litellm binary",
            "ok": bool(litellm_bin),
            "detail": litellm_bin or "not on PATH",
        },
        {
            "name": "graphify",
            "ok": bool(graphify_bin),
            "detail": graphify_bin or "not on PATH",
        },
    ]


def up_down(check_list: List[dict]) -> dict:
    return {"up": sum(1 for c in check_list if c["ok"]), "total": len(check_list)}


def project_info() -> Optional[dict]:
    """Active project: path, name, runtime (read from .pipa/runtime)."""
    try:
        project = config.find_project()
    except Exception:
        project = None
    if project is None:
        return None
    runtime_file = config.pipa_dir(project) / config.RUNTIME_MARKER
    runtime = ""
    try:
        if runtime_file.is_file():
            runtime = runtime_file.read_text().strip()
    except OSError:
        runtime = ""
    return {
        "path": str(project),
        "name": project.name,
        "runtime": runtime or "auto",
    }
