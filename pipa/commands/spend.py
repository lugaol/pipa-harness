"""pipa spend — token/cost ledger from the gateway."""
from __future__ import annotations

import json
from pathlib import Path

from pipa.spend import default_path, format_report, summarize


def _say(msg: str = "") -> None:
    print(msg)


def cmd_spend(args) -> int:
    path = (
        Path(args.log).expanduser() if getattr(args, "log", None)
        else default_path()
    )
    summary = summarize(path, since=args.since)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _say(format_report(summary))
    return 0
