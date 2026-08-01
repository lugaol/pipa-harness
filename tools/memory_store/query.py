#!/usr/bin/env python3
"""
Query the structured memory store.

Usage:
  # Query the base harness memory
  python tools/memory_store/query.py "blow detection"

  # Query a project extension memory
  python tools/memory_store/query.py --project /path/to/project "blow detection"
"""
import argparse
import sqlite3
from pathlib import Path
from typing import Optional


def _db_path(project_root: Optional[Path]) -> Path:
    if project_root:
        return project_root / ".harness_extension" / "state" / "memory.db"
    return Path(__file__).parent.parent.parent / "state" / "memory.db"


def query_memory(query_text, project_root: Optional[Path] = None, scope=None, limit=5):
    db_path = _db_path(project_root)
    if not db_path.exists():
        print(f"Memory DB not found: {db_path}. Run index_vault.py first.")
        return
    conn = sqlite3.connect(db_path)
    sql = "SELECT path, title, scope, as_of, valid_until, status FROM memories WHERE status='active'"
    params = []
    if scope:
        sql += " AND scope=?"
        params.append(scope)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    if not rows:
        print("No matching memories found.")
    for row in rows:
        print(f"- {row[1]} ({row[2]}) — {row[0]} [as_of={row[3]}, valid_until={row[4]}]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query the pipa harness memory store")
    parser.add_argument("query", nargs="?", default="", help="Query text")
    parser.add_argument("--project", type=Path, help="Project root whose extension vault to query")
    parser.add_argument("--scope", help="Filter by scope (decision, research, architecture, analysis)")
    parser.add_argument("--limit", type=int, default=5, help="Maximum results")
    args = parser.parse_args()
    query_memory(args.query, args.project, args.scope, args.limit)
