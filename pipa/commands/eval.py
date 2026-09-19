"""pipa eval — run agent evals (tools/evals/run.py) + routing eval (evals/validate.py)."""
from __future__ import annotations

import subprocess
import sys

from pipa import config


def _die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def cmd_eval(args) -> int:
    root = config.harness_root()
    script = root / "tools" / "evals" / "run.py"
    if not script.exists():
        _die(f"eval runner not found: {script}")
    rc = subprocess.run([sys.executable, str(script), *args.eval_args]).returncode
    routing = root / "evals" / "validate.py"
    if routing.exists():
        rc2 = subprocess.run([sys.executable, str(routing)]).returncode
        rc = rc or rc2
    return rc
