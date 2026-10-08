"""Evals — the agent behavioural contract, run on demand.

Reachable from Status. No top-level nav entry: it is not a daily surface, but
it must not be unreachable either — its own docstring used to claim "reachable
from Status" while nothing on the page linked to it.

Runs on GET rather than caching the last report in a module global. The old
`global _LAST` was shared by every browser that hit the endpoint, so two people
opening the page raced, and a second visitor silently saw the first visitor's
result. The suite is 39 checks over 9 files and finishes in milliseconds.
"""
from __future__ import annotations

import json
import subprocess
import sys

from fastapi import APIRouter, Request

from pipa import config

from . import render

router = APIRouter()

EVAL_SCRIPT = config.harness_root() / "tools" / "evals" / "run.py"
_TIMEOUT_S = 60


def _failure(detail: str) -> dict:
    return {"ok": False, "detail": detail[:400], "total": 0, "failed": 0, "rows": []}


def run_evals(timeout: int = _TIMEOUT_S) -> dict:
    """Run the eval runner; parse its JSON stdout into display rows.

    Reads `checks` (name -> {pass, msg}) from each result. It used to read
    top-level dict values, which silently dropped every boolean check — the
    same shape bug that made the runner report 0 failures.
    """
    if not EVAL_SCRIPT.is_file():
        return _failure(f"eval runner not found at {EVAL_SCRIPT}")
    try:
        proc = subprocess.run(
            [sys.executable, str(EVAL_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return _failure(f"eval runner timed out after {timeout}s")
    except OSError as exc:
        return _failure(f"could not launch eval runner: {exc}")
    try:
        report = json.loads(proc.stdout)
    except ValueError:
        return _failure("eval runner printed non-JSON output")
    if not isinstance(report, dict) or "results" not in report:
        return _failure("eval runner output has no 'results'")

    rows = []
    for r in report["results"]:
        checks = [
            {"name": name.replace("_", " "), "ok": bool(c.get("pass")), "msg": c.get("msg", "")}
            for name, c in (r.get("checks") or {}).items()
        ]
        rows.append({
            "file": str(r.get("file") or "?"),
            "checks": checks,
            "ok": bool(checks) and all(c["ok"] for c in checks),
        })
    return {
        "ok": True,
        "detail": "",
        "total": int(report.get("total", sum(len(r["checks"]) for r in rows))),
        "failed": int(report.get("failed", 0)),
        "rows": rows,
    }


@router.get("/evals")
def evals_view(request: Request):
    try:
        result = run_evals()
    except Exception as exc:  # noqa: BLE001 — a broken runner is a result, not a 500
        result = _failure(f"{type(exc).__name__}: {exc}")
    return render(request, "evals.html", result=result)