"""pipa — single CLI entrypoint for the harness.

  pipa init [--runtime R] [--type T]   scaffold .pipa/ in the current project
  pipa up [--runtime R] [--no-pull] [--no-apps]   install tools, start services
  pipa stop                            stop services started by pipa
  pipa status [--json]                 health check (gate-friendly exit code)
  pipa runtime list|show|set <name>    inspect/switch the project runtime
  pipa migrate                         legacy .harness_extension/ -> .pipa/
  pipa hook <event> [args...]          append to the shared NDJSON session log
  pipa replay [SID] [--log P]          flight-recorder: replay one session
  pipa diff A B [--log P]              compare two recorded sessions
  pipa recall "query"                  one query over vault+memory.db+graph
  pipa spend [--since TS] [--json]     token/cost ledger from the gateway
  pipa eval [args...]                  run agent evals (tools/evals)

Runtimes: opencode, deepseek-harness, auto (prefers deepseek-harness).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from . import __version__, config, hooks, runtime as runtimes, scaffold, services, session


def _say(msg: str = "") -> None:
    print(msg)


def _die(msg: str, code: int = 1) -> "None":
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


# ── init ────────────────────────────────────────────────────────────────────

def cmd_init(args) -> int:
    target = Path(args.path).resolve() if args.path else (config.git_root() or Path.cwd())
    if args.fill_only:
        facts = scaffold.fill_agents_md(target)
        if not facts:
            _die(f"no AGENTS.md found in {target}")
        _say(f"Filled AGENTS.md: name={facts['name']} build={facts['build']} test={facts['test']}")
        return 0
    try:
        actions = scaffold.init_project(target, args.runtime, args.type)
    except (scaffold.ScaffoldError, runtimes.RuntimeError_) as e:
        _die(str(e))
    _say(f"pipa init — {target}")
    for a in actions:
        _say(f"  {a}")
    name = runtimes.project_runtime(target)
    _say("")
    _say("Done. Next steps:")
    _say("  1. Start services:   pipa up")
    _say("  2. Health check:     pipa status")
    _say(f"  3. Start runtime:    {'opencode' if name == 'opencode' else 'deepseek-harness (dsh web — npm i -g @deepseek-ai/dsh)'}")
    _say("  4. Review .pipa/AGENTS.md and add project-specific golden rules.")
    return 0


# ── up / stop / status ──────────────────────────────────────────────────────

def cmd_up(args) -> int:
    root = config.harness_root()
    rep = services.Reporter("up")
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

    # scaffold the current project when inside a foreign git repo
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
    cmd_status(args)
    _say("")
    _say("Done.")
    if dashboard_up:
        _say(f"  Dashboard: http://localhost:{config.DASHBOARD_PORT}")
    _say(f"  Logs: {config.state_dir()}/litellm.log · {config.state_dir()}/ollama.log    Stop: pipa stop")
    return 0


def cmd_stop(args) -> int:
    stopped = services.stop_services()
    if stopped:
        for s in stopped:
            _say(f"  [ok] {s} stopped")
    else:
        _say("No pipa services were running.")
    return 0


def cmd_status(args) -> int:
    root = config.harness_root()
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "status": "pass" if ok else "fail", "detail": detail})

    # LiteLLM gateway
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

    # runtimes
    found = runtimes.installed()
    check("runtime", bool(found), f"installed: {', '.join(found)}" if found else "no runtime on PATH")

    # graphify
    check("graphify-cli", services.have("graphify"), "installed" if services.have("graphify") else "not on PATH")

    # project checks
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


# ── runtime ─────────────────────────────────────────────────────────────────

def cmd_runtime(args) -> int:
    if args.runtime_cmd == "list":
        for name in runtimes.names():
            rt = runtimes.RUNTIMES[name]
            mark = "installed" if rt.installed() else "not installed"
            _say(f"  {name:<18} {rt.label:<18} {mark}")
        return 0
    project = config.find_project()
    if not project or not config.pipa_dir(project).exists():
        _die("not inside a pipa project (run `pipa init` first)")
    if args.runtime_cmd == "show" or args.runtime_cmd is None:
        current = runtimes.read_project_runtime(project)
        _say(f"project:  {project}")
        _say(f"runtime:  {current or '(auto)'} -> {runtimes.project_runtime(project)}")
        return 0
    if args.runtime_cmd == "set":
        try:
            runtimes.write_project_runtime(project, args.name)
        except runtimes.RuntimeError_ as e:
            _die(str(e))
        root = config.harness_root()
        actions = runtimes.wire(args.name, project, root)
        _say(f"runtime set to '{args.name}' in {project}")
        for a in actions:
            _say(f"  {a}")
        return 0
    _die(f"unknown runtime subcommand: {args.runtime_cmd}", code=2)


# ── migrate ─────────────────────────────────────────────────────────────────

def cmd_migrate(args) -> int:
    target = Path(args.path).resolve() if args.path else (config.git_root() or Path.cwd())
    try:
        actions = scaffold.migrate_project(target)
    except scaffold.ScaffoldError as e:
        _die(str(e))
    _say(f"pipa migrate — {target}")
    for a in actions:
        _say(f"  {a}")
    _say("\nMigrated to .pipa/. Run `pipa status` to verify.")
    return 0


# ── eval ────────────────────────────────────────────────────────────────────

def cmd_eval(args) -> int:
    script = config.harness_root() / "tools" / "evals" / "run.py"
    if not script.exists():
        _die(f"eval runner not found: {script}")
    return subprocess.run([sys.executable, str(script), *args.eval_args]).returncode


# ── install ─────────────────────────────────────────────────────────────────

def _install_runtime(name: str):
    def go(rep) -> None:
        ok, msg = runtimes.ensure_installed(name)
        (rep.ok if ok else rep.warn)(msg)
    return go


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
}


def cmd_install(args) -> int:
    rep = services.Reporter("install")
    components = list(INSTALL_COMPONENTS) if args.component == ["all"] else args.component
    unknown = [c for c in components if c not in INSTALL_COMPONENTS]
    if unknown:
        _die(f"unknown component(s): {', '.join(unknown)} "
             f"(choose: {', '.join(INSTALL_COMPONENTS)}, all)")
    for c in components:
        INSTALL_COMPONENTS[c](rep)
    return 0


# ── flight recorder (replay / diff) ────────────────────────────────────────

def _session_log(args) -> Path:
    if getattr(args, "log", None):
        return Path(args.log).expanduser()
    project = config.find_project()
    if project:
        return config.session_log_path(project)
    return config.state_dir() / config.SESSION_LOG


def _parse_ts(ts: str | None) -> float:
    if not ts:
        return 0.0
    try:
        from datetime import datetime
        return datetime.fromisoformat(ts).timestamp()
    except ValueError:
        return 0.0


def _replay_lines(events: list[dict]) -> list[str]:
    t0 = _parse_ts(events[0].get("ts")) if events else 0.0
    lines = []
    for e in events:
        off = _parse_ts(e.get("ts")) - t0
        ev = e.get("event", "?")
        head = f"  +{off:6.1f}s  {ev:<14}"
        detail = e.get("tool") or e.get("model") or ""
        payload = e.get("payload") or e.get("text") or ""
        if payload:
            payload = str(payload).replace("\n", " ")
            payload = payload[:70] + "…" if len(payload) > 70 else payload
            detail = f"{detail}  {payload}" if detail else payload
        meta = ", ".join(
            f"{k}={e[k]}" for k in ("tokens_in", "tokens_out", "cost_usd")
            if e.get(k) is not None
        )
        if meta:
            detail = f"{detail}  ({meta})" if detail else meta
        lines.append(head + (f" {detail}" if detail else ""))
    return lines


def cmd_replay(args) -> int:
    log = _session_log(args)
    all_sessions = session.sessions(log)
    if not all_sessions:
        _say(f"no sessions in {log}")
        return 1
    sid = args.session or all_sessions[-1]["id"]
    events = session.load_session(log, sid)
    if not events:
        known = ", ".join(s["id"] for s in all_sessions[-8:])
        _die(f"no session '{sid}' in {log} (recent: {known})")
    s = next(x for x in all_sessions if x["id"] == sid)
    dur = (_parse_ts(s["end"]) - _parse_ts(s["start"])) if s["end"] else 0.0
    tools = ",".join(sorted(s["tools"])) or "-"
    models = ",".join(sorted(s["models"])) or "-"
    _say(
        f"session {s['id']} · runtime={s['runtime'] or '?'} · "
        f"{s['events']} events · {dur:.0f}s · tools[{tools}] · models[{models}]"
    )
    for line in _replay_lines(events):
        _say(line)
    return 0


def cmd_diff(args) -> int:
    log = _session_log(args)
    a_events = session.load_session(log, args.a)
    b_events = session.load_session(log, args.b)
    if not a_events or not b_events:
        known = ", ".join(s["id"] for s in session.sessions(log)[-8:])
        _die(f"unknown session id(s) in {log} (recent: {known})")

    def profile(evs: list[dict]) -> dict:
        tools: set = set()
        models: set = set()
        tokens = 0
        for e in evs:
            if e.get("tool"):
                tools.add(e["tool"])
            if e.get("model"):
                models.add(e["model"])
            tokens += int(e.get("tokens_in") or 0) + int(e.get("tokens_out") or 0)
        dur = _parse_ts(evs[-1].get("ts")) - _parse_ts(evs[0].get("ts"))
        return {
            "events": len(evs), "dur": max(dur, 0.0),
            "tools": tools, "models": models, "tokens": tokens,
        }

    pa, pb = profile(a_events), profile(b_events)
    _say(f"diff {args.a} vs {args.b}  ({log})")
    rows = [
        ("events", pa["events"], pb["events"]),
        ("duration_s", round(pa["dur"], 1), round(pb["dur"], 1)),
        ("tokens", pa["tokens"] or "-", pb["tokens"] or "-"),
    ]
    for name, va, vb in rows:
        mark = "=" if va == vb else ("A" if vb < va or isinstance(va, str) else "B")
        _say(f"  {name:<12} A={va!s:<12} B={vb!s:<12} -> {mark}")
    only_a = sorted(pa["tools"] - pb["tools"])
    only_b = sorted(pb["tools"] - pa["tools"])
    _say(f"  tools only-A {only_a or '-'} · only-B {only_b or '-'}")
    ma, mb = sorted(pa["models"]), sorted(pb["models"])
    _say(f"  models       A={ma or '-'} · B={mb or '-'}")
    return 0


# ── memory plane (recall) ───────────────────────────────────────────────────

def cmd_recall(args) -> int:
    from .recall import recall as do_recall
    out = do_recall(args.query, project=config.find_project(), limit=args.limit)
    if not out["results"]:
        _say(f'nothing recalled for "{args.query}" '
             f"(sources: {', '.join(out['sources_queried']) or 'none'})")
        return 1
    _say(f'recall "{args.query}" — sources: {", ".join(out["sources_queried"])}')
    cur = None
    for hit in out["results"]:
        if hit["source"] != cur:
            cur = hit["source"]
            _say(f"\n  [{cur}]")
        flag = " EXPIRED" if hit["expired"] else ""
        loc = f" @ {hit['path']}" if hit.get("path") else ""
        _say(f"   - {hit['title']}{flag}{loc}")
        if hit.get("detail"):
            _say(f"       {hit['detail'][:100]}")
    return 0


# ── spend ledger ────────────────────────────────────────────────────────────

def cmd_spend(args) -> int:
    from .spend import summarize, format_report
    path = (
        Path(args.log).expanduser() if getattr(args, "log", None)
        else None
    )
    if path is None:
        candidate = config.state_dir() / "spend.ndjson"
        path = candidate if candidate.exists() else None
    summary = summarize(path, since=args.since)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _say(format_report(summary))
    return 0


# ── argparse ────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pipa", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"pipa {__version__}")
    sub = p.add_subparsers(dest="cmd")

    sp = sub.add_parser("init", help="scaffold .pipa/ in the current project")
    sp.add_argument("--runtime", default="auto", choices=[*runtimes.names(), "auto"])
    sp.add_argument("--type", default="generic", help="project-type template (templates/project/)")
    sp.add_argument("--path", help="project root (default: git root / cwd)")
    sp.add_argument("--fill-only", action="store_true",
                    help="only re-fill AGENTS.md placeholders")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("up", help="install tools, start services, wire project")
    sp.add_argument("--runtime", default="auto", choices=[*runtimes.names(), "auto"])
    sp.add_argument("--no-pull", action="store_true", help="skip ollama model downloads")
    sp.add_argument("--no-apps", action="store_true", help="skip GUI apps (obsidian, emdash)")
    sp.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    sp.set_defaults(func=cmd_up)

    sp = sub.add_parser("stop", help="stop services started by pipa")
    sp.set_defaults(func=cmd_stop)

    sp = sub.add_parser("status", help="health check (exit 1 on failure)")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("runtime", help="inspect or switch the project runtime")
    sp.add_argument("runtime_cmd", nargs="?", choices=["list", "show", "set"], default="show")
    sp.add_argument("name", nargs="?", choices=runtimes.names())
    sp.set_defaults(func=cmd_runtime)

    sp = sub.add_parser("migrate", help="legacy .harness_extension/ -> .pipa/")
    sp.add_argument("--path", help="project root (default: git root / cwd)")
    sp.set_defaults(func=cmd_migrate)

    sp = sub.add_parser("hook", help="append to the shared NDJSON session log")
    sp.add_argument("hook_args", nargs=argparse.REMAINDER)
    sp.set_defaults(func=lambda a: hooks.main(a.hook_args))

    sp = sub.add_parser("eval", help="run agent evals")
    sp.add_argument("eval_args", nargs=argparse.REMAINDER)
    sp.set_defaults(func=cmd_eval)

    sp = sub.add_parser("install", help="install harness components")
    sp.add_argument("component", nargs="+",
                    help="uv py-deps ollama litellm graphify dsh opencode apps | all")
    sp.set_defaults(func=cmd_install)

    sp = sub.add_parser("replay", help="replay a session from the flight recorder")
    sp.add_argument("session", nargs="?", help="session id (default: latest)")
    sp.add_argument("--log", help="session log path (default: project bus)")
    sp.set_defaults(func=cmd_replay)

    sp = sub.add_parser("diff", help="compare two recorded sessions A vs B")
    sp.add_argument("a", help="first session id")
    sp.add_argument("b", help="second session id")
    sp.add_argument("--log", help="session log path (default: project bus)")
    sp.set_defaults(func=cmd_diff)

    sp = sub.add_parser("recall", help='one query over vault + memory.db + code graph')
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=8)
    sp.set_defaults(func=cmd_recall)

    sp = sub.add_parser("spend", help="token/cost ledger written by the gateway")
    sp.add_argument("--since", help="only rows at/after this ISO ts")
    sp.add_argument("--log", help="spend NDJSON path (default: harness state)")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_spend)

    return p


def main(argv: list[str] | None = None) -> int:
    config.load_dotenv()
    args = build_parser().parse_args(argv)
    if not hasattr(args, "func"):
        build_parser().print_help()
        return 2
    if getattr(args, "cmd", None) == "runtime" and args.runtime_cmd == "set" and not args.name:
        _die("usage: pipa runtime set <name>", code=2)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
