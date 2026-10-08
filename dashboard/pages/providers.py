"""Providers — API-key inventory (names only) + per-provider checks."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from data import providers as providers_data
from . import form_fields, render

router = APIRouter()


@router.get("/providers")
def providers_view(request: Request):
    try:
        rows = providers_data.list_providers()
    except Exception:
        rows = []
    return render(
        request,
        "providers.html",
        rows=rows,
        tested=request.query_params.get("tested", ""),
        test_ok=request.query_params.get("ok", "") != "0",
        test_msg=request.query_params.get("msg", ""),
    )


@router.post("/api/providers/test")
async def test_provider(request: Request):
    fields = await form_fields(request)
    slug = str(fields.get("provider", ""))
    try:
        ok, msg = providers_data.test_provider(slug)
    except Exception as exc:
        ok, msg = False, str(exc)[:200]
    return RedirectResponse(
        f"/providers?tested={quote(slug[:60])}&ok={'1' if ok else '0'}"
        f"&msg={quote(msg[:300])}",
        status_code=303,
    )
