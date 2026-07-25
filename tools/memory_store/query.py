#!/usr/bin/env python3
"""
Query the structured memory store.
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "state" / "memory.db"

def query_memory(query_text, scope=None, limit=5):
    if not DB_PATH.exists():
        print("Memory DB not found. Run index_vault.py first.")
        return
    conn = sqlite3.connect(DB_PATH)
    sql = "SELECT path, title, scope, as_of, valid_until, status FROM memories WHERE status='active'"
    params = []
    if scope:
        sql += " AND scope=?"
        params.append(scope)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    for row in rows:
        print(f"- {row[1]} ({row[2]}) — {row[0]} [as_of={row[3]}, valid_until={row[4]}]")

if __name__ == "__main__":
    query_memory(sys.argv[1] if len(sys.argv) > 1 else "")
