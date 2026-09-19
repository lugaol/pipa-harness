"""pipa init — scaffold .pipa/ in the current project."""
from __future__ import annotations

from pathlib import Path

from pipa import config, runtime as runtimes, scaffold


def _say(msg: str = "") -> None:
    print(msg)


def _die(msg: str, code: int = 1) -> None:
    import sys

    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


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
