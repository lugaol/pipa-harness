"""JSON API: code-graph (graphify) status, search, rebuild.

Split out of api.py (Phase A.3). Routes byte-identical — no behavior change.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/api/graph/stats")
def api_graph_stats(project: str = ""):
    from data import graph as graph_data

    st = graph_data.status(project or None)
    return JSONResponse({"ok": st["has_graph"], **st})


@router.get("/api/graph/search")
def api_graph_search(q: str = "", project: str = ""):
    from data import graph as graph_data

    if not q.strip():
        raise HTTPException(400, "q is required")
    result = graph_data.query(q, project or None)
    hits = [{
        "title": h.get("title") or "",
        "detail": h.get("detail") or "",
        "path": h.get("path") or "",
        "score": h.get("score") or 0,
    } for h in result.get("hits") or []]
    return JSONResponse({"query": q, "hits": hits,
                         "cli_out": result.get("cli_out") or "",
                         "cli_err": result.get("cli_err") or "",
                         "has_graph": result["status"]["has_graph"]})


@router.post("/api/graph/refresh")
def api_graph_refresh(project: str = ""):
    """Rebuild graphify-out/graph.json via the graphify CLI (best-effort)."""
    import shutil
    import subprocess

    from pipa import config

    binary = shutil.which("graphify")
    if not binary:
        return JSONResponse({"ok": False,
                             "detail": "graphify CLI not installed (pipa install graphify)"})
    root = project or str(config.find_project() or config.harness_root())
    try:
        proc = subprocess.run(
            [binary, "extract", "."], cwd=root,
            capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return JSONResponse({"ok": False, "detail": "graphify extract timed out after 300s"})
    except OSError as exc:
        return JSONResponse({"ok": False, "detail": str(exc)[:200]})
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip()[-500:]
    if proc.returncode != 0:
        return JSONResponse({"ok": False, "detail": tail or f"exit {proc.returncode}"})
    return JSONResponse({"ok": True, "detail": tail or "graph rebuilt"})
