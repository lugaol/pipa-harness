#!/usr/bin/env python3
"""
Lightweight tracing CLI for pipa_harness.

Unified schema owner: hooks/pipa_trace.py (PipaTraceHook). This module keeps
the `start|end|export` CLI but writes the SAME tables/columns so both writers
never conflict (fixes specs/010 2-schema problem).
"""
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "state" / "traces.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    id INTEGER PRIMARY KEY,
    session_id TEXT,
    agent_name TEXT,
    model TEXT,
    tokens_in INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    latency_ms REAL DEFAULT 0,
    tools_called TEXT DEFAULT '[]',
    status TEXT DEFAULT 'success',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS hook_events (
    id INTEGER PRIMARY KEY,
    hook_name TEXT,
    event_type TEXT,
    agent_name TEXT,
    duration_ms REAL DEFAULT 0,
    success BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def start_trace(agent_name, task_type, model_alias="unknown"):
    conn = init_db()
    cur = conn.execute(
        "INSERT INTO traces (session_id, agent_name, model, tools_called, status)"
        " VALUES (?, ?, ?, ?, 'running')",
        ("cli", agent_name, model_alias, json.dumps([task_type])),
    )
    trace_id = cur.lastrowid
    conn.commit()
    conn.close()
    print(f"TRACE_START id={trace_id} agent={agent_name} task={task_type}")


def end_trace(agent_name, task_type, status, tokens, latency_ms):
    conn = init_db()
    conn.execute(
        "UPDATE traces SET status=?, tokens_out=?, latency_ms=? WHERE agent_name=?"
        " AND status='running' ORDER BY id DESC LIMIT 1",
        (status, tokens, latency_ms, agent_name),
    )
    conn.commit()
    conn.close()
    print(f"TRACE_END agent={agent_name} task={task_type} status={status} tokens={tokens} latency={latency_ms}ms")


def export_traces():
    conn = init_db()
    rows = conn.execute(
        "SELECT id, session_id, agent_name, model, tokens_in, tokens_out,"
        " latency_ms, status, created_at FROM traces ORDER BY created_at DESC LIMIT 100"
    ).fetchall()
    conn.close()
    for row in rows:
        print(json.dumps({
            "id": row[0], "session_id": row[1], "agent": row[2], "model": row[3],
            "tokens_in": row[4], "tokens_out": row[5], "latency_ms": row[6],
            "status": row[7], "created_at": row[8],
        }))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: tracing.py start|end|export")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "start":
        start_trace(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "unknown")
    elif cmd == "end":
        end_trace(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]), int(sys.argv[6]))
    elif cmd == "export":
        export_traces()
    else:
        print(f"Unknown command: {cmd}")
