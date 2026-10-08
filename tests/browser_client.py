"""Browser-simulating TestClient factory.

The dashboard refuses state-changing requests that do not prove they came from
its own page (dashboard/pages/security.py). httpx's TestClient sends neither
`Sec-Fetch-Site` nor `Origin`, so every test would 403. Rather than switch the
guard off for tests — which would leave the one thing most worth testing
unverified — these helpers send the headers a real browser sends.
"""
from __future__ import annotations

LOOPBACK_HOST = "127.0.0.1:8080"


def browser_headers(extra: dict | None = None) -> dict:
    """Headers a browser sends for a same-origin request."""
    headers = {
        "Host": LOOPBACK_HOST,
        "Origin": f"http://{LOOPBACK_HOST}",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
    }
    headers.update(extra or {})
    return headers


def browser_client(app, **kwargs):
    """TestClient that looks like a same-origin browser to the guard."""
    from fastapi.testclient import TestClient

    client = TestClient(app, **kwargs)
    client.headers.update(browser_headers())
    return client
