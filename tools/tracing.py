#!/usr/bin/env python3
"""
Lightweight OpenTelemetry tracing for pipa_harness.
Stores traces in SQLite for local dev; exports to OTel collector when configured.

Usage:
  python tools/tracing.py start <agent_name> <task_type>
  python tools/tracing.py end <agent_name> <status> <tokens> <latency_ms>
  python tools/tracing.py export
"""
import sqlite3
import json
import os
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "state" / "traces.db"

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS traces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent TEXT,
            task_type TEXT,
            status TEXT,
            tokens INTEGER,
            latency_ms INTEGER,
            model_alias TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn

def start_trace(agent_name, task_type, model_alias="unknown"):
    conn = init_db()
    conn.execute(
        "INSERT INTO traces (agent, task_type, status, tokens, latency_ms, model_alias) VALUES (?, ?, ?, ?, ?, ?)",
        (agent_name, task_type, "running", 0, 0, model_alias)
    )
    conn.commit()
    trace_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    print(f"TRACE_START id={trace_id} agent={agent_name} task={task_type}")

def end_trace(agent_name, task_type, status, tokens, latency_ms):
    conn = init_db()
    conn.execute(
        "UPDATE traces SET status=?, tokens=?, latency_ms=? WHERE agent=? AND task_type=? AND status='running' ORDER BY id DESC LIMIT 1",
        (status, tokens, latency_ms, agent_name, task_type)
    )
    conn.commit()
    conn.close()
    print(f"TRACE_END agent={agent_name} task={task_type} status={status} tokens={tokens} latency={latency_ms}ms")

def export_traces():
    conn = init_db()
    rows = conn.execute("SELECT * FROM traces ORDER BY created_at DESC LIMIT 100").fetchall()
    conn.close()
    for row in rows:
        print(json.dumps({
            "id": row[0], "agent": row[1], "task_type": row[2],
            "status": row[3], "tokens": row[4], "latency_ms": row[5],
            "model_alias": row[6], "created_at": row[7]
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
