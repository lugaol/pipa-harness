"""pipa usage-report — team adoption rollup (sessions + spend)."""
from __future__ import annotations

import json
from pathlib import Path

from pipa import config
from pipa import metrics as metrics_lib


def cmd_usage_report(args) -> int:
    from pipa import session as session_mod, spend as spend_mod

    project = config.find_project()
    log = config.session_log_path(project) if project else None
    summaries = session_mod.sessions(log) if log and log.exists() else []
    spend = spend_mod.summarize(getattr(args, "since", None) or None)
    report = metrics_lib.build_report(summaries, spend)
    if getattr(args, "json", False):
        print(json.dumps(report, indent=2))
    else:
        print(metrics_lib.format_report(report))
    return 0


def build_subparser(sub) -> None:
    p = sub.add_parser("usage-report",
                       help="adoption rollup: sessions per day, top tools/models, spend")
    p.add_argument("--since", help="spend rows at/after this ISO ts")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_usage_report)
