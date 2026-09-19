"""Redirect: /memory -> /knowledge?tab=memory (backwards compat)."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from data import memory as memory_data
from . import form_fields, render

router = APIRouter()


def _clean_scope(value: str) -> str:
    return value if value in ("global", "project") else "global"


def _back(scope: str, extra: str = "") -> RedirectResponse:
    return RedirectResponse(f"/memory?scope={scope}{extra}", status_code=303)


@router.get("/memory")
def memory_view(request: Request, scope: str = "global", proj: str = "",
                q: str = "", saved: str = "", deleted: str = "",
                error: str = ""):
    params = f"?tab=memory&scope={_clean_scope(scope)}"
    if proj:
        params += f"&proj={quote(proj)}"
    if q.strip():
        params += f"&q={quote(q.strip())}"
    return RedirectResponse(url=f"/knowledge{params}", status_code=307)


@router.get("/memory/edit")
def memory_edit(request: Request, scope: str = "global", path: str = "",
                name: str = "", proj: str = ""):
    scope = _clean_scope(scope)
    params = f"?scope={scope}&path={quote(path)}"
    if name:
        params += f"&name={quote(name)}"
    if proj:
        params += f"&proj={quote(proj)}"
    return RedirectResponse(url=f"/knowledge/edit{params}", status_code=307)


@router.post("/memory/save")
async def memory_save(request: Request):
    fields = await form_fields(request)
    scope = _clean_scope(str(fields.get("tier", "")))
    raw_path = str(fields.get("path", ""))
    content = str(fields.get("content", ""))
    proj = str(fields.get("proj", ""))
    keep = f"&proj={quote(proj)}" if proj else ""
    if raw_path == "new":
        ok, result = memory_data.new_note_path(scope, str(fields.get("name", "")))
        if not ok:
            return RedirectResponse(
                f"/knowledge?tab=memory&scope={scope}{keep}&error={quote(result)}",
                status_code=303)
        rel = result
    else:
        rel = raw_path
    wrote_ok, msg = memory_data.write_note(scope, rel, content, proj or None)
    if wrote_ok:
        return RedirectResponse(f"/knowledge?tab=memory&scope={scope}{keep}&saved=1",
                                status_code=303)
    return render(
        request, "context_edit.html",
        creating=False, tier=scope, tab="memory", rel=rel, proj=proj,
        content=content, error=msg, memory=True,
    )


@router.post("/memory/delete")
async def memory_delete(request: Request):
    fields = await form_fields(request)
    scope = _clean_scope(str(fields.get("tier", "")))
    proj = str(fields.get("proj", ""))
    ok, msg = memory_data.delete_note(scope, str(fields.get("path", "")), proj or None)
    extra = ("&proj=" + quote(proj) if proj else "") + \
            ("&deleted=1" if ok else "&error=" + quote(msg))
    return RedirectResponse(f"/knowledge?tab=memory&scope={scope}{extra}", status_code=303)


@router.post("/memory/expiry")
async def memory_expiry(request: Request):
    fields = await form_fields(request)
    scope = _clean_scope(str(fields.get("tier", "")))
    rel = str(fields.get("path", ""))
    proj = str(fields.get("proj", ""))
    action = str(fields.get("action", ""))
    if action == "extend":
        ok, msg = memory_data.extend_years(scope, rel, 1, proj or None)
    elif action == "expire":
        ok, msg = memory_data.set_expiry(scope, rel, "2000-01-01", proj or None)
    else:
        ok, msg = memory_data.set_expiry(scope, rel, None, proj or None)
    extra = ("&proj=" + quote(proj) if proj else "") + \
            ("&saved=1" if ok else "&error=" + quote(msg))
    return RedirectResponse(f"/knowledge?tab=memory&scope={scope}{extra}", status_code=303)
