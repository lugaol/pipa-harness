"""pipa update/check-update/version + diagnose — lifecycle operations.

Ported from ia_harness tools/auto-update.sh + tools/diagnose.sh, adapted
to git semantics: the updater never touches local changes (dirty tree →
refuse with instructions), never merges (fast-forward only), and never
blocks on offline (best-effort messages, exit 0 for probes).
"""
from __future__ import annotations

import argparse
import socket
import subprocess
import sys
from pathlib import Path

from pipa import config, services


def _git(args: list[str], timeout: int = 20) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["git", "-C", str(config.harness_root()), *args],
            capture_output=True, text=True, timeout=timeout,
        )
        return r.returncode == 0, (r.stdout or r.stderr).strip()
    except Exception as exc:
        return False, str(exc)


def cmd_version(args) -> int:
    from pipa import __version__

    print(f"pipa {__version__}")
    return 0


def freshness_note(timeout: int = 10) -> str | None:
    """Best-effort 'update available' notice for `pipa up` (warn mode).

    Silent (None) on any failure — offline, no git, no remote. Never blocks.
    """
    ok, head = _git(["rev-parse", "HEAD"], timeout=timeout)
    if not ok or not head:
        return None
    ok, remote = _git(["ls-remote", "origin", "HEAD"], timeout=timeout)
    if not ok or not remote:
        return None
    remote_sha = remote.split()[0]
    if remote_sha and remote_sha != head:
        return (f"harness update available "
                f"({head[:12]} → {remote_sha[:12]}); run `pipa update`")
    return None


def cmd_check_update(args) -> int:
    from pipa import __version__

    ok, head = _git(["rev-parse", "HEAD"])
    if not ok:
        print("check-update: not a git checkout (nothing to compare)")
        return 0
    ok, remote = _git(["ls-remote", "origin", "HEAD"])
    if not ok or not remote:
        print(f"check-update: local {head[:12]} — remote unreachable (offline?)")
        return 0
    remote_sha = remote.split()[0]
    if remote_sha == head:
        print(f"check-update: up to date ({head[:12]})")
    else:
        print(f"check-update: update available (local {head[:12]} → "
              f"remote {remote_sha[:12]}); run `pipa update`")
    return 0


def cmd_update(args) -> int:
    ok, dirty = _git(["status", "--porcelain"])
    if not ok:
        print("ERROR: not a git checkout — cannot update", file=sys.stderr)
        return 1
    if dirty:
        print("ERROR: working tree has local changes — update refused "
              "(commit, stash, or discard them first)", file=sys.stderr)
        return 1
    ok, out = _git(["pull", "--ff-only"])
    print(out or "(already up to date)")
    return 0 if ok else 1


def _port_owner(port: int) -> str:
    """Best-effort 'what listens on port' via connect probe (no psutil)."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return "listening"
    except Exception:
        return "free"


def cmd_diagnose(args) -> int:
    """Human-readable troubleshooting dump; always exits 0."""
    from pipa import __version__

    print(f"pipa diagnose — v{__version__} @ {config.harness_root()}")
    for name, port in (("litellm gateway", config.LITELLM_PORT),
                       ("ollama", config.OLLAMA_PORT),
                       ("dashboard", config.DASHBOARD_PORT)):
        print(f"  port {port} ({name}): {_port_owner(port)}")
    state = config.state_dir()
    for pid_file in sorted(state.glob("*.pid")):
        alive = services._pid_alive(pid_file)
        print(f"  pid {pid_file.name}: {'alive' if alive else 'STALE'}")
    if not list(state.glob("*.pid")):
        print("  pid: no pid files in state/")
    try:
        effective = config.models_dir() / ".effective.yaml"
        before = effective.read_text() if effective.exists() else None
        config.compose_litellm_config()
        after = effective.read_text() if effective.exists() else None
        print("  gateway-config: "
              + ("in sync" if before == after else "was stale (regenerated)"))
    except Exception as exc:
        print(f"  gateway-config: compose failed: {exc}")
    gw = "reachable" if services._http_up(
        f"{config.LITELLM_URL}/v1/models",
        headers={"Authorization": f"Bearer {config.LITELLM_KEY}"}) else "down"
    print(f"  gateway probe: {gw}")
    print(f"  ollama probe: {'up' if services._http_up(config.OLLAMA_URL) else 'down'}")
    return 0


def build_subparsers(sub) -> None:
    p = sub.add_parser("version", help="print the harness version")
    p.set_defaults(func=cmd_version)
    p = sub.add_parser("check-update",
                       help="compare local checkout against origin HEAD")
    p.set_defaults(func=cmd_check_update)
    p = sub.add_parser("update",
                       help="fast-forward pull (refuses on dirty tree)")
    p.set_defaults(func=cmd_update)
    p = sub.add_parser("diagnose",
                       help="troubleshooting dump (ports, pids, config)")
    p.set_defaults(func=cmd_diagnose)
