"""Knowledge — memory (vault notes) + graph (code graph query)."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from data import graph as graph_data
from data import memory as memory_data
from data import projects as projects_data
from . import form_fields, render

router = APIRouter()


def _clean_scope(value: str) -> str:
    return value if value in ("global", "project") else "global"


def _back(scope: str, extra: str = "") -> RedirectResponse:
    return RedirectResponse(f"/knowledge?scope={scope}{extra}", status_code=303)


def _grouped(notes: list) -> list:
    grouped: dict = {}
    for n in notes:
        grouped.setdefault(n["group"], []).append(n)
    return sorted(grouped.items())


@router.get("/knowledge")
def knowledge_view(request: Request, scope: str = "global", tab: str = "memory",
                   proj: str = "", q: str = "", gq: str = "",
                   saved: str = "", deleted: str = "", error: str = ""):
    scope = _clean_scope(scope)
    tab = tab if tab in ("memory", "graph") else "memory"
    projects = projects_data.registry_entries()
    if proj and proj not in {p["path"] for p in projects}:
        proj = ""

    # Memory data
    notes = memory_data.list_notes(scope, proj or None)
    hits, searched, recall_error = [], False, False
    query = (q or "").strip()
    if query:
        searched = True
        out = memory_data.recall(query, proj or None)
        hits = out.get("results", [])
        recall_error = bool(out.get("error"))
    expired_count = sum(1 for n in notes if n["expired"])

    # Graph data
    g_status = graph_data.status(proj or None)
    g_result = graph_data.query(gq, proj or None) if gq.strip() else None

    return render(
        request, "knowledge.html",
        tab=tab, scope=scope, projects=projects, proj=proj,
        notes=notes, groups=_grouped(notes),
        q=query, hits=hits, searched=searched, recall_error=recall_error,
        expired_count=expired_count,
        g_status=g_status, gq=(gq or "").strip(), g_result=g_result,
        saved=saved, deleted=deleted, error=error,
    )


# ── memory CRUD (same handlers as former memory page) ─────────────────────

@router.get("/knowledge/edit")
def knowledge_edit(request: Request, scope: str = "global", path: str = "",
                   name: str = "", proj: str = ""):
    scope = _clean_scope(scope)
    keep = f"&proj={quote(proj)}" if proj else ""
    if path == "new":
        ok, result = memory_data.new_note_path(scope, name)
        if not ok:
            return _back(scope, keep + "&error=" + quote(result))
        content = (
            "---\n"
            "as_of: \n"
            "valid_until: \n"
            "status: active\n"
            "---\n\n"
            f"# {result.rsplit('/', 1)[-1][:-3].replace('-', ' ').title()}\n\n"
        )
        return render(
            request, "context_edit.html",
            creating=True, tier=scope, tab="memory", rel=result, proj=proj,
            content=content, error="", memory=True,
        )
    content = memory_data.read_note(scope, path, proj or None)
    if content is None:
        return _back(scope, keep + "&error=" +
                     quote(f"cannot read {path} — missing or outside jail"))
    return render(
        request, "context_edit.html",
        creating=False, tier=scope, tab="memory", rel=path, proj=proj,
        content=content, error="", memory=True,
    )


@router.post("/knowledge/save")
async def knowledge_save(request: Request):
    fields = await form_fields(request)
    scope = _clean_scope(str(fields.get("tier", "")))
    raw_path = str(fields.get("path", ""))
    content = str(fields.get("content", ""))
    proj = str(fields.get("proj", ""))
    keep = f"&proj={quote(proj)}" if proj else ""
    if raw_path == "new":
        ok, result = memory_data.new_note_path(scope, str(fields.get("name", "")))
        if not ok:
            return _back(scope, keep + "&error=" + quote(result))
        rel = result
    else:
        rel = raw_path
    wrote_ok, msg = memory_data.write_note(scope, rel, content, proj or None)
    if wrote_ok:
        return _back(scope, keep + "&saved=1")
    return render(
        request, "context_edit.html",
        creating=False, tier=scope, tab="memory", rel=rel, proj=proj,
        content=content, error=msg, memory=True,
    )


@router.post("/knowledge/delete")
async def knowledge_delete(request: Request):
    fields = await form_fields(request)
    scope = _clean_scope(str(fields.get("tier", "")))
    proj = str(fields.get("proj", ""))
    ok, msg = memory_data.delete_note(scope, str(fields.get("path", "")), proj or None)
    extra = ("&proj=" + quote(proj) if proj else "") + \
            ("&deleted=1" if ok else "&error=" + quote(msg))
    return _back(scope, extra)


@router.post("/knowledge/expiry")
async def knowledge_expiry(request: Request):
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
    return _back(scope, extra)
