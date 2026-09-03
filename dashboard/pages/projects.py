"""Projects page: registry table + runtime switching.

Each row carries a runtime <select> (from pipa.runtime names) with Apply —
the POST only accepts paths that already sit in the registry.
/extensions is kept as a redirect for old links.
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from pipa.runtime import names as runtime_names

from data import projects as projects_data
from . import form_fields, render

router = APIRouter()


@router.get("/projects")
def projects_view(request: Request, saved: str = "", error: str = ""):
    projects = projects_data.list_projects()
    return render(
        request,
        "projects.html",
        title="Projects",
        projects=projects,
        runtimes=runtime_names(),
        count=len(projects),
        saved=saved,
        error=error,
    )


@router.get("/extensions")
def extensions_redirect():
    return RedirectResponse("/projects", status_code=307)


@router.post("/projects/runtime")
async def set_runtime(request: Request):
    fields = await form_fields(request)
    ok, msg = projects_data.set_runtime(
        str(fields.get("path", "")), str(fields.get("runtime", ""))
    )
    extra = "&saved=1" if ok else "&error=" + quote(msg)
    return RedirectResponse(f"/projects{extra}", status_code=303)
