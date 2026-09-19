"""Redirect: /graph -> /knowledge?tab=graph (backwards compat)."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

router = APIRouter()


@router.get("/graph")
def graph_view(request: Request, q: str = "", proj: str = ""):
    params = "?tab=graph&scope=global"
    if q.strip():
        params += f"&gq={quote(q.strip())}"
    if proj:
        params += f"&proj={quote(proj)}"
    return RedirectResponse(url=f"/knowledge{params}", status_code=307)
