#!/usr/bin/env python3
"""
Structured memory store for pipa_harness.
Markdown is the human-readable layer; this module provides the query layer.

Usage:
  # Index the base harness vault (default)
  python tools/memory_store/index_vault.py

  # Index a project extension vault into its own state DB
  python tools/memory_store/index_vault.py /path/to/project

  # Index multiple projects (one DB per project)
  python tools/memory_store/index_vault.py /path/to/project1 /path/to/project2
"""
import sqlite3
import re
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


def _db_path(project_root: Optional[Path]) -> Path:
    if project_root:
        pipa_state = project_root / ".pipa" / "state" / "memory.db"
        legacy = project_root / ".harness_extension" / "state" / "memory.db"
        return pipa_state if pipa_state.exists() or not legacy.exists() else legacy
    return Path(__file__).parent.parent.parent / "state" / "memory.db"


def _vault_dir(project_root: Optional[Path]) -> Path:
    if project_root:
        pipa_vault = project_root / ".pipa" / "extension" / "vault"
        legacy = project_root / ".harness_extension" / "vault"
        return pipa_vault if pipa_vault.exists() or not legacy.exists() else legacy
    return Path(__file__).parent.parent.parent / "vault"


def index_vault(project_root: Optional[Path] = None):
    vault_dir = _vault_dir(project_root)
    db_path = _db_path(project_root)

    if not vault_dir.exists():
        print(f"Vault not found: {vault_dir}")
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE,
            title TEXT,
            content TEXT,
            scope TEXT,  -- decision, research, architecture, analysis
            as_of DATE,
            valid_until DATE,
            status TEXT,
            embedding TEXT,  -- JSON array; populated by embedder
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for md_file in vault_dir.rglob("*.md"):
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
    print(f"Indexed {vault_dir} into {db_path}")


if __name__ == "__main__":
    projects = [Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else [None]
    for project in projects:
        index_vault(project)
