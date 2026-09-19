"""pipa triage — the only loop, capped at L1 (report-only).

Gathers bounded signals (doctor, graph freshness, memory staleness/GC,
session volume), prints them, and rewrites vault/triage/STATE.md.
No code edits, no commits, no pushes, no auto-fix — ever.
"""
from __future__ import annotations

STATE_SCHEMA = """# Triage STATE — {date}
route: triage · tier lowest · <model>
signals: doctor={doctor} graph={graph} stale_notes={stale} gc={gc} sessions_7d={sessions}
needs-human: {needs}
watch-list: {watch}
next-run: {next_run}
"""


def _state_path():
    from pipa import config

    d = config.harness_root() / "vault" / "triage"
    d.mkdir(parents=True, exist_ok=True)
    return d / "STATE.md"


def cmd_triage(args) -> int:
    import json
    from datetime import date, timedelta

    from pipa import config, triage as triage_lib

    project = config.find_project()
    signals = triage_lib.collect_signals(project)
    needs = triage_lib.needs_human(signals)
    if getattr(args, "json", False):
        print(json.dumps({**signals, "needs_human": needs}, indent=2))
        return 0
    doc = signals["doctor"]
    graph = signals["graph"]
    mem = signals["memory"]
    sess = signals["sessions"]
    gc = mem.get("gc") or {}
    print(f"triage · {signals['at']} · pipa v{signals['version']}")
    print(f"  doctor: {doc['status']} ({doc.get('detail', '')})")
    print(f"  graph: harness={graph.get('harness')} project={graph.get('project')}")
    stale = mem.get("stale_notes")
    print(f"  memory: stale_notes={stale} "
          f"gc={{rollup={gc.get('rollup')}, prune={gc.get('prune')}, "
          f"report={gc.get('report')}}}")
    print(f"  sessions: {sess.get('detail', '')} errors_7d={sess.get('errors_7d')}")
    if needs:
        print("  needs-human:")
        for n in needs:
            print(f"    - {n}")
    else:
        print("  all quiet.")
    if not getattr(args, "no_write", False):
        today = date.today()
        state = STATE_SCHEMA.format(
            date=today.isoformat(),
            doctor=doc["status"],
            graph=f"harness:{graph.get('harness')}/project:{graph.get('project')}",
            stale=stale,
            gc=(f"{gc.get('rollup') or 0}r+{gc.get('prune') or 0}p"
                if gc else "unknown"),
            sessions=sess.get("sessions_7d"),
            needs="; ".join(needs) if needs else "-",
            watch="-",
            next_run=(today + timedelta(days=1)).isoformat(),
        )
        try:
            _state_path().write_text(state)
        except OSError as exc:
            print(f"  (STATE.md unwritten: {exc})")
    return 0


def build_subparser(sub) -> None:
    p = sub.add_parser("triage", help="L1 report-only loop: signals + STATE.md (no fixes)")
    p.add_argument("--json", action="store_true", help="machine-readable signals + needs_human")
    p.add_argument("--no-write", action="store_true", help="print only, do not rewrite STATE.md")
    p.set_defaults(func=cmd_triage)
