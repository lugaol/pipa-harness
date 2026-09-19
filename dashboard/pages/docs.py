"""Rules & Skills — docs browser screen (JS + JSON API)."""
from __future__ import annotations

from fastapi import APIRouter, Request

from . import render

router = APIRouter()


@router.get("/docs")
def docs_view(request: Request):
    return render(request, "docs.html")
