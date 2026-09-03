"""Code-graph status + query for the graphify knowledge plane.

graphify-out/graph.json is the artifact agents are told to query BEFORE
grep (AGENTS.md). This module reports whether that pillar is actually
alive for a project and answers queries via the `graphify` CLI when
installed, falling back to scored node scans of graph.json otherwise.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from pipa import config

QUERY_TIMEOUT_S = 20


def _project_root(project_path: Optional[str]) -> Path:
    if project_path:
        return Path(project_path)
    try:
        found = config.find_project()
        if found:
            return found
    except Exception:
        pass
    return config.harness_root()


def _graph_file(root: Path) -> Optional[Path]:
    cand = root / "graphify-out" / "graph.json"
    return cand if cand.is_file() else None


def status(project_path: Optional[str] = None) -> dict:
    root = _project_root(project_path)
    gfile = _graph_file(root)
    harness_gfile = _graph_file(config.harness_root())
    nodes = 0
    if gfile:
        try:
            data = json.loads(gfile.read_text())
            items = data if isinstance(data, list) else (
                data.get("nodes") or data.get("entities")
                or next((v for v in data.values() if isinstance(v, list)), [])
            )
            nodes = len(items) if isinstance(items, list) else 0
        except (OSError, ValueError):
            pass
    return {
        "root": str(root),
        "has_graph": gfile is not None,
        "graph_path": str(gfile) if gfile else "",
        "nodes": nodes,
        "harness_has_graph": harness_gfile is not None,
        "cli": shutil.which("graphify") or "",
    }


def query(q: str, project_path: Optional[str] = None) -> dict:
    """Run `graphify query` when available; always add scored fallback hits."""
    st = status(project_path)
    cli_out, cli_err = "", ""
    if q.strip() and st["cli"]:
        try:
            proc = subprocess.run(
                [st["cli"], "query", q],
                cwd=st["root"], capture_output=True, text=True,
                timeout=QUERY_TIMEOUT_S,
            )
            cli_out = (proc.stdout or "").strip()[:4000]
            if proc.returncode != 0:
                cli_err = (proc.stderr or f"exit {proc.returncode}").strip()[:400]
        except subprocess.TimeoutExpired:
            cli_err = f"graphify query timed out after {QUERY_TIMEOUT_S}s"
        except OSError as exc:
            cli_err = str(exc)[:400]

    hits: List[dict] = []
    if q.strip():
        try:
            from pipa.recall import recall as do_recall
            out = do_recall(
                q, project=Path(st["root"]) if project_path else None, limit=12)
            hits = [h for h in out.get("results", []) if h.get("source") == "code-graph"]
        except Exception:
            hits = []
    return {"status": st, "cli_out": cli_out, "cli_err": cli_err, "hits": hits}
