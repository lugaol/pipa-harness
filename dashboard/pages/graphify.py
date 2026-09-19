"""Graph — code-graph search/status/rebuild screen (JS + JSON API)."""
from __future__ import annotations

from fastapi import APIRouter, Request

from . import render

router = APIRouter()


@router.get("/graphify")
def graphify_view(request: Request):
    return render(request, "graph.html")
