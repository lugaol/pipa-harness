"""Evals page: run tools/evals/run.py and render its JSON report."""
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

_LAST = None  # last run report, shown by GET until the next run


def _failure(detail: str) -> dict:
    return {"ok": False, "detail": detail[:400], "total": 0, "failed": 0, "rows": []}


def run_evals(timeout: int = _TIMEOUT_S) -> dict:
    """Run the eval runner; parse its JSON stdout into display rows."""
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
    if proc.returncode != 0:
        detail = proc.stdout.strip() or proc.stderr.strip() or f"exit {proc.returncode}"
        return _failure(f"evals failed — {detail}")
    try:
        report = json.loads(proc.stdout)
    except ValueError:
        return _failure("eval runner printed non-JSON output")
    rows = []
    for r in report.get("results", []):
        checks = [
            {"name": name.replace("_", " "), "ok": bool(v.get("pass", True))}
            for name, v in r.items()
            if isinstance(v, dict)
        ]
        rows.append({
            "file": str(r.get("file") or "?"),
            "checks": checks,
            "ok": all(c["ok"] for c in checks),
        })
    return {
        "ok": True,
        "detail": "",
        "total": int(report.get("total", len(rows))),
        "failed": int(report.get("failed", 0)),
        "rows": rows,
    }


@router.get("/evals")
def evals_view(request: Request):
    return render(request, "evals.html", result=_LAST)


@router.post("/api/evals/run")
def evals_run(request: Request):
    # sync def → FastAPI offloads the 60s subprocess to the threadpool,
    # keeping the event loop (and /api/health) responsive
    global _LAST
    try:
        _LAST = run_evals()
    except Exception as exc:  # defensive: page must never 500
        _LAST = _failure(str(exc))
    return render(request, "evals.html", result=_LAST)
