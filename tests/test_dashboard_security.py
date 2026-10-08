"""The dashboard must not accept commands from other origins.

The dashboard has no accounts, no cookies and no session. It binds 127.0.0.1 and
trusts whatever reaches the socket — which is fine until a browser is pointed at
it, because then any page the user has open can auto-POST to 127.0.0.1:8080 and
rewrite AGENTS.md, write provider API keys into $PIPA_ROOT/.env, recompose the
gateway config, shell out to `pipa install`, or spawn graphify.

There is no CSRF token to steal here (there is nothing to steal), so a token
would be theatre. The control is: prove the request came from this app.
These tests pin that, plus the two ways it could be bypassed by accident —
a permissive middleware, or a router that reads the socket directly.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import re
import sys
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parents[1]
DASHBOARD = HARNESS / "dashboard"
for _p in (str(HARNESS), str(DASHBOARD)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytest.importorskip("httpx")

from browser_client import browser_headers  # noqa: E402

WRITE_ROUTES = [
    ("POST", "/api/env-keys"),
    ("POST", "/api/services/gateway/restart"),
    ("POST", "/api/gateway/rebuild"),
    ("POST", "/api/install/run"),
    ("PUT", "/api/docs/content"),
    ("PUT", "/api/tier-models"),
    ("POST", "/api/mcp/toggle"),
    ("POST", "/context/save"),
    ("POST", "/knowledge/delete"),
    ("POST", "/api/graph/refresh"),
]


def _app():
    import server

    return server.create_app()


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("PIPA_DASHBOARD_TRUST_CLI", "1")
    return TestClient(_app(), raise_server_exceptions=False)


@pytest.mark.parametrize("method,path", WRITE_ROUTES)
def test_cross_origin_write_is_refused(client, method, path):
    """A page on another site must not be able to drive the dashboard."""
    r = client.request(method, path, headers={
        "Host": "127.0.0.1:8080",
        "Origin": "https://evil.example",
        "Sec-Fetch-Site": "cross-site",
    })
    assert r.status_code == 403, f"{method} {path} accepted a cross-origin write"


@pytest.mark.parametrize("method,path", WRITE_ROUTES)
def test_sec_fetch_site_cross_site_alone_is_refused(client, method, path):
    """Sec-Fetch-Site is browser-enforced and cannot be set by page JS."""
    r = client.request(method, path, headers=browser_headers({
        "Sec-Fetch-Site": "cross-site",
    }))
    assert r.status_code == 403, f"{method} {path} ignored Sec-Fetch-Site"


def test_dns_rebinding_host_is_refused(client):
    """An attacker domain resolving to 127.0.0.1 must not be served.

    This is the case an Origin check alone misses: the browser considers the
    request same-origin because the page *is* evil.example, while the socket is
    local. Only a loopback Host check catches it.
    """
    r = client.post("/api/services/gateway/restart", headers={
        "Host": "evil.example",
        "Origin": "http://evil.example",
        "Sec-Fetch-Site": "same-origin",
    })
    assert r.status_code == 403
    assert "loopback" in r.text.lower()


def test_reads_are_not_blocked(client):
    """The guard is about writes; GET must keep working."""
    for path in ("/", "/api/status", "/models", "/observability"):
        r = client.get(path, headers=browser_headers())
        assert r.status_code == 200, path


def test_same_origin_write_is_allowed(client):
    """A real browser request from our own page must not be refused."""
    r = client.post("/api/mcp/toggle", headers=browser_headers(), data={})
    assert r.status_code in (200, 303, 400, 422), r.status_code


def test_non_browser_client_requires_explicit_opt_in(monkeypatch):
    """curl sends neither header — refuse unless the operator opts in.

    Otherwise the guard is trivially bypassed by anything that is not a
    browser, and the whole point is that reaching the socket is not enough.
    """
    from fastapi.testclient import TestClient

    monkeypatch.delenv("PIPA_DASHBOARD_TRUST_CLI", raising=False)
    c = TestClient(_app(), raise_server_exceptions=False)
    r = c.post("/api/services/gateway/restart", headers={"Host": "127.0.0.1:8080"})
    assert r.status_code == 403
    assert "PIPA_DASHBOARD_TRUST_CLI" in r.text

    monkeypatch.setenv("PIPA_DASHBOARD_TRUST_CLI", "1")
    r = c.post("/api/services/gateway/restart", headers={"Host": "127.0.0.1:8080"})
    assert r.status_code != 403


def test_security_headers_are_attached(client):
    r = client.get("/", headers=browser_headers())
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    csp = r.headers["content-security-policy"]
    assert "script-src 'self'" in csp, (
        "a sanitiser bypass must not be able to execute script"
    )
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp


def test_every_state_changing_route_is_behind_the_guard():
    """Structural: the middleware is installed on the app, not per-route.

    A per-route dependency is one forgotten decorator away from an open door.
    """
    app = _app()
    assert app.user_middleware, "no HTTP middleware installed"
    dispatches = [
        m.kwargs.get("dispatch") for m in app.user_middleware
        if hasattr(m, "kwargs") and m.kwargs
    ]
    names = [getattr(d, "__name__", None) for d in dispatches if d]
    assert "same_origin_guard" in names, (
        f"same_origin_guard middleware missing; installed: {names or app.user_middleware}"
    )


def test_no_route_handles_writes_without_the_middleware(monkeypatch):
    """Regression against a future `app = FastAPI()` in another entrypoint."""
    text = (DASHBOARD / "server.py").read_text()
    assert "same_origin_guard" in text
    assert text.count("FastAPI(") == 1, (
        "a second app instance would not inherit the middleware"
    )

def test_destructive_forms_do_not_embed_filenames_in_javascript():
    """A quote in a filename must not break the delete confirmation.

    Regression: `onsubmit="return confirm('Delete {{ path }}?')"`. Jinja escapes
    the apostrophe to `&#39;`; the HTML parser DECODES it back to a quote before
    the JS parser runs, so a note named `it's-bad.md` produced a syntax error,
    `confirm()` never ran, and the form submitted anyway — the file was deleted
    with no prompt. Any user-controlled string inside inline script is a
    double-decoding trap.
    """
    import re

    from pages import templates

    tpl = templates.env.from_string(
        (DASHBOARD / "templates" / "_entry_table.html").read_text()
    )
    html = tpl.render(
        entries=[{"path_rel": "it's-bad.md", "mtime_h": "x", "size_h": "y"}],
        tier="vault", tab="rules",
    )
    assert "onsubmit" not in html, "no inline script may carry a filename"
    m = re.search(r'data-confirm="([^"]*)"', html)
    assert m, "the confirmation message must live in data-confirm"
    assert "Delete it&#39;s-bad.md?" in m.group(1), m.group(1)


def test_confirm_guard_is_installed():
    """The delegated handler that reads data-confirm must exist and be wired."""
    js = (DASHBOARD / "static" / "js" / "common.js").read_text()
    assert "data-confirm" in js or "dataset.confirm" in js, (
        "nothing reads data-confirm — deleting would happen with no prompt"
    )
    assert "installConfirmGuards" in js
    assert re.search(r"installConfirmGuards\(\)", js), (
        "installConfirmGuards must actually be called from init()"
    )


def test_no_template_embeds_user_data_in_inline_handlers():
    """Sweep every template: no `on*=` attribute may interpolate a path/title.

    Inline handlers are decoded before evaluation, so Jinja escaping is not
    sufficient there. Any such attribute is a latent double-decoding bug.
    """
    import re

    offenders = []
    for html in list((DASHBOARD / "templates").glob("*.html")) + \
            list((DASHBOARD / "fragments").glob("*.html")):
        for n, line in enumerate(html.read_text().splitlines(), 1):
            for m in re.finditer(r'on(click|submit|change|input)=["\']([^"\']*)["\']', line):
                if "{{" in m.group(2):
                    offenders.append(f"{html.name}:{n} {m.group(0)[:70]}")
    assert not offenders, (
        "user-controlled data interpolated into an inline JS handler "
        "(HTML-decoded before evaluation):\n  " + "\n  ".join(offenders)
    )


def test_docs_viewer_uses_an_allowlist_sanitiser():
    """The docs viewer renders repo markdown into innerHTML.

    A blocklist cannot be complete. Assert the sanitiser is allowlist-shaped:
    it must name a set of permitted tags and rebuild nodes, rather than only
    subtracting known-bad ones.
    """
    js = (DASHBOARD / "static" / "js" / "pages" / "docs.js").read_text()
    assert "DOC_SAFE_TAGS" in js or "SAFE_TAGS" in js, (
        "sanitiser must declare an explicit allowlist of tags"
    )
    assert "DOMParser" in js, "an allowlist sanitiser should rebuild via DOMParser"
    for banned in ("form", "svg", "math", "style"):
        assert banned in js, f"the allowlist must explicitly exclude <{banned}>"


# ── the deadcode gate itself ───────────────────────────────────────────────
# A gate that cannot fail is worse than no gate: it reports "ok" and the
# residue it was written to catch walks back in.

def _deadcode_rc() -> int:
    """Run `pipa-check deadcode` in-process and return its exit code."""
    import contextlib
    import importlib.util
    import io

    spec = importlib.util.spec_from_loader(
        "pipa_check_mod",
        importlib.machinery.SourceFileLoader(
            "pipa_check_mod", str(HARNESS / "bin" / "pipa-check")
        ),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return mod.check_deadcode()


def test_deadcode_gate_passes_on_a_clean_tree():
    assert _deadcode_rc() == 0, "the tree should be free of dashboard dead code"


def test_deadcode_gate_catches_an_unread_context_value(tmp_path):
    """The gate must FAIL when a page passes a value its template ignores."""
    page = DASHBOARD / "pages" / "knowledge.py"
    orig = page.read_text()
    page.write_text(orig.replace("groups=_grouped(notes),",
                                 "groups=_grouped(notes), notes=notes,", 1))
    try:
        assert _deadcode_rc() == 1, (
            "deadcode gate did not notice a context value the template "
            "never reads"
        )
    finally:
        page.write_text(orig)


def test_deadcode_gate_catches_a_dead_stylesheet_link():
    tpl = DASHBOARD / "templates" / "overview.html"
    orig = tpl.read_text()
    tpl.write_text(orig.replace(
        "{% block content %}",
        '{% block content %}\n<link rel="stylesheet" href="/static/css/pages/nope.css">',
        1))
    try:
        assert _deadcode_rc() == 1, "deadcode gate did not notice a 404 stylesheet"
    finally:
        tpl.write_text(orig)


def test_deadcode_gate_does_not_flag_used_context():
    """Guard against the false positive that shipped first.

    Stripping `{% %}` tags flagged every list a template iterates, and
    matching bare words flagged prose: `{% with message='No notes in this
    scope yet.' %}` made a genuinely-used `notes` look dead.
    """
    # `groups` is consumed only by `{% for group, rows in groups %}`
    kt = (DASHBOARD / "templates" / "knowledge.html").read_text()
    assert "{% for group, rows in groups %}" in kt, "fixture drifted"
    kp = (DASHBOARD / "pages" / "knowledge.py").read_text()
    assert "groups=_grouped(notes)" in kp, "fixture drifted"
    assert _deadcode_rc() == 0


# ── CSP compatibility: no inline event handlers ────────────────────────────

INLINE_HANDLER = re.compile(r"\son[a-z]+\s*=\s*[\"']", re.IGNORECASE)


def test_no_inline_event_handlers_under_csp():
    """The CSP has no 'unsafe-inline', so an inline on* attribute never runs.

    The browser refuses it silently — the button just does nothing. That is
    exactly the "no dashboard button works" failure: every static onclick was
    dead while the API tests passed. Actions go through data-action (or
    data-submit-form) and the delegated dispatcher in common.js; this scan
    keeps new inline handlers from coming back.
    """
    offenders = []
    for root in (DASHBOARD / "templates", DASHBOARD / "static" / "js"):
        for f in sorted(root.rglob("*")):
            if f.suffix not in (".html", ".js"):
                continue
            for n, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                if INLINE_HANDLER.search(line):
                    offenders.append(f"{f.relative_to(DASHBOARD)}:{n}")
    assert not offenders, (
        "inline event handlers are blocked by the dashboard CSP and do "
        "nothing in a browser; use data-action / data-submit-form:\n  "
        + "\n  ".join(offenders)
    )
