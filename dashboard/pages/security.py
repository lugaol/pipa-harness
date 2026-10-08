"""Same-origin guard for state-changing requests.

The dashboard has no accounts, no cookies and no session — it binds 127.0.0.1
and trusts whatever reaches it. That is fine until a browser is pointed at it:
because no credential is required, ANY page the user has open can auto-POST to
127.0.0.1:8080 and

  * rewrite the harness contract (`PUT /api/docs/content` -> AGENTS.md,
    rules/*, skills/*),
  * write attacker-chosen provider keys into `$PIPA_ROOT/.env`,
  * recompose the gateway config and restart the proxy,
  * shell out to `pipa install <component>`,
  * spawn `graphify extract`.

There is no CSRF *token* to steal here, because there is nothing to steal —
so a token would be theatre. The correct control for "a service that requires
no credentials" is to require that the request actually came from this app:
prove same-origin, then prove the Host is a loopback name.

Three signals, checked in order, any one of which is sufficient:

  1. `Sec-Fetch-Site` (browser-enforced, cannot be set by page JS):
     `same-origin`/`none` passes, `cross-site` is refused.
  2. `Origin`: must match the request's own Host, scheme included.
  3. `Host`: must be a loopback name. Refusing anything else blocks DNS
     rebinding, where an attacker's domain resolves to 127.0.0.1 and `Host`
     carries their domain — Origin would look "same" to the browser while the
     socket is local.

Browsers send at least one of (1)/(2) on every state-changing request. A
client that sends neither is not a browser: allow it only when
PIPA_DASHBOARD_TRUST_CLI=1, so curl and the test suite keep working and a
misconfiguration is an explicit opt-in rather than a default.
"""
from __future__ import annotations

import os
import re

from fastapi import Request
from fastapi.responses import JSONResponse, PlainTextResponse

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
LOOPBACK_HOST = re.compile(
    r"^(localhost|127(?:\.\d{1,3}){3}|\[::1\]|::1)(:\d+)?$", re.IGNORECASE
)
TRUST_ENV = "PIPA_DASHBOARD_TRUST_CLI"


def _host(request: Request) -> str:
    return request.headers.get("host", "")


def _origin_allowed(request: Request) -> bool:
    """True when Origin names this same host."""
    origin = request.headers.get("origin")
    if not origin:
        return True  # nothing to compare; Sec-Fetch-Site may still have ruled
    return origin.rstrip("/").endswith(_host(request).lower())


def _fetch_site_allowed(request: Request) -> bool | None:
    """True/False from Sec-Fetch-Site, or None when the browser didn't send it."""
    value = request.headers.get("sec-fetch-site")
    if value is None:
        return None
    return value.lower() in ("same-origin", "none")


def trust_unattributed_clients() -> bool:
    """Opt-in escape hatch for curl / the test suite."""
    return os.environ.get(TRUST_ENV, "") not in ("", "0", "false", "no")


def describe_violation(request: Request) -> str | None:
    """Why this request must be refused, or None if it is acceptable."""
    host = _host(request)
    if not LOOPBACK_HOST.match(host):
        return (
            f"Host {host!r} is not a loopback name — refusing. The dashboard "
            f"manages local files and services and must not answer for another "
            f"domain (DNS rebinding)."
        )
    site = _fetch_site_allowed(request)
    if site is False:
        return (
            "Sec-Fetch-Site: cross-site — this request came from another page. "
            "The dashboard does not accept commands from other origins."
        )
    if not _origin_allowed(request):
        return (
            f"Origin {request.headers.get('origin')!r} does not match Host "
            f"{host!r} — refusing a cross-origin request."
        )
    if site is None and not request.headers.get("origin") and not trust_unattributed_clients():
        return (
            "Neither Sec-Fetch-Site nor Origin was sent, and "
            f"{TRUST_ENV} is not set. Browsers always send one of these; a "
            "client that sends neither is not a browser."
        )
    return None


async def same_origin_guard(request: Request, call_next):
    """ASGI middleware: refuse cross-origin writes, add security headers."""
    if request.method.upper() not in SAFE_METHODS:
        reason = describe_violation(request)
        if reason:
            return PlainTextResponse(
                f"403 {reason}\n\nIf you are driving the dashboard from a script, "
                f"set {TRUST_ENV}=1.",
                status_code=403,
            )
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    # The docs viewer renders repo markdown through a sanitiser, and the app
    # loads `marked` from a CDN. `script-src 'self'` means a sanitiser bypass
    # in /docs cannot execute script, even though the CDN script is allowed.
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; object-src 'none'",
    )
    return response


def violation_response(reason: str) -> JSONResponse:
    return JSONResponse({"error": reason}, status_code=403)