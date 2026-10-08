"""`pipa check` — thin CLI wrapper over bin/pipa-check.

The script is the single implementation so the harness and a human run
identical logic. This module only resolves the script path and forwards argv,
which keeps one source of truth for what "enforced" actually means.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pipa import config


def _script() -> Path | None:
    """Locate bin/pipa-check next to the harness root."""
    for base in (config.harness_root(), Path(__file__).resolve().parent.parent):
        candidate = base / "bin" / "pipa-check"
        if candidate.is_file():
            return candidate
    return None


def cmd_check(args) -> int:
    script = _script()
    if script is None:
        print("  [!!] bin/pipa-check not found next to the harness", file=sys.stderr)
        print("      looked in:", config.harness_root() / "bin", file=sys.stderr)
        return 1
    argv = [str(script)]
    argv += [str(w) for w in (args.which or ["all"])]
    if getattr(args, "install_hooks", False):
        argv = [str(script), "install-hooks"]
    return subprocess.call(argv)
