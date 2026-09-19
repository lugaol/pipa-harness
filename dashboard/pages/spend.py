"""Redirect: /spend -> /observability?tab=spend (backwards compat)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

router = APIRouter()


@router.get("/spend")
def spend_view(request: Request, since: str = ""):
    url = "/observability?tab=spend"
    if since.strip():
        url += f"&since={since.strip()}"
    return RedirectResponse(url=url, status_code=307)
