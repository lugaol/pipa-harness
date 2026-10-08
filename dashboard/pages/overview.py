"""Status page: health grid, env keys, projects, MCP."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from pipa.runtime import RUNTIMES

from data import mcp as mcp_data
from data import projects as projects_data
from data import services as services_data
from data import system
from . import form_fields, render

router = APIRouter()


@router.get("/api/health")
def health():
    """Lightweight probe for the sidebar status pill.

    Reads the same owned check list as /api/status instead of looking rows up by
    lowercased name. It used to match on the literal string "litellm gateway",
    so any rename of that subsystem silently reported False for both services
    rather than failing loudly.
    """
    try:
        rows = system.checks()
    except Exception:
        rows = []
    by_name = {r["name"]: r for r in rows}
    return {
        "gateway": bool(by_name.get("litellm gateway", {}).get("ok")),
        "ollama": bool(by_name.get("ollama", {}).get("ok")),
    }


@router.get("/")
def overview(request: Request, flash: str = "", ok: str = ""):
    # Only what overview.html actually renders. It used to also build `cards`,
    # `checks`, `gateway_up`, `ollama_up` and `env_keys` — five values Jinja
    # silently dropped (Undefined renders as empty), two of which cost an HTTP
    # probe to the gateway and ollama on every single page load. The status
    # grid and the key chips are JS-driven from /api/status and /api/env-keys.
    project = system.project_info()

    # Projects + MCP for the folded sections
    try:
        projects = projects_data.list_projects()
    except Exception:
        projects = []
    try:
        mcp_servers = mcp_data.list_servers()
    except Exception:
        mcp_servers = []

    return render(
        request,
        "overview.html",
        project=project,
        projects=projects,
        runtimes=list(RUNTIMES),
        mcp_servers=mcp_servers,
        flash=flash,
        flash_ok=ok != "0",
    )


@router.post("/api/services/gateway/restart")
def restart_gateway(request: Request):
    ok, msg = services_data.gateway_restart()
    return RedirectResponse(
        f"/?flash={quote(msg[:300])}&ok={'1' if ok else '0'}", status_code=303
    )


@router.post("/api/services/ollama/start")
def start_ollama(request: Request):
    ok, msg = services_data.ollama_start()
    return RedirectResponse(
        f"/?flash={quote(msg[:300])}&ok={'1' if ok else '0'}", status_code=303
    )


@router.post("/projects/runtime")
async def set_project_runtime(request: Request):
    """Single owner of the project-runtime switch.

    Reads BOTH historical field names: the current form posts "project", the
    retired pages/projects.py form posted "path". That module was shadowed by
    this one (server.py includes routers alphabetically) while reading the
    other name, so it would have failed closed on a blank path the moment
    ordering changed — silently, because its caller discarded the verdict.
    Also honours the (ok, msg) the data layer actually returns, rather than
    reporting success unconditionally.
    """
    fields = await form_fields(request)
    project = str(fields.get("project") or fields.get("path") or "")
    runtime = str(fields.get("runtime") or "")
    try:
        ok, msg = projects_data.set_runtime(project, runtime)
    except Exception as exc:  # noqa: BLE001
        ok, msg = False, f"{type(exc).__name__}: {exc}"[:300]
    return RedirectResponse(
        f"/?flash={quote(msg[:300])}&ok={'1' if ok else '0'}", status_code=303
    )


@router.post("/api/mcp/toggle")
async def mcp_toggle(request: Request):
    fields = await form_fields(request)
    ok, msg = mcp_data.set_enabled(
        str(fields.get("server", "")), str(fields.get("enabled", "")) == "1"
    )
    extra = "&saved=1" if ok else "&error=" + quote(msg)
    # Redirect back to status (MCP now lives there)
    return RedirectResponse(f"/?flash={quote(msg[:300])}&ok={'1' if ok else '0'}",
                            status_code=303)
