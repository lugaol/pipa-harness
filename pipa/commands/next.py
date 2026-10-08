"""`pipa next` — the single next action, derived from actual state.

A new user faces 21 commands and no ordering. `pipa init` prints a fixed
four-step list whether or not those steps are the ones that matter right now
— it tells someone with a broken gateway to "start services", and someone
whose models were never verified that they are done.

This inspects real state and emits exactly one next action, so the guidance
is never stale relative to the machine. Each step is cheap and read-only.
"""
from __future__ import annotations

import json
from pathlib import Path

from pipa import config


def _services() -> tuple[bool, bool]:
    gateway = dashboard = False
    try:
        import urllib.request

        req = urllib.request.Request(
            f"{config.LITELLM_URL}/v1/models",
            headers={"Authorization": f"Bearer {config.LITELLM_KEY}"},
        )
        with urllib.request.urlopen(req, timeout=4):
            gateway = True
    except Exception:  # noqa: BLE001
        pass
    try:
        import urllib.request

        with urllib.request.urlopen(
            f"http://localhost:{config.DASHBOARD_PORT}/api/health", timeout=3
        ):
            dashboard = True
    except Exception:  # noqa: BLE001
        pass
    return gateway, dashboard


def _verified() -> tuple[bool, str]:
    p = config.state_dir() / "model_verification.json"
    if not p.is_file():
        return False, ""
    try:
        data = json.loads(p.read_text())
        stamp = data.pop("_checked_at", None)
        if not data:
            return False, ""
        ok = sum(1 for v in data.values() if isinstance(v, dict) and v.get("ok"))
        return True, f"{ok}/{len(data)} callable, probed {stamp}"
    except (OSError, ValueError):
        return False, ""


def _commands() -> list[dict]:
    project = config.find_project()
    out = []
    if project is None:
        out.append((
            "not in a project",
            "cd into your project directory, then: git init && pipa init",
        ))
        return out
    pipa_dir = config.pipa_dir(project)
    if not pipa_dir.is_dir():
        out.append((
            "project not initialised",
            f"cd {project} && git init && pipa init",
        ))
        return out
    agents_md = project / "AGENTS.md"
    if not agents_md.is_file():
        out.append((
            "no project AGENTS.md",
            "pipa init   (creates .pipa/AGENTS.md + the root symlink)",
        ))
    elif "none detected" in agents_md.read_text(errors="ignore"):
        out.append((
            "AGENTS.md has unfilled placeholders",
            f"edit {pipa_dir / 'AGENTS.md'} — set the real build and test commands",
        ))
    return out


def _doctor_wiring() -> tuple[bool, str]:
    try:
        from pipa.commands.doctor import collect_checks

        for c in collect_checks():
            if c["name"] == "cli-on-path" and c["status"] != "pass":
                return False, c["detail"]
            if c["name"] == "agent-instructions" and c["status"] != "pass":
                return False, c["detail"]
    except Exception as exc:  # noqa: BLE001
        return True, f"(could not verify: {exc})"
    return True, ""


def cmd_next(args) -> int:
    project = config.find_project()

    print("\n  What to do next\n  " + "-" * 46)

    wiring_ok, wiring_detail = _doctor_wiring()
    if not wiring_ok:
        print("  [1] Fix the install first — nothing else will behave")
        print(f"      {wiring_detail}")
        print("\n      Then: pipa doctor")
        return 1

    steps = _commands()
    gateway, dashboard = _services()
    verified, vdetail = _verified()

    if steps:
        label, cmdline = steps[0]
        print(f"  [1] {label}")
        print(f"      {cmdline}")
    elif not gateway:
        print("  [1] Services are not running")
        print("      pipa up")
    elif not verified:
        print(f"  [1] Models have never been verified live")
        print("      pipa check models    # catches listed-but-broken models")
    elif not dashboard:
        print("  [1] Dashboard is not running")
        print("      pipa up")
    else:
        print("  [1] Setup is complete — you are ready to work")
        print("      Ask the agent something only your project can answer:")
        print("        opencode run \"what build and test commands does this project use?\"")
    print()

    print("  State")
    print(f"    project      {project or '(none — not inside one)'}")
    print(f"    gateway      {'up' if gateway else 'down'}"
          f"{'  (' + config.LITELLM_URL + ')' if gateway else ''}")
    print(f"    dashboard    {'up' if dashboard else 'down'}")
    print(f"    models       {vdetail or 'never probed'}")
    print()
    print("  Useful at any time")
    print("    pipa doctor        full diagnostics")
    print("    pipa check         mechanical checks")
    print("    pipa agents        what can be delegated to")
    print("    pipa bus read      messages from other agents")
    print("    opencode            start the agent\n")
    return 0


def build_subparser(sub) -> None:
    sp = sub.add_parser(
        "next",
        help="the single next action, derived from actual state",
    )
    sp.set_defaults(func=cmd_next)
