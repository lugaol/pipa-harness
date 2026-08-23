"""Shared Jinja2 environment + helpers for dashboard pages.

Templates live in templates/, reusable partials in fragments/. The
ChoiceLoader lets any template `{% include %}` a fragment without knowing
the caller. Autoescape is on (FastAPI/starlette default).
"""
from __future__ import annotations

import urllib.parse
from pathlib import Path

from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader

DASHBOARD_DIR = Path(__file__).resolve().parent.parent

templates = Jinja2Templates(directory=str(DASHBOARD_DIR / "templates"))
templates.env.loader = ChoiceLoader([
    templates.env.loader,
    FileSystemLoader(str(DASHBOARD_DIR / "fragments")),
])


def render(request, name: str, **context):
    """TemplateResponse shorthand that always passes the request."""
    return templates.TemplateResponse(
        request=request, name=name, context=context
    )


async def form_fields(request) -> dict:
    """Parse an application/x-www-form-urlencoded POST body.

    Hand-rolled instead of request.form() to avoid a hard dependency on
    python-multipart (plain HTML forms are urlencoded by default).
    """
    body = (await request.body()).decode("utf-8", "replace")
    pairs = urllib.parse.parse_qs(body, keep_blank_values=True)
    return {key: values[0] for key, values in pairs.items() if values}
