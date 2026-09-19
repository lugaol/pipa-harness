"""Install — staged component setup (JS + JSON API, ia framework)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from data import installer as installer_data
from . import form_fields, render

router = APIRouter()


@router.get("/install")
def install_view(request: Request):
    return render(request, "install.html")


@router.post("/api/install/run")
async def install_run(request: Request):
    fields: dict = {}
    body = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            fields = body
    except Exception:
        fields = await form_fields(request)
    result = installer_data.run_install(str(fields.get("component", "")))
    if isinstance(body, dict):
        return JSONResponse({**result,
                             "detail": result.get("error") or f"job started: {result.get('label', '')}"})
    if not result.get("ok"):
        from urllib.parse import quote

        return RedirectResponse(
            f"/install?error={quote(str(result.get('error', 'failed'))[:200])}",
            status_code=303,
        )
    return RedirectResponse("/install?started=1", status_code=303)


@router.get("/api/install/log")
def install_log():
    return JSONResponse(installer_data.snapshot())
