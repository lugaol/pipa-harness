"""Tier Manager — ia-style tier -> model screen (JS + JSON API)."""
from __future__ import annotations

from fastapi import APIRouter, Request

from . import render

router = APIRouter()


@router.get("/tiers")
def tiers_view(request: Request):
    return render(request, "tiers.html")
