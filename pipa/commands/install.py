"""pipa install — selective component install."""
from __future__ import annotations

import sys

from pipa import runtime as runtimes, services


def _die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def _install_runtime(name: str):
    def go(rep) -> None:
        ok, msg = runtimes.ensure_installed(name)
        (rep.ok if ok else rep.warn)(msg)
    return go


def _verify_doctor(rep) -> None:
    """Run `pipa doctor` as the final install stage (must be green)."""
    from pipa.commands.doctor import _collect

    try:
        checks = _collect()
    except Exception as exc:
        rep.warn(f"doctor failed to run: {exc}")
        return
    fails = [c for c in checks if c["status"] == "fail"]
    warns = [c for c in checks if c["status"] == "warn"]
    summary = (f"pipa doctor: {len(checks) - len(fails) - len(warns)} pass, "
               f"{len(warns)} warn, {len(fails)} fail")
    if fails:
        rep.warn(summary + " — " + "; ".join(c["name"] for c in fails))
    else:
        rep.ok(summary)


INSTALL_COMPONENTS = {
    "uv": lambda rep: services.ensure_uv(rep),
    "py-deps": lambda rep: services.ensure_python_deps(rep),
    "ollama": lambda rep: services.ensure_ollama(rep),
    "litellm": lambda rep: services.ensure_litellm(rep),
    "graphify": lambda rep: services.ensure_graphify(rep),
    "dsh": _install_runtime("deepseek-harness"),
    "opencode": _install_runtime("opencode"),
    "apps": lambda rep: (
        services.ensure_obsidian(rep),
        services.ensure_emdash(rep),
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
    for c in components:
        INSTALL_COMPONENTS[c](rep)
    return 0
