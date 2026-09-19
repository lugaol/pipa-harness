"""pipa up — install tools, start services, wire project."""
from __future__ import annotations

from pathlib import Path

from pipa import config, runtime as runtimes, scaffold, services, session


def _say(msg: str = "") -> None:
    print(msg)


def _readiness(root: Path, rt_name: str) -> list[tuple[bool, str]]:
    """`pipa up` closing checklist — what works now, what needs a human."""
    out: list[tuple[bool, str]] = []
    try:
        from pipa.model_registry import tier_assignments

        tiers = tier_assignments()
        out.append((bool(tiers),
                     f"tier aliases assigned ({', '.join(sorted(tiers)) or 'NONE — agents cannot pick models'})"))
    except Exception:
        pass
    try:
        from urllib.request import Request, urlopen

        req = Request(f"{config.LITELLM_URL}/v1/models",
                       headers={"Authorization": f"Bearer {config.LITELLM_KEY}"})
        with urlopen(req, timeout=5):
            gateway = True
    except Exception:
        gateway = False
    out.append((gateway, f"gateway serving at {config.LITELLM_URL}"))
    project = config.git_root()
    graph = (project or root) / "graphify-out" / "graph.json"
    if not graph.is_file():
        graph = root / "graphify-out" / "graph.json"
    out.append((graph.is_file(),
                 "code graph indexed"
                 + ("" if graph.is_file() else f" — run: cd {(project or root)} && graphify index .")))
    if rt_name == "opencode":
        plugin = Path.home() / ".config" / "opencode" / "plugin" / "pipa-session-bus.js"
        out.append((plugin.is_file(),
                     "session bus wired (opencode plugin)"
                     + ("" if plugin.is_file() else " — re-run `pipa runtime set opencode`")))
    return out


def cmd_up(args) -> int:
    root = config.harness_root()
    rep = services.Reporter()

    try:
        from pipa.providers import refresh as discover_models

        summary = discover_models(timeout=6)
        found = sum(len(p.get("models") or []) for p in summary["providers"].values())
        failed = [s for s, p in summary["providers"].items() if not p.get("ok")]
        rep.ok(f"discovered {found} models from providers" + (
            f" (unreachable: {', '.join(failed)})" if failed else ""))
    except Exception as e:  # noqa: BLE001 — never block `pipa up` on discovery
        rep.warn(f"model discovery failed ({e}); using last known catalog")

    try:
        from pipa.model_registry import seed_default_tiers

        seeded = seed_default_tiers()
        if seeded:
            rep.ok("seeded default tier assignments (change on dashboard Models page)")
            for tier, alias in sorted(seeded.items()):
                _say(f"       {tier:<7} -> {alias}")
    except Exception:
        pass

    litellm_cfg, warn = config.pick_litellm_config(root)
    if warn:
        rep.warn(warn)

    _say(f"pipa up — {services.OS}/{services.ARCH} (root: {root})")
    _say("")

    services.ensure_uv(rep)
    services.ensure_python_deps(rep)
    services.ensure_ollama(rep)
    services.ensure_litellm(rep)
    services.ensure_graphify(rep)

    rt_name = runtimes.resolve(args.runtime)
    ok, msg = runtimes.ensure_installed(rt_name)
    (rep.ok if ok else rep.warn)(msg)
    services.ensure_obsidian(rep, gui=not args.no_apps)
    services.ensure_emdash(rep, gui=not args.no_apps)
    dashboard_up = services.ensure_dashboard(rep, root)

    _say("")
    services.start_ollama(rep)
    if not args.no_pull:
        services.pull_models(rep, litellm_cfg, root)
    services.start_litellm(rep, litellm_cfg)

    _say("")
    services.persist_path(rep, root)

    target = config.git_root()
    if target and target != root:
        pipa_dir = config.pipa_dir(target)
        if not pipa_dir.exists():
            rep.add(f"scaffolding project in {target}")
            try:
                for a in scaffold.init_project(target, rt_name):
                    _say(f"  {a}")
            except scaffold.ScaffoldError as e:
                rep.warn(str(e))
        else:
            for a in runtimes.wire(runtimes.project_runtime(target), target, root):
                _say(f"  {a}")
            failed = [m for ok_, m in scaffold.check_extension(target) if not ok_]
            if failed:
                rep.warn(f"extension health: {len(failed)} issue(s) — run `pipa status`")

    _say("")
    _say("Verifying...")
    from pipa.commands.status import cmd_status

    cmd_status(args)
    try:
        from pipa.commands.lifecycle import freshness_note

        note = freshness_note()
        if note:
            rep.warn(note)
    except Exception:
        pass
    readiness = _readiness(root, rt_name)
    if readiness:
        _say("")
        _say("Readiness:")
        for ok, label in readiness:
            mark = "✓" if ok else "✗"
            _say(f"  [{mark}] {label}")
        if not all(ok for ok, _ in readiness):
            _say("  Fix ✗ rows above, then re-run `pipa up`.")
    _say("")
    _say("Done.")
    if dashboard_up:
        _say(f"  Dashboard: http://localhost:{config.DASHBOARD_PORT}")
    _say(f"  Logs: {config.state_dir()}/litellm.log · {config.state_dir()}/ollama.log    Stop: pipa stop")
    return 0
