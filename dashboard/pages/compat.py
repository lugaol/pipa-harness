"""Backwards-compatible redirects for routes retired by the 10 -> 5 nav merge.

The merge moved Sessions+Spend into Observability, Memory+Graph into Knowledge,
and Projects into Status. Old bookmarks kept working, which is worth keeping —
but it was kept by *retaining whole page modules*, and those modules carried
the retired page's duplicate handlers with them:

  pages/memory.py     re-registered /memory/save|delete|expiry (Knowledge owns
                      them at /knowledge/*) against a memory.html template that
                      no renderer ever loaded. 101 lines, zero reachable calls.
  pages/sessions.py   re-registered /sessions/{sid}, a verbatim copy of
                      observability.py's session detail. 71 lines.
  pages/projects.py   re-registered POST /projects/runtime, which
                      overview.py already owns. server.py includes routers in
                      alphabetical order, so overview won and this handler was
                      unreachable -- but the two read DIFFERENT form fields
                      ("project" vs "path"). One alphabetical reshuffle away
                      from being live, and it would have failed closed with no
                      visible error.
  pages/graph.py, pages/spend.py   pure redirects already.

So: redirects stay (cheap, deliberate compat), duplicates go. Every path
below is a GET that no template or JS in this repo emits any more.

If a retired POST ever needs to keep working, give it one owner here rather
than restoring the page module -- and read the same field names the live form
actually posts.
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

router = APIRouter()

# Old path -> (new path, param passthroughs). 307 keeps the method and body.
_REDIRECTS = {
    "/sessions": ("/observability", ("tab",)),
    "/spend": ("/observability", ("tab",)),
    "/memory": ("/knowledge", ("tab", "scope", "proj", "q")),
    "/memory/edit": ("/knowledge/edit", ("scope", "path", "name", "proj")),
    "/graph": ("/knowledge", ("tab",)),
    "/projects": ("/", ()),
    "/extensions": ("/", ()),
}

# Retired paths that pin a tab, so /memory lands on the Memory tab rather than
# the page default.
_TAB_DEFAULTS = {"/sessions": "sessions", "/spend": "spend",
                 "/memory": "memory", "/graph": "graph"}


def _passthrough(request: Request, keys: tuple[str, ...]) -> str:
    params = request.query_params
    out = []
    for key in keys:
        value = params.get(key)
        if value:
            out.append(f"{key}={quote(value)}")
    return ("?" + "&".join(out)) if out else ""


def _make_redirect(old: str, new: str, keys: tuple[str, ...]):
    def handler(request: Request):
        query = _passthrough(request, keys)
        tab = _TAB_DEFAULTS.get(old)
        if tab and "tab=" not in query:
            query = f"?tab={tab}" if not query else f"{query}&tab={tab}"
        return RedirectResponse(url=f"{new}{query}", status_code=307)

    handler.__name__ = f"compat_{old.strip('/').replace('/', '_') or 'root'}"
    return handler


for _old, (_new, _keys) in _REDIRECTS.items():
    router.add_api_route(
        _old, _make_redirect(_old, _new, _keys), methods=["GET"],
    )

del _old, _new, _keys

# POST /projects/runtime is deliberately NOT here. It has a live owner:
# pages/overview.py, which reads both field names the two historical forms
# used ("project" and "path"). Registering it a second time only recreates the
# shadowing that made it unreachable in the first place — server.py includes
# routers alphabetically, so whichever module sorted first silently won.