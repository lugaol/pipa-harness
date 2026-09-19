"""Redirect: /projects -> / (now folded into Status)."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from data import projects as projects_data
from . import form_fields

router = APIRouter()


@router.get("/projects")
def projects_view(request: Request, saved: str = "", error: str = ""):
    return RedirectResponse(url="/", status_code=307)


@router.get("/extensions")
def extensions_redirect():
    return RedirectResponse("/", status_code=307)


@router.post("/projects/runtime")
async def set_runtime(request: Request):
    fields = await form_fields(request)
    ok, msg = projects_data.set_runtime(
        str(fields.get("path", "")), str(fields.get("runtime", ""))
    )
    extra = "&saved=1" if ok else "&error=" + quote(msg)
    # Redirect to Status (projects now lives there)
    return RedirectResponse(f"/?flash={quote(msg[:300])}&ok={'1' if ok else '0'}",
                            status_code=303)
