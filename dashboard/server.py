#!/usr/bin/env python3
"""pipa_harness dashboard — modular FastAPI server (pages + fragments).

Wiring only: sys.path bootstrap, one router per pages/*.py, /static mount,
uvicorn entrypoint on $DASHBOARD_PORT (default 8080). All business logic
lives in dashboard/data/ and dashboard/pages/.
"""
from __future__ import annotations

import importlib
import os
import pkgutil
import sys
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parent
REPO_ROOT = DASHBOARD_DIR.parent

# `pipa` imports need the repo root; flat packages (`pages`, `data`) need
# the dashboard dir itself.
for _p in (str(REPO_ROOT), str(DASHBOARD_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

import pages  # noqa: E402


def create_app() -> FastAPI:
    """App factory: include every pages/*.router, mount /static."""
    app = FastAPI(title="pipa_harness dashboard", version="1.0.0")
    for mod_info in sorted(pkgutil.iter_modules(pages.__path__), key=lambda m: m.name):
        if mod_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"pages.{mod_info.name}")
        router = getattr(module, "router", None)
        if router is not None:
            app.include_router(router)
    app.mount(
        "/static",
        StaticFiles(directory=str(DASHBOARD_DIR / "static")),
        name="static",
    )
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    from pipa import config  # noqa: E402  (needs the bootstrap above)

    port = int(os.environ.get("DASHBOARD_PORT", config.DASHBOARD_PORT))
    # Loopback by default: the dashboard can rewrite rules and restart
    # services, so LAN exposure must be an explicit opt-in.
    host = os.environ.get("DASHBOARD_HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=port, log_level="warning")
