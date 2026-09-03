"""Service-control actions for the dashboard, bridging pipa.services.

Pages never spawn processes directly: they call gateway_restart() /
ollama_start() which reuse the state/ pid files and capture Reporter
output into a flashable message. Every failure degrades to (False, msg).
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import List, Tuple

from pipa import config, services


class _Capture(services.Reporter):
    """Reporter that collects messages instead of printing them."""

    def __init__(self) -> None:
        super().__init__()
        self.messages: List[str] = []

    def ok(self, msg: str) -> None:
        self.messages.append(msg)

    def add(self, msg: str) -> None:
        self.messages.append(msg)

    def warn(self, msg: str) -> None:
        self.messages.append(msg)


def _pid_alive(pid_file: Path) -> bool:
    if not pid_file.exists():
        return False
    try:
        os.kill(int(pid_file.read_text().strip()), 0)
        return True
    except Exception:
        return False


def _stop_by_pid(pid_file: Path, seconds: int = 10) -> bool:
    try:
        os.kill(int(pid_file.read_text().strip()), 15)
    except Exception:
        return False
    deadline = time.time() + seconds
    while time.time() < deadline:
        if not _pid_alive(pid_file):
            return True
        time.sleep(0.3)
    return not _pid_alive(pid_file)


def gateway_restart() -> Tuple[bool, str]:
    """Stop the litellm pid (if alive), recompose config, start it again."""
    rep = _Capture()
    try:
        pid_file = config.state_dir() / "litellm.pid"
        if _pid_alive(pid_file) and not _stop_by_pid(pid_file):
            return False, "gateway restart failed — old process did not stop"
        effective, warning = config.compose_litellm_config()
        ok = services.start_litellm(rep, effective)
        msg = "; ".join(rep.messages)
        if warning:
            msg = f"{warning} — {msg}" if msg else warning
        return ok, msg or ("gateway restarted" if ok else "gateway did not come up")
    except Exception as exc:
        return False, f"gateway restart failed: {exc}"


def ollama_start() -> Tuple[bool, str]:
    rep = _Capture()
    try:
        ok = services.start_ollama(rep)
    except Exception as exc:
        return False, f"ollama start failed: {exc}"
    msg = "; ".join(rep.messages)
    return ok, msg or ("ollama running" if ok else "ollama did not come up")
