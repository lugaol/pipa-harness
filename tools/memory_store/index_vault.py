#!/usr/bin/env python3
"""
Structured memory store for pipa_harness.
Markdown is the human-readable layer; this module provides the query layer.

Usage:
  python tools/memory_store/index_vault.py    # index vault/ into SQLite
  python tools/memory_store/query.py "blow detection"  # semantic search
"""
import sqlite3
import re
from pathlib import Path
from datetime import datetime

VAULT_DIR = Path(__file__).parent.parent.parent / "vault"
DB_PATH = Path(__file__).parent.parent.parent / "state" / "memory.db"

def index_vault():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE,
            title TEXT,
            content TEXT,
            scope TEXT,  -- decision, research, architecture
            as_of DATE,
            valid_until DATE,
            status TEXT,
            embedding TEXT,  -- JSON array; populated by embedder
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for md_file in VAULT_DIR.rglob("*.md"):
        content = md_file.read_text()
        title_match = re.search(r'^# (.+)', content, re.MULTILINE)
        title = title_match.group(1) if title_match else md_file.stem
        scope = md_file.parent.name
        as_of = re.search(r'as_of:\s*(\S+)', content)
        valid_until = re.search(r'valid_until:\s*(\S+)', content)
        status = re.search(r'status:\s*(\S+)', content)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO memories (path, title, content, scope, as_of, valid_until, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(md_file), title, content, scope,
                 as_of.group(1) if as_of else None,
                 valid_until.group(1) if valid_until else None,
                 status.group(1) if status else "active")
            )
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    print(f"Indexed {VAULT_DIR} into {DB_PATH}")

if __name__ == "__main__":
    index_vault()
