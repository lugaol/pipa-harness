"""`pipa bus` — inter-agent message bus CLI.

The bus is a shared append-only board at <project>/.pipa/state/bus.ndjson.
Any agent (or a human) can post to it and read from it, which is what lets
sibling agents see each other's work without the orchestrator relaying
everything through its own context.

    pipa bus post --from explorer --to dev --kind finding --body "..."
    pipa bus read --to dev --since 12
    pipa bus list
"""
from __future__ import annotations

from pipa import bus as bus_mod


def _fmt(rec: dict) -> str:
    head = f"  [{rec.get('_line', '?'):>4}] {rec.get('ts', '')} {rec.get('from', '?')} → {rec.get('to', 'all')}"
    if rec.get("topic"):
        head += f"  ({rec['topic']})"
    kind = rec.get("kind", "note")
    colour = {
        "blocker": "31", "question": "33", "handoff": "36",
        "done": "32", "finding": "0",
    }.get(kind, "2")
    return f"{head}  \033[{colour}m{kind}\033[0m\n          {rec.get('body', '')}"


def cmd_bus(args) -> int:
    action = getattr(args, "bus_action", None) or "read"
    project = None

    if action == "post":
        ok, msg = bus_mod.post(
            frm=getattr(args, "frm", "") or "unknown",
            body=getattr(args, "body", "") or "",
            to=getattr(args, "to", "all") or "all",
            kind=getattr(args, "kind", "note") or "note",
            topic=getattr(args, "topic", "") or "",
            project=project,
        )
        if ok:
            print(f"  [ok] {msg}")
            return 0
        print(f"  [!!] {msg}")
        return 1

    if action == "clear":
        ok, msg = bus_mod.clear(project=project)
        print(f"  [{'ok' if ok else '!!'}] {msg}")
        return 0 if ok else 1

    if action == "list":
        path = bus_mod.bus_path(project)
        if not path.is_file():
            print("  bus empty — no messages posted yet")
            print(f"  path: {path}")
            return 0
        recs, _ = bus_mod.read(limit=0, project=project)
        print(f"  {len(recs)} message(s) on {path}")
        for rec in recs[-int(getattr(args, 'limit', 20) or 20):]:
            print(_fmt(rec))
        return 0

    # read
    recs, total = bus_mod.read(
        since=int(getattr(args, "since", 0) or 0),
        to=getattr(args, "to", None),
        frm=getattr(args, "frm", None),
        kind=getattr(args, "kind", None),
        limit=int(getattr(args, "limit", 20) or 20),
        project=project,
    )
    if not recs:
        print(f"  no messages (board has {total} total; cursor={total})")
        return 0
    print(f"  {len(recs)} message(s) of {total} total — next cursor: {total}")
    for rec in recs:
        print(_fmt(rec))
    return 0


def build_subparser(sub) -> None:
    sp = sub.add_parser(
        "bus",
        help="inter-agent message bus (post/read/list) — shared project board",
    )
    spsub = sp.add_subparsers(dest="bus_action")

    p = spsub.add_parser("post", help="append a message to the board")
    p.set_defaults(bus_action="post")
    p.add_argument("--from", dest="frm", default="", help="sender agent name")
    p.add_argument("--to", default="all", help="recipient agent, or 'all'")
    p.add_argument(
        "--kind", default="note",
        help="note|finding|question|blocker|handoff|done",
    )
    p.add_argument("--topic", default="", help="short subject")
    p.add_argument("--body", default="", help="message text")

    r = spsub.add_parser("read", help="read messages addressed to you")
    r.set_defaults(bus_action="read")
    r.add_argument("--to", default=None, help="filter by recipient")
    r.add_argument("--from", dest="frm", default=None, help="filter by sender")
    r.add_argument("--kind", default=None)
    r.add_argument("--since", type=int, default=0, help="only lines after N")
    r.add_argument("--limit", type=int, default=20)

    lst = spsub.add_parser("list", help="show the whole board")
    lst.set_defaults(bus_action="list")
    lst.add_argument("--limit", type=int, default=20)

    c = spsub.add_parser("clear", help="reset the board")
    c.set_defaults(bus_action="clear")
    sp.set_defaults(func=cmd_bus, bus_action="read")
