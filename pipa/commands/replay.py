"""pipa replay / diff — flight-recorder session tools."""
from __future__ import annotations

import sys
from pathlib import Path

from pipa import config, session


def _say(msg: str = "") -> None:
    print(msg)


def _die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def _session_log(args) -> Path:
    if getattr(args, "log", None):
        return Path(args.log).expanduser()
    project = config.find_project()
    if project:
        return config.session_log_path(project)
    return config.state_dir() / config.SESSION_LOG


def _parse_ts(ts: str | None) -> float:
    if not ts:
        return 0.0
    try:
        from datetime import datetime
        return datetime.fromisoformat(ts).timestamp()
    except ValueError:
        return 0.0


def _replay_lines(events: list[dict]) -> list[str]:
    t0 = _parse_ts(events[0].get("ts")) if events else 0.0
    lines = []
    for e in events:
        off = _parse_ts(e.get("ts")) - t0
        ev = e.get("event", "?")
        head = f"  +{off:6.1f}s  {ev:<14}"
        detail = e.get("tool") or e.get("model") or ""
        payload = e.get("payload") or e.get("text") or ""
        if payload:
            payload = str(payload).replace("\n", " ")
            payload = payload[:70] + "…" if len(payload) > 70 else payload
            detail = f"{detail}  {payload}" if detail else payload
        meta = ", ".join(
            f"{k}={e[k]}" for k in ("tokens_in", "tokens_out", "cost_usd")
            if e.get(k) is not None
        )
        if meta:
            detail = f"{detail}  ({meta})" if detail else meta
        lines.append(head + (f" {detail}" if detail else ""))
    return lines


def cmd_replay(args) -> int:
    log = _session_log(args)
    all_sessions = session.sessions(log)
    if not all_sessions:
        _say(f"no sessions in {log}")
        return 1
    sid = args.session or all_sessions[-1]["id"]
    events = session.load_session(log, sid)
    if not events:
        known = ", ".join(s["id"] for s in all_sessions[-8:])
        _die(f"no session '{sid}' in {log} (recent: {known})")
    s = next(x for x in all_sessions if x["id"] == sid)
    dur = (_parse_ts(s["end"]) - _parse_ts(s["start"])) if s["end"] else 0.0
    tools = ",".join(sorted(s["tools"])) or "-"
    models = ",".join(sorted(s["models"])) or "-"
    _say(
        f"session {s['id']} · runtime={s['runtime'] or '?'} · "
        f"{s['events']} events · {dur:.0f}s · tools[{tools}] · models[{models}]"
    )
    for line in _replay_lines(events):
        _say(line)
    return 0


def cmd_diff(args) -> int:
    log = _session_log(args)
    a_events = session.load_session(log, args.a)
    b_events = session.load_session(log, args.b)
    if not a_events or not b_events:
        known = ", ".join(s["id"] for s in session.sessions(log)[-8:])
        _die(f"unknown session id(s) in {log} (recent: {known})")

    def profile(evs: list[dict]) -> dict:
        tools: set = set()
        models: set = set()
        tokens = 0
        for e in evs:
            if e.get("tool"):
                tools.add(e["tool"])
            if e.get("model"):
                models.add(e["model"])
            tokens += int(e.get("tokens_in") or 0) + int(e.get("tokens_out") or 0)
        dur = _parse_ts(evs[-1].get("ts")) - _parse_ts(evs[0].get("ts"))
        return {
            "events": len(evs), "dur": max(dur, 0.0),
            "tools": tools, "models": models, "tokens": tokens,
        }

    pa, pb = profile(a_events), profile(b_events)
    _say(f"diff {args.a} vs {args.b}  ({log})")
    rows = [
        ("events", pa["events"], pb["events"]),
        ("duration_s", round(pa["dur"], 1), round(pb["dur"], 1)),
        ("tokens", pa["tokens"], pb["tokens"]),
    ]
    for name, va, vb in rows:
        va_s = str(va) if va != "" else "-"
        vb_s = str(vb) if vb != "" else "-"
        mark = "=" if va == vb else ("A" if vb < va else "B")
        _say(f"  {name:<12} A={va_s:<12} B={vb_s:<12} -> {mark}")
    only_a = sorted(pa["tools"] - pb["tools"])
    only_b = sorted(pb["tools"] - pa["tools"])
    _say(f"  tools only-A {only_a or '-'} · only-B {only_b or '-'}")
    ma, mb = sorted(pa["models"]), sorted(pb["models"])
    _say(f"  models       A={ma or '-'} · B={mb or '-'}")
    return 0
