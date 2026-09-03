"""Graph page: graphify knowledge-graph status + query UI."""
from __future__ import annotations

from fastapi import APIRouter, Request

from data import graph as graph_data
from . import render

router = APIRouter()


@router.get("/graph")
def graph_view(request: Request, q: str = "", proj: str = ""):
    st = graph_data.status(proj or None)
    result = graph_data.query(q, proj or None) if q.strip() else None
    return render(
        request,
        "graph.html",
        status=st,
        q=(q or "").strip(),
        result=result,
        proj=proj,
    )
