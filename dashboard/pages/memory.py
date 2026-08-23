"""Memory page: recall search across memory-db, vault and code-graph."""
from __future__ import annotations

from fastapi import APIRouter, Request
from pipa.recall import recall
from pipa import config

from . import render

router = APIRouter()


@router.get("/memory")
def memory_view(request: Request, q: str = ""):
    query = (q or "").strip()
    hits = []
    error = False
    if query:
        try:
            out = recall(query, project=config.find_project())
            hits = out.get("results", [])
        except Exception:
            hits, error = [], True
    return render(
        request,
        "memory.html",
        q=query,
        searched=bool(query),
        hits=hits,
        error=error,
    )
