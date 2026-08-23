"""Projects page (route /extensions): registry table with enrichment counts."""
from __future__ import annotations

from fastapi import APIRouter, Request

from data import projects as projects_data
from . import render

router = APIRouter()

_COLUMNS = ["project", "path", "runtime", "rules", "skills", "memory", "status"]


@router.get("/extensions")
def projects_view(request: Request):
    try:
        projects = projects_data.list_projects()
    except Exception:
        projects = []
    rows = [
        {
            "cells": [
                p["name"],
                p["path"],
                p["runtime"],
                p["rules"],
                p["skills"],
                p["memory"],
                "ok" if p["exists"] else "missing",
            ]
        }
        for p in projects
    ]
    return render(
        request,
        "extensions.html",
        title="Projects",
        columns=_COLUMNS,
        rows=rows,
        count=len(rows),
    )
