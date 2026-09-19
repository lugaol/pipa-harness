"""pipa — CLI entrypoint (arg parsing + dispatch; logic lives in pipa/commands/)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, config
from .commands.eval import cmd_eval
from .commands.doctor import cmd_doctor
from .commands.lifecycle import build_subparsers as lifecycle_parsers
from .commands.usage import build_subparser as usage_parser
from .commands.memory_gc import build_subparser as memory_gc_parser
from .commands.triage import build_subparser as triage_parser
from .commands.init import cmd_init
from .commands.install import INSTALL_COMPONENTS, cmd_install
from .commands.recall import cmd_recall
from .commands.replay import cmd_diff, cmd_replay
from .commands.runtime import cmd_runtime
from .commands.spend import cmd_spend
from .commands.status import cmd_status
from .commands.up import cmd_up
from . import hooks, runtime as runtimes, scaffold, services


def _die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def cmd_stop(args) -> int:
    stopped = services.stop_services()
    if stopped:
        for s in stopped:
            print(f"  [ok] {s} stopped")
    else:
        print("No pipa services were running.")
    return 0


def cmd_migrate(args) -> int:
    target = Path(args.path).resolve() if args.path else (config.git_root() or Path.cwd())
    try:
        actions = scaffold.migrate_project(target)
    except scaffold.ScaffoldError as e:
        _die(str(e))
    print(f"pipa migrate — {target}")
    for a in actions:
        print(f"  {a}")
    print("\nMigrated to .pipa/. Run `pipa status` to verify.")
    return 0


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

    sp = sub.add_parser("doctor", help="tier-system + gateway diagnostics (exit 1 on hard errors)")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_doctor)

    lifecycle_parsers(sub)
    usage_parser(sub)
    memory_gc_parser(sub)
    triage_parser(sub)

    sp = sub.add_parser("runtime", help="inspect or switch the project runtime")
    sp.add_argument("runtime_cmd", nargs="?", choices=["list", "show", "set"], default="show")
    sp.add_argument("name", nargs="?", choices=runtimes.names())
    sp.set_defaults(func=cmd_runtime)

    sp = sub.add_parser("migrate", help="legacy .harness_extension/ -> .pipa/")
    sp.add_argument("--path", help="project root (default: git root / cwd)")
    sp.set_defaults(func=cmd_migrate)

    sp = sub.add_parser("hook", help="append to the shared NDJSON session log (internal)")
    sp.set_defaults(func=lambda a: hooks.main(a.hook_args))

    sp = sub.add_parser("eval", help="run agent evals")
    sp.add_argument("eval_args", nargs=argparse.REMAINDER)
    sp.set_defaults(func=cmd_eval)

    sp = sub.add_parser("install", help="install harness components")
    sp.add_argument("component", nargs="+",
                    help="uv py-deps ollama litellm graphify dsh opencode apps verify | all")
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

    sp = sub.add_parser("recall", help="one query over vault + memory.db + code graph")
    sp.add_argument("query", nargs="?")
    sp.add_argument("--limit", type=int, default=8)
    sp.add_argument("--stale", action="store_true",
                    help="report stale notes (expired/untouched/over-budget), no query needed")
    sp.add_argument("--digest", action="store_true",
                    help="compact bounded digest for the memory-context plugin")
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
