"""Agents page: one card per discovered agent definition."""
from __future__ import annotations

from fastapi import APIRouter, Request

from data import agents as agents_data
from . import render

router = APIRouter()


@router.get("/agents")
def agents_view(request: Request):
    try:
        agents = agents_data.discover_agents()
    except Exception:
        agents = []
    return render(request, "agents.html", agents=agents)
