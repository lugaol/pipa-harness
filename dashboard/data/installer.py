"""Background job runner for Install-page actions (single-flight).

Every job shells out to `python -m pipa install <component>` — the same
code path as the CLI — so retry-after-failure is just "click again".
stdout/stderr merge into a ring buffer with secret values from the
environment scrubbed before buffering: a leaked key can never reach the
browser. Ported from ia_harness dashboard/services/installer.py.
"""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
import threading
import time
from collections import deque
from typing import List

MAX_LINES = 2000

_lock = threading.Lock()
_job = {
    "running": False,
    "label": "",
    "cmd": [],
    "exit_code": None,
    "started_at": None,
    "finished_at": None,
    "lines": deque(maxlen=MAX_LINES),
}


def secret_values() -> List[str]:
    """Current secret values worth masking (env only, never logged)."""
    try:
        from pipa.providers import PROVIDERS

        names = {k for p in PROVIDERS.values() for k in p.requires}
    except Exception:
        names = set()
    names |= {"LITELLM_KEY"}
    vals = [os.environ.get(n, "") for n in names]
    return sorted({v for v in vals if v and len(v) >= 6},
                  key=len, reverse=True)


def scrub(line: str, secrets: List[str] | None = None) -> str:
    for s in secrets if secrets is not None else secret_values():
        line = line.replace(s, "***")
    return line


def snapshot() -> dict:
    return {
        "running": _job["running"],
        "label": _job["label"],
        "cmd": list(_job["cmd"]),
        "exit_code": _job["exit_code"],
        "started_at": _job["started_at"],
        "finished_at": _job["finished_at"],
        "lines": list(_job["lines"]),
    }


def _reader(proc: "subprocess.Popen[str]", secrets: List[str]) -> None:
    for raw in iter(proc.stdout.readline, ""):
        _job["lines"].append(scrub(raw.rstrip("\n"), secrets))
    proc.stdout.close()
    proc.wait()
    with _lock:
        _job["running"] = False
        _job["exit_code"] = proc.returncode
        _job["finished_at"] = time.time()


def run(label: str, cmd: list[str]) -> dict:
    """Start cmd as the single active job; refuse while one runs."""
    from pipa import config

    with _lock:
        if _job["running"]:
            return {"ok": False,
                    "error": f"another job is still running: {_job['label']}",
                    **snapshot()}
        cmd = [str(c) for c in cmd]
        try:
            proc = subprocess.Popen(
                cmd, cwd=str(config.harness_root()),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors="replace", start_new_session=True,
            )
        except OSError as exc:
            return {"ok": False,
                    "error": f"failed to start {shlex.join(cmd)}: {exc}",
                    **snapshot()}
        secrets = secret_values()
        _job.update(running=True, label=label, cmd=cmd, proc=proc,
                    exit_code=None, started_at=time.time(), finished_at=None)
        _job["lines"].clear()
        _job["lines"].append(f"$ {shlex.join(cmd)}")
        threading.Thread(target=_reader, args=(proc, secrets),
                         daemon=True).start()
        return {"ok": True, **snapshot()}


def run_install(component: str) -> dict:
    """Queue `python -m pipa install <component>` (unknown → error)."""
    from pipa.commands.install import INSTALL_COMPONENTS

    if component not in INSTALL_COMPONENTS:
        return {"ok": False,
                "error": f"unknown component '{component}'",
                **snapshot()}
    return run(f"install {component}",
               [sys.executable, "-m", "pipa", "install", component])
