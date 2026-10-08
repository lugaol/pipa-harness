#!/usr/bin/env python3
"""Pipa Trace Hook - Emit trace spans to pipa dashboard

Fixes applied per QA review:
- Connection pooling (single connection per instance)
- Lazy-init DB connection
- Error handling throughout
"""
import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class PipaTraceHook:
    """Emit trace spans from OmO to pipa traces.db"""

    _instance = None
    _conn = None

    def __new__(cls, project_root: str = None):
        """Singleton pattern for connection pooling"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, project_root: str = None):
        if self._initialized:
            return
        import os
        self.project_root = Path(project_root or os.getcwd())
        self.pipa_dir = self.project_root / ".pipa"
        self.db_path = self.pipa_dir / "state" / "traces.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._initialized = True

    @property
    def conn(self) -> sqlite3.Connection:
        """Get or create database connection"""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def _init_db(self):
        self.conn.executescript("""
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
        """)

    def emit_trace(self, session_id: str, agent_name: str, model: str,
                   tokens_in: int = 0, tokens_out: int = 0,
                   latency_ms: float = 0, tools_called: list = None,
                   status: str = "success"):
        """Emit a trace span"""
        try:
            self.conn.execute("""
                INSERT INTO traces (session_id, agent_name, model, tokens_in,
                    tokens_out, latency_ms, tools_called, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, agent_name, model, tokens_in, tokens_out,
                  latency_ms, json.dumps(tools_called or []), status))
            self.conn.commit()
        except Exception as e:
            print(f"Warning: Failed to emit trace: {e}")

    def emit_hook_event(self, hook_name: str, event_type: str,
                        agent_name: str = None, duration_ms: float = 0,
                        success: bool = True):
        """Emit a hook execution event"""
        try:
            self.conn.execute("""
                INSERT INTO hook_events (hook_name, event_type, agent_name,
                                         duration_ms, success)
                VALUES (?, ?, ?, ?, ?)
            """, (hook_name, event_type, agent_name, duration_ms, success))
            self.conn.commit()
        except Exception as e:
            print(f"Warning: Failed to emit hook event: {e}")

    def get_recent_traces(self, limit: int = 50) -> list:
        """Get recent traces for dashboard"""
        cursor = self.conn.execute("""
            SELECT session_id, agent_name, model, tokens_in, tokens_out,
                   latency_ms, tools_called, status, created_at
            FROM traces ORDER BY created_at DESC LIMIT ?
        """, (limit,))
        return [
            {
                "session_id": row[0], "agent_name": row[1], "model": row[2],
                "tokens_in": row[3], "tokens_out": row[4], "latency_ms": row[5],
                "tools_called": json.loads(row[6]), "status": row[7],
                "created_at": row[8],
            }
            for row in cursor.fetchall()
        ]

    def get_hook_stats(self) -> Dict[str, Any]:
        """Get hook execution statistics"""
        cursor = self.conn.execute("""
            SELECT hook_name, COUNT(*) as cnt, AVG(duration_ms) as avg_ms,
                   SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes
            FROM hook_events GROUP BY hook_name
        """)
        return {
            row[0]: {"count": row[1], "avg_ms": round(row[2], 2), "success_rate": round(row[3] / row[1], 3)}
            for row in cursor.fetchall()
        }

    def close(self):
        """Close database connection"""
        if self._conn:
            self._conn.close()
            self._conn = None
            PipaTraceHook._instance = None
