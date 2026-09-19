"""JSON API: Rules & Skills doc browser (jailed reads + writes).

Split out of api.py (Phase A.3). Routes byte-identical — no behavior change.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from pipa import config

router = APIRouter()

_DOC_ROOTS: dict = {}
_DOC_ROOT_FOR: str = ""


def _doc_roots() -> dict:
    """{namespace: dir} — global harness + active project overlay."""
    from pipa import config

    global _DOC_ROOT_FOR
    root = config.harness_root()
    if _DOC_ROOTS and _DOC_ROOT_FOR == str(root):
        return _DOC_ROOTS
    _DOC_ROOTS.clear()
    _DOC_ROOT_FOR = str(root)
    root = config.harness_root()
    roots = {
        "agents": root / "agents",
        "rules": root / "rules",
        "skills": root / "skills",
    }
    try:
        project = config.find_project()
    except Exception:
        project = None
    if project is not None:
        pdir = config.pipa_dir(project)
        if (pdir / "rules").is_dir():
            roots["project/rules"] = pdir / "rules"
        if (pdir / "skills").is_dir():
            roots["project/skills"] = pdir / "skills"
    for namespace, path in list(roots.items()):
        if not path.is_dir():
            roots.pop(namespace, None)
    _DOC_ROOTS.update(roots)
    return _DOC_ROOTS


@router.get("/api/docs")
def api_list_docs():
    docs = []
    for namespace, root_dir in _doc_roots().items():
        for f in sorted(root_dir.rglob("*.md")):
            rel = f.relative_to(root_dir)
            if f.stem.upper() in ("SKILL", "README") and len(rel.parts) > 1:
                display = rel.parts[-2]
            else:
                display = f.stem
            docs.append({
                "root": namespace.split("/")[0],
                "path": f"{namespace}/{rel.as_posix()}",
                "name": display,
                "group": rel.parts[0] if len(rel.parts) > 1 else namespace,
            })
    docs.sort(key=lambda d: d["path"])
    agents_md = config.harness_root() / "AGENTS.md"
    if agents_md.is_file():
        docs.insert(0, {"root": "agents", "path": "agents/AGENTS.md",
                        "name": "AGENTS.md (entry file)", "group": "agents"})
    return JSONResponse(docs)


def _resolve_doc(rel_path: str):
    from pathlib import Path

    from pipa import config

    if rel_path == "agents/AGENTS.md":
        cand = config.harness_root() / "AGENTS.md"
        if cand.is_file():
            return cand
        raise HTTPException(404, "AGENTS.md not found")
    parts = rel_path.strip("/").split("/", 1)
    if len(parts) != 2 or parts[0] not in _doc_roots():
        # "project/rules/x" splits to ["project", "rules/x"] — remap.
        if len(parts) == 2 and parts[0] == "project":
            sub = parts[1].split("/", 1)
            if len(sub) == 2 and f"project/{sub[0]}" in _doc_roots():
                namespace, rest = f"project/{sub[0]}", sub[1]
            else:
                raise HTTPException(400, "path must start with agents/, rules/, skills/ or project/")
        else:
            raise HTTPException(400, "path must start with agents/, rules/, skills/ or project/")
    else:
        namespace, rest = parts
    root_dir = _doc_roots()[namespace]
    candidate = (root_dir / rest).resolve()
    if candidate.suffix != ".md":
        raise HTTPException(400, "only .md files are supported")
    if root_dir.resolve() not in candidate.parents:
        raise HTTPException(400, "invalid path")
    return candidate


@router.get("/api/docs/content")
def api_get_doc(path: str):
    file_path = _resolve_doc(path)
    if not file_path.is_file():
        raise HTTPException(404, f"not found: {path}")
    return JSONResponse({"path": path, "content": file_path.read_text()})


@router.put("/api/docs/content")
async def api_put_doc(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "JSON body required")
    path = str(payload.get("path") or "")
    content = payload.get("content")
    if content is None:
        raise HTTPException(400, "content is required")
    if len(str(content).encode("utf-8")) > 200 * 1024:
        raise HTTPException(400, "refusing to write more than 200KB")
    file_path = _resolve_doc(path)
    if not file_path.is_file():
        raise HTTPException(404, f"not found: {path}")
    file_path.write_text(str(content))
    return JSONResponse({"ok": True, "path": path})
