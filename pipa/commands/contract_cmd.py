"""`pipa contract` — inspect what subagents reported.

Reads the delegation log and prints a summary plus the unverified/blocked
work, which is the part a parent actually needs to act on.
"""
from __future__ import annotations

from pathlib import Path

from pipa import config, contract


def _log_path() -> Path:
    """Per-project log: a delegation belongs to the project it happened in."""
    project = config.find_project()
    if project is not None:
        return config.pipa_dir(project) / "state" / contract.CONTRACT_FILE
    return config.state_dir() / contract.CONTRACT_FILE


def cmd_contract(args) -> int:
    records = contract.read_log(_log_path())
    if not records:
        print("  no delegations recorded yet")
        print(f"  log: {_log_path()}")
        print("\n  Have subagents report with one line, e.g.:")
        print('    {"event":"delegation","agent":"dev","outcome":"done",'
              '"tier":"mid","verified":true}')
        return 0

    s = contract.summarize(records)
    print(f"\n  {s['total']} delegation(s)\n")
    print("  by agent")
    for a, n in sorted(s["by_agent"].items(), key=lambda kv: -kv[1]):
        print(f"    {a:14} {n}")
    print("\n  outcome")
    for o, n in sorted(s["by_outcome"].items(), key=lambda kv: -kv[1]):
        colour = "32" if o == "done" else ("33" if o == "partial" else "31")
        print(f"    \033[{colour}m{o:14}\033[0m {n}")
    if s["files"]:
        print(f"\n  files touched ({len(s['files'])})")
        for f in s["files"][:15]:
            print(f"    {f}")
    if s["skills"]:
        print(f"\n  skills used: {', '.join(s['skills'])}")
    if s["unverified"]:
        print(f"\n  \033[33munverified work — treat these results as unconfirmed\033[0m")
        for a in s["unverified"]:
            print(f"    {a}")
    print()
    if s["needs_attention"]:
        print("  \033[33mneeds attention: blocked/failed outcomes or unverified work above\033[0m")
    return 0


def build_subparser(sub) -> None:
    sp = sub.add_parser(
        "contract",
        help="summarise what subagents reported (outcome, files, unverified work)",
    )
    sp.set_defaults(func=cmd_contract)
