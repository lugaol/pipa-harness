"""JSON API: Install wizard stage readiness.

Split out of api.py (Phase A.3). Routes byte-identical — no behavior change.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/api/install/state")
def api_install_state():
    """Per-stage readiness for the Install wizard."""
    from pipa import services
    from pipa.commands.install import INSTALL_COMPONENTS

    bin_of = {
        "uv": "uv", "ollama": "ollama", "litellm": "litellm",
        "graphify": "graphify", "opencode": "opencode", "dsh": "dsh",
    }
    stages = []
    for slug in INSTALL_COMPONENTS:
        binary = bin_of.get(slug)
        if slug == "verify":
            try:
                from pipa.commands.doctor import _collect

                checks = _collect()
                fails = sum(1 for c in checks if c["status"] == "fail")
                warns = sum(1 for c in checks if c["status"] == "warn")
                ready = fails == 0
                detail = (f"pipa doctor: {len(checks) - fails - warns} pass, "
                          f"{warns} warn, {fails} fail")
            except Exception as exc:
                ready, detail = False, f"doctor failed: {exc}"
        elif binary:
            ready = services.have(binary)
            detail = f"{binary} on PATH" if ready else f"{binary} not installed"
        elif slug == "py-deps":
            try:
                import fastapi, uvicorn, yaml  # noqa: F401

                ready, detail = True, "gateway + dashboard deps importable"
            except ImportError as exc:
                ready, detail = False, f"missing: {exc}"
        else:  # apps
            ready, detail = False, "GUI helpers install on demand"
        stages.append({"slug": slug, "ready": ready, "detail": detail})
    return JSONResponse({"stages": stages})
