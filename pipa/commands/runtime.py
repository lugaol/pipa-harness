"""pipa runtime — inspect or switch the project runtime."""
from __future__ import annotations

import sys

from pipa import config, runtime as runtimes


def _say(msg: str = "") -> None:
    print(msg)


def _die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


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
