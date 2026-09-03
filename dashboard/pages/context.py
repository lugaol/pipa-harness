"""Context page: authoring UI for rules/skills/agents + MCP registry.

GET  /context        tier switcher + tab strip + listings
GET  /context/edit   monospace editor (new-file mode via path=new&name=)
POST /context/save   create/update through the data-layer jail
POST /context/delete delete one entry (confirm happens client-side)
POST /api/mcp/toggle enable/disable one registered MCP server

Flash state travels via ?saved=1 / ?deleted=1 / ?error= query params.
Agent tier overrides live on the /agents page only.
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from pipa.model_registry import normalize_tier
from pipa.runtime import AGENT_MODEL_MAP

from data import agents as agents_data
from data import context as context_data
from data import mcp as mcp_data
from . import form_fields, render

router = APIRouter()

_TABS = (
    {"id": "rules", "label": "Rules"},
    {"id": "skills", "label": "Skills"},
    {"id": "agents", "label": "Agents"},
    {"id": "mcp", "label": "MCP"},
)


def _clean_tier(value: str) -> str:
    return value if value in context_data.TIERS else "project"


def _clean_tab(value: str) -> str:
    return value if value in context_data.TABS else "rules"


def _back(tier: str, tab: str, extra: str = "") -> RedirectResponse:
    return RedirectResponse(f"/context?tier={tier}&tab={tab}{extra}", status_code=303)


def _starter(tab: str, rel: str) -> str:
    stem = rel.rsplit("/", 1)[-1]
    if stem.endswith(".md"):
        stem = stem[:-3]
    if tab == "skills":
        return f"# {stem}\n\nUse when the task matches this skill.\n"
    if tab == "agents":
        return (
            "---\n"
            f"name: {stem}\n"
            "description: \n"
            "mode: subagent\n"
            "model: \n"
            "---\n\n"
        )
    return f"# {stem}\n\n"


@router.get("/context")
def context_view(request: Request, tier: str = "project", tab: str = "rules",
                 saved: str = "", deleted: str = "",
                 error: str = "", proj: str = ""):
    tier = _clean_tier(tier)
    tab = _clean_tab(tab)
    projects = context_data.list_projects()
    if proj and proj not in {p["path"] for p in projects}:
        proj = ""
    has_project = bool(projects) or _find_project() is not None
    tier_hint = "" if has_project or tier == "global" else \
        "No pipa projects registered yet — run pipa init in a project."
    project_path = proj or (projects[-1]["path"] if projects else "")

    entries = context_data.list_entries(tier, project_path or None, tab)

    agent_rows = []
    if tab == "agents":
        for e in entries:
            text = context_data.read_entry(tier, project_path or None, tab, e["path_rel"]) or ""
            fm, _body = agents_data.parse_frontmatter(text)
            name = fm.get("name") or e["path_rel"].rsplit("/", 1)[-1][:-3]
            override = agents_data.override_for(name)
            agent_rows.append({
                **e,
                "description": fm.get("description", ""),
                "name": name,
                "model_badge": normalize_tier(override or "")
                or AGENT_MODEL_MAP.get(name, "—"),
                "override": normalize_tier(override or ""),
            })

    servers = mcp_data.list_servers() if tab == "mcp" else []

    return render(
        request,
        "context.html",
        tier=tier,
        tab=tab,
        tabs=_TABS,
        projects=projects,
        proj=project_path,
        has_project=has_project,
        tier_hint=tier_hint,
        entries=entries,
        agent_rows=agent_rows,
        servers=servers,
        saved=saved,
        deleted=deleted,
        error=error,
    )


def _find_project():
    try:
        from pipa import config
        return config.find_project()
    except Exception:
        return None


@router.get("/context/edit")
def context_edit(request: Request, tier: str = "project", tab: str = "rules",
                 path: str = "", name: str = "", proj: str = ""):
    tier = _clean_tier(tier)
    tab = _clean_tab(tab)
    keep = f"&proj={quote(proj)}" if proj else ""
    if path == "new":
        ok, result = context_data.new_entry_path(tier, proj or None, tab, name)
        if not ok:
            return _back(tier, tab, keep + "&error=" + quote(result))
        return render(
            request, "context_edit.html",
            creating=True, tier=tier, tab=tab, rel=result, proj=proj,
            content=_starter(tab, result), error="",
        )
    content = context_data.read_entry(tier, proj or None, tab, path)
    if content is None:
        return _back(tier, tab, keep + "&error=" +
                     quote(f"cannot read {path} — missing or outside jail"))
    return render(
        request, "context_edit.html",
        creating=False, tier=tier, tab=tab, rel=path, proj=proj,
        content=content, error="",
    )


@router.post("/context/save")
async def context_save(request: Request):
    fields = await form_fields(request)
    tier = _clean_tier(str(fields.get("tier", "")))
    tab = _clean_tab(str(fields.get("tab", "")))
    raw_path = str(fields.get("path", ""))
    content = str(fields.get("content", ""))
    proj = str(fields.get("proj", ""))
    keep = f"&proj={quote(proj)}" if proj else ""
    if raw_path == "new":
        ok, result = context_data.new_entry_path(tier, proj or None, tab, str(fields.get("name", "")))
        if not ok:
            return _back(tier, tab, keep + "&error=" + quote(result))
        rel = result
    else:
        rel = raw_path
    wrote_ok, msg = context_data.write_entry(tier, proj or None, tab, rel, content)
    if wrote_ok:
        return _back(tier, tab, keep + "&saved=1")
    # keep the editor open with the user's text intact on failure
    return render(
        request, "context_edit.html",
        creating=False, tier=tier, tab=tab, rel=rel, proj=proj,
        content=content, error=msg,
    )


@router.post("/context/delete")
async def context_delete(request: Request):
    fields = await form_fields(request)
    tier = _clean_tier(str(fields.get("tier", "")))
    tab = _clean_tab(str(fields.get("tab", "")))
    proj = str(fields.get("proj", ""))
    ok, msg = context_data.delete_entry(tier, proj or None, tab, str(fields.get("path", "")))
    extra = ("&proj=" + quote(proj) if proj else "") + ("&deleted=1" if ok else "&error=" + quote(msg))
    return _back(tier, tab, extra)


@router.post("/api/mcp/toggle")
async def mcp_toggle(request: Request):
    fields = await form_fields(request)
    ok, msg = mcp_data.set_enabled(
        str(fields.get("server", "")), str(fields.get("enabled", "")) == "1"
    )
    extra = "&saved=1" if ok else "&error=" + quote(msg)
    return _back(_clean_tier(str(fields.get("tier", ""))), "mcp", extra)
