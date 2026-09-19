"""pipa status — health check (gate-friendly exit code)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from pipa import config, runtime as runtimes, scaffold, services, session


def _say(msg: str = "") -> None:
    print(msg)


def cmd_status(args) -> int:
    root = config.harness_root()
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "status": "pass" if ok else "fail", "detail": detail})

    models: list[str] = []
    url = f"{config.LITELLM_URL}/v1/models"
    import urllib.request
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {config.LITELLM_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            models = [m["id"] for m in json.load(r).get("data", [])]
        check("litellm", True, f"{len(models)} models: {', '.join(models[:4])}")
    except Exception:
        check("litellm", False, "gateway not reachable")

    found = runtimes.installed()
    check("runtime", bool(found), f"installed: {', '.join(found)}" if found else "no runtime on PATH")

    check("graphify-cli", services.have("graphify"), "installed" if services.have("graphify") else "not on PATH")

    project = config.find_project()
    if project and project != root and config.pipa_dir(project).exists():
        rt = runtimes.read_project_runtime(project) or "auto"
        check("project", True, f"{project} (runtime: {rt})")
        for ok, msg in scaffold.check_extension(project):
            check(f"ext:{msg.split(' ')[0]}", ok, msg)
        g = project / "graphify-out" / "graph.json"
        check("graphify-graph", g.exists(),
              "graph.json present" if g.exists() else "no graph yet — run: graphify extract .")
        log = config.session_log_path(project)
        if log.exists():
            s = session.stats(log)
            check("session-log", True, f"{s['events']} events, last: {s['last_ts']}")
    else:
        check("project", config.git_root() is not None,
              "not inside a pipa project" if project == root else "not a git repo")

    summary = {
        "pass": sum(1 for c in checks if c["status"] == "pass"),
        "fail": sum(1 for c in checks if c["status"] == "fail"),
    }
    if getattr(args, "json", False):
        print(json.dumps({"checks": checks, "summary": summary, "timestamp": time.time()}))
    else:
        for c in checks:
            mark = "PASS" if c["status"] == "pass" else "FAIL"
            _say(f"  [{mark}] {c['name']}: {c['detail']}")
        _say(f"\n  {summary['pass']} pass, {summary['fail']} fail")
    return 0 if summary["fail"] == 0 else 1
