"""pipa install — selective component install."""
from __future__ import annotations

import sys

from pipa import runtime as runtimes, services


def _die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def _install_runtime(name: str):
    def go(rep) -> bool:
        ok, msg = runtimes.ensure_installed(name)
        (rep.ok if ok else rep.warn)(msg)
        return ok
    return go


def _verify_doctor(rep) -> bool:
    """Run `pipa doctor` as the final install stage (must be green)."""
    from pipa.commands.doctor import collect_checks

    try:
        checks = collect_checks()
    except Exception as exc:
        rep.warn(f"doctor failed to run: {exc}")
        return False
    fails = [c for c in checks if c["status"] == "fail"]
    warns = [c for c in checks if c["status"] == "warn"]
    summary = (f"pipa doctor: {len(checks) - len(fails) - len(warns)} pass, "
               f"{len(warns)} warn, {len(fails)} fail")
    if fails:
        rep.warn(summary + " — " + "; ".join(c["name"] for c in fails))
    else:
        rep.ok(summary)
    return not fails


def _all_ok(*calls) -> bool:
    return all(bool(c) for c in calls)


INSTALL_COMPONENTS = {
    "uv": services.ensure_uv,
    "py-deps": services.ensure_python_deps,
    "ollama": services.ensure_ollama,
    "litellm": services.ensure_litellm,
    "graphify": services.ensure_graphify,
    "opencode": _install_runtime("opencode"),
    "apps": lambda rep: _all_ok(
        services.ensure_obsidian(rep), services.ensure_emdash(rep)
    ),
    "verify": _verify_doctor,
}


def cmd_install(args) -> int:
    rep = services.Reporter()
    components = list(INSTALL_COMPONENTS) if args.component == ["all"] else args.component
    unknown = [c for c in components if c not in INSTALL_COMPONENTS]
    if unknown:
        _die(f"unknown component(s): {', '.join(unknown)} "
             f"(choose: {', '.join(INSTALL_COMPONENTS)}, all)")
    # Each component reports success or failure; `pipa install` exits with the
    # verdict. It used to return 0 unconditionally, so the dashboard installer
    # rendered "exit 0" next to a component that had just failed to install.
    failed: list[str] = []
    for c in components:
        try:
            if not INSTALL_COMPONENTS[c](rep):
                failed.append(c)
        except Exception as e:  # noqa: BLE001 — one bad component, clear verdict
            rep.warn(f"{c}: {type(e).__name__}: {e}")
            failed.append(c)
    if failed:
        rep.warn(f"{len(failed)} component(s) failed: {', '.join(failed)}")
        return 1
    return 0
