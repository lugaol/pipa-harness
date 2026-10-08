"""pipa status — health check (gate-friendly exit code).

Also the single owner of SUBSYSTEM HEALTH. `collect_checks()` is the reusable
form; the dashboard adapts it rather than re-probing. It used to keep its own
copy, with three consequences: the same dead gateway read FAIL here, WARN in
`pipa doctor`, and red on the Status page; subsystem names drifted apart
("litellm" vs "litellm gateway" vs "gateway"), so a rename silently broke
lookups keyed on the string; and the dashboard's copy had no severity concept
at all, so it could not express the optional/fault distinction.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from pipa import config, runtime as runtimes, scaffold, services, session


def _say(msg: str = "") -> None:
    print(msg)


# Subsystems probed on every run, in display order. The dashboard keys its
# icons and actions off these exact names.
SUBSYSTEMS = ("litellm gateway", "ollama", "litellm binary", "graphify")


def collect_checks() -> list[dict]:
    """[{name, status, detail}] with status in pass|warn|fail.

    Pure enough to call from a web handler: no printing, no exit code.
    """
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "status": "pass" if ok else "fail", "detail": detail})

    def optional(name: str, ok: bool, detail: str = "") -> None:
        """An absent optional subsystem is a choice, not a fault.

        Reporting these as failures makes a fresh project's first health check
        look broken, which trains people to ignore red output.
        """
        checks.append({
            "name": name,
            "status": "pass" if ok else "warn",
            "detail": detail,
        })

    models: list[str] = []
    url = f"{config.LITELLM_URL}/v1/models"
    import urllib.request
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {config.LITELLM_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            models = [m["id"] for m in json.load(r).get("data", [])]
        check("litellm gateway", True,
              f"up at {config.LITELLM_URL} · {len(models)} models: "
              f"{', '.join(models[:4])}")
    except Exception:
        check("litellm gateway", False, "not reachable")

    import shutil as _shutil
    ollama_up = _shutil.which("ollama") is not None and _http_up(config.OLLAMA_URL)
    check("ollama", ollama_up,
          "running" if ollama_up else "not running (local models unavailable)")

    litellm_bin = _shutil.which("litellm")
    check("litellm binary", bool(litellm_bin),
          litellm_bin or "not on PATH")

    graphify_bin = _shutil.which("graphify")
    # Optional, consistent with graphify-graph below. Marking the binary hard
    # while its output is optional meant `pipa up` exited 1 on a machine where
    # the user had simply never indexed a graph — teaching people to ignore a
    # non-zero exit, which is exactly what the severity model exists to avoid.
    optional("graphify", bool(graphify_bin),
             graphify_bin or "not on PATH — run: pipa install graphify")

    found = runtimes.installed()
    check("runtime", bool(found), f"installed: {', '.join(found)}" if found else "no runtime on PATH")

    _tmux = _shutil.which("tmux")
    check("tmux", bool(_tmux), _tmux or "not on PATH — OmO Team Mode needs it (brew install tmux)")

    project = config.find_project()
    if project and project != root() and config.pipa_dir(project).exists():
        rt = runtimes.read_project_runtime(project) or "auto"
        check("project", True, f"{project} (runtime: {rt})")
        for ok, msg in scaffold.check_extension(project):
            check(f"ext:{msg.split(' ')[0]}", ok, msg)
        g = project / "graphify-out" / "graph.json"
        optional("graphify-graph", g.exists(),
                 "graph.json present" if g.exists()
                 else "optional: no code graph yet — enable with: graphify extract .")
        log = config.session_log_path(project)
        if log.exists():
            s = session.stats(log)
            check("session-log", True, f"{s['events']} events, last: {s['last_ts']}")
    else:
        check("project", config.git_root() is not None,
              "not inside a pipa project" if project == root() else "not a git repo")

    return checks


def _http_up(url: str, timeout: float = 2.0) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except Exception:
        return False


def root() -> Path:
    return config.harness_root()


def cmd_status(args) -> int:
    checks = collect_checks()

    summary = {
        "pass": sum(1 for c in checks if c["status"] == "pass"),
        "warn": sum(1 for c in checks if c["status"] == "warn"),
        "fail": sum(1 for c in checks if c["status"] == "fail"),
    }
    if getattr(args, "json", False):
        print(json.dumps({"checks": checks, "summary": summary, "timestamp": time.time()}))
    else:
        for c in checks:
            mark = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}.get(
                c["status"], "FAIL")
            _say(f"  [{mark}] {c['name']}: {c['detail']}")
        _say(f"\n  {summary['pass']} pass, {summary['warn']} warn, "
             f"{summary['fail']} fail")
    return 0 if summary["fail"] == 0 else 1
