#!/usr/bin/env python3
"""pipa_harness status — pre-session health check.
Verifies LiteLLM gateway, graphify, git, and (optionally) build tooling are ready.
Usage: python3 harness/bin/harness_status.py [--json] [--probe]
Exit code 1 if any check fails — usable as a pre-session gate.
"""
import json, os, subprocess, sys, time
from pathlib import Path

LITELLM_URL = os.environ.get("LITELLM_URL", "http://localhost:4000")
CHECKS = []

def check(name, ok, detail=""):
    CHECKS.append({"name": name, "status": "pass" if ok else "fail", "detail": detail})

def run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, ""

# LiteLLM gateway
ok, out = run(["curl", "-sf", f"{LITELLM_URL}/v1/models", "-H", "Authorization: Bearer sk-pipa-local"])
models = []
if ok:
    try:
        models = [m["id"] for m in json.loads(out).get("data", [])]
    except Exception:
        pass
check("litellm", ok, f"{len(models)} models: {', '.join(models[:4])}" if models else "gateway up, no models")

# graphify
gpath = Path(".graphifyignore").parent / "graphify-out" / "graph.json"
gok = gpath.exists()
check("graphify-graph", gok, "graph.json present" if gok else "no graph yet — run: graphify extract .")

# graphify CLI
ok, _ = run(["graphify", "--version"])
check("graphify-cli", ok, "installed" if ok else "not on PATH")

# git repo
ok, out = run(["git", "rev-parse", "--show-toplevel"])
check("git-repo", ok, out if ok else "not a git repo")

# opencode
ok, _ = run(["opencode", "--version"])
check("opencode", ok, "installed" if ok else "not on PATH (optional)")

# emdash (GUI app — check PATH, then the macOS app bundle)
ok, _ = run(["emdash", "--version"])
if not ok and sys.platform == "darwin":
    ok, _ = run(["ls", "-d", "/Applications/Emdash.app"])
check("emdash", ok, "installed" if ok else "not installed (GUI app — optional)")

summary = {
    "pass": sum(1 for c in CHECKS if c["status"] == "pass"),
    "fail": sum(1 for c in CHECKS if c["status"] == "fail"),
}

if "--json" in sys.argv:
    print(json.dumps({"checks": CHECKS, "summary": summary, "timestamp": time.time()}))
else:
    for c in CHECKS:
        mark = "PASS" if c["status"] == "pass" else "FAIL"
        print(f"  [{mark}] {c['name']}: {c['detail']}")
    print(f"\n  {summary['pass']} pass, {summary['fail']} fail")

sys.exit(0 if summary["fail"] == 0 else 1)
