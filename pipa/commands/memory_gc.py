"""pipa memory-gc — retention GC for summaries + scratch (dry-run default)."""
from __future__ import annotations

import os

from pipa import memory_gc as gc_lib


def cmd_memory_gc(args) -> int:
    import json

    from pipa import config

    summaries_days = int(getattr(args, "summaries_days", 0) or
                         os.environ.get("SUMMARIES_RETENTION_DAYS", "180"))
    scratch_days = int(getattr(args, "scratch_days", 0) or
                       os.environ.get("SCRATCH_RETENTION_DAYS", "30"))
    state_dir = config.state_dir()
    vault = config.harness_root() / "vault"
    if getattr(args, "manifest", False):
        cands = gc_lib.collect_candidates(state_dir, vault, summaries_days, scratch_days)
        print(json.dumps({
            "summaries_days": summaries_days, "scratch_days": scratch_days,
            "eligible": len(cands),
            "by_action": {a: sum(1 for _, (x, _) in cands.items() if x == a)
                          for a in ("rollup", "prune", "report")},
        }, indent=2))
        return 0
    cands = gc_lib.collect_candidates(state_dir, vault, summaries_days, scratch_days)
    print(f"Retention: summaries > {summaries_days}d, scratch > {scratch_days}d")
    print(f"Eligible files: {len(cands)}")
    for rel, (action, reason) in sorted(cands.items()):
        print(f"  [{action}] {rel} ({reason})")
    if not cands:
        print("Nothing to prune.")
        return 0
    if not getattr(args, "apply", False):
        print("Dry run — re-run with --apply to roll up + prune.")
        return 0
    result = gc_lib.apply_gc(state_dir, cands)
    print(f"Wrote {result['rollups_written']} rollup(s), pruned "
          f"{result['summaries_pruned']} summar(ies), deleted "
          f"{result['scratch_deleted']} scratch file(s), "
          f"{result['reported']} over-budget note(s) reported.")
    return 0


def build_subparser(sub) -> None:
    p = sub.add_parser("memory-gc", help="retention GC for summaries + scratch (dry-run default)")
    p.add_argument("--apply", action="store_true", help="roll up + prune (default is dry-run preview)")
    p.add_argument("--manifest", action="store_true", help="print JSON eligibility manifest and exit")
    p.add_argument("--summaries-days", type=int, default=0, help="summaries older than N days (default 180)")
    p.add_argument("--scratch-days", type=int, default=0, help="scratch older than N days (default 30)")
    p.set_defaults(func=cmd_memory_gc)
