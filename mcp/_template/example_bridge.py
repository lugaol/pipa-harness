#!/usr/bin/env python3
"""Example MCP bridge — the convention every mcp/<name>/ bridge follows.

Contract (ported from ia_harness mcp/_template/example_mcp_bridge.py):
  --status     one JSON line: {"ok": bool, "detail": str} (dashboard health)
  --self-test  exit 0 when the bridge works, nonzero with a reason on stderr
  --<tool>     one tool per flag, JSON on stdout, errors on stderr (exit 1)

Rules: never print secrets; never touch paths outside your own mcp/<name>/
folder (or explicit allow-listed targets); fail soft with a message, never
a traceback, when an optional backend is offline.
"""
import argparse
import json
import sys


def cmd_status() -> dict:
    """One-line health for dashboards and `pipa status`."""
    return {"ok": True, "detail": "template bridge: no backend required"}


def cmd_example(name: str = "world") -> dict:
    """A placeholder tool: replace with real backend calls."""
    if not name.strip():
        raise ValueError("name must not be empty")
    return {"greeting": f"hello, {name.strip()}"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--example", metavar="NAME", default=None)
    args = ap.parse_args(argv)
    try:
        if args.status:
            print(json.dumps(cmd_status()))
        elif args.self_test:
            st = cmd_status()
            assert st["ok"], st.get("detail", "unhealthy")
            out = cmd_example("self-test")
            assert out["greeting"] == "hello, self-test"
            print(json.dumps({"ok": True, "detail": "self-test passed"}))
        elif args.example is not None:
            print(json.dumps(cmd_example(args.example)))
        else:
            ap.print_help()
            return 2
    except AssertionError as exc:
        print(f"self-test failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — soft failure, no tracebacks
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
