"""`pipa agents` — discoverability for the subagent layer.

Both audiences need this and neither had it:

- **A human** asking "what can this thing delegate to?" currently has to read
  nine markdown files.
- **An orchestrating agent** choosing a delegate needs the same facts as
  structured data. opencode's own agent list gives names but not intent, and
  the per-agent `description:` frontmatter is the only place that says when
  to use one.

This reads the frontmatter and prints it, so the two can never drift from
what the files actually say.
"""
from __future__ import annotations

import re
from pathlib import Path

from pipa import config

FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---[ \t]*\r?\n", re.S)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split flat `key: value` frontmatter from the body.

    Single owner: the dashboard imports this rather than keeping a second
    parser. Its copy anchored on `^---\\n` and split on any `:`, so a
    CRLF-authored agent lost its whole frontmatter and a nested permission
    line yielded a junk key.

    Returns ({}, text) when there is no frontmatter.
    """
    m = FRONTMATTER.match(text)
    if not m:
        return {}, text
    fm: dict = {}
    for line in m.group(1).splitlines():
        km = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if not km:
            continue
        key, val = km.group(1), km.group(2).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        fm[key] = val
    return fm, text[m.end():]


def _parse(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}
    return parse_frontmatter(text)[0]


def collect(root: Path | None = None) -> list[dict]:
    """[{name, description, model, mode, permission}] from agents/*.md."""
    root = root or config.harness_root()
    out: list[dict] = []
    for d in (root / "agents").glob("*.md"):
        fm = _parse(d)
        if not fm:
            continue
        out.append({
            "name": fm.get("name", d.stem),
            "description": fm.get("description", ""),
            "model": fm.get("model", ""),
            "mode": fm.get("mode", ""),
            "permission": fm.get("permission", ""),
        })
    return sorted(out, key=lambda a: a["name"])


def cmd_agents(args) -> int:
    agents = collect()
    if not agents:
        print("  no agents found — is the harness installed?")
        return 1
    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps(agents, indent=2))
        return 0

    print(f"\n  {len(agents)} subagent(s) available for delegation\n")
    for a in agents:
        print(f"  {a['name']}")
        if a["description"]:
            print(f"      {a['description']}")
        bits = [b for b in (a["model"], a["mode"]) if b]
        if bits:
            print(f"      \033[2m{' · '.join(bits)}\033[0m")
        if a["permission"]:
            print(f"      \033[2mpermissions: {a['permission']}\033[0m")
        print()
    print("  Delegate by role, not by name-guessing: read a target agent's")
    print("  frontmatter before invoking it, and report what you used:")
    print("      <agent>: <what it did>")
    return 0


def build_subparser(sub) -> None:
    sp = sub.add_parser(
        "agents",
        help="list subagents: what each is for, which model, what it may do",
    )
    sp.add_argument("--json", action="store_true", help="machine-readable")
    sp.set_defaults(func=cmd_agents)
