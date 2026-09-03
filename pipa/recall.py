"""Unified memory recall across the harness's three stores.

Fuses results from:
  - memory-db    the SQLite store built by tools/memory_store/index_vault.py
                 (<project>/.pipa/state/memory.db, else harness state/memory.db)
  - vault        raw markdown notes (<project>/.pipa/memory when a project is
                 given, plus <harness>/vault; legacy .pipa/extension/vault and
                 .harness_extension/vault still read for compatibility)
  - code-graph   graphify's knowledge graph (graphify-out/graph.json from the
                 project root, else the harness root)

Everything is parsed defensively: missing files, unknown graph schemas,
corrupt JSON, and malformed dates degrade to fewer results instead of errors.

Scoring is lowercase token overlap weighted by where the match lands
(title/path x3, headings/type x2, body x1). Hits whose valid_until date has
passed are flagged ``expired`` and sorted last, never dropped.

Usage:
    from pipa.recall import recall
    out = recall("blow detection", project=Path("/repo"))
    for hit in out["results"]:
        print(hit["source"], hit["score"], hit["title"])
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import date
from pathlib import Path

from . import config

DETAIL_MAX = 200

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_AS_OF_RE = re.compile(r"as_of:\s*(\S+)")
_VALID_UNTIL_RE = re.compile(r"valid_until:\s*(\S+)")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _clip(text: str, n: int = DETAIL_MAX) -> str:
    collapsed = " ".join(text.split())
    return collapsed[:n]


def _snippet(text: str, toks: set[str], n: int = DETAIL_MAX) -> str:
    """A <=n-char window of text around the first token match."""
    collapsed = " ".join(text.split())
    low = collapsed.lower()
    positions = [low.find(t) for t in sorted(toks)]
    positions = [p for p in positions if p >= 0]
    pos = min(positions) if positions else 0
    start = max(0, pos - 40)
    end = start + n
    prefix = "\u2026" if start > 0 else ""
    suffix = "\u2026" if end < len(collapsed) else ""
    return prefix + collapsed[start:end] + suffix


def _meta_dates(content: str) -> tuple[str | None, str | None]:
    as_of = _AS_OF_RE.search(content)
    valid_until = _VALID_UNTIL_RE.search(content)
    return (
        as_of.group(1) if as_of else None,
        valid_until.group(1) if valid_until else None,
    )


def _parse_iso(raw: str | None) -> date | None:
    if not raw:
        return None
    m = _DATE_RE.search(str(raw))
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(0))
    except ValueError:
        return None


def _is_expired(valid_until_raw: str | None) -> bool:
    d = _parse_iso(valid_until_raw)
    return bool(d and d < date.today())


def _hit(source: str, title: str, detail: str, path: str | None,
         score: float, as_of: str | None, valid_until: str | None) -> dict:
    return {
        "source": source,
        "title": _clip(title, 120),
        "detail": _clip(detail),
        "path": path,
        "score": float(score),
        "as_of": as_of,
        "valid_until": valid_until,
        "expired": _is_expired(valid_until),
    }


def _match_score(toks: set[str], *fields_weight_pairs: tuple[str, float]) -> float:
    """Sum weight per query token appearing as a substring of the field."""
    score = 0.0
    for field, weight in fields_weight_pairs:
        low = (field or "").lower()
        if not low:
            continue
        for t in toks:
            if t in low:
                score += weight
    return score


def _memory_db_path(project: Path | None) -> Path | None:
    candidates = []
    if project:
        candidates.append(Path(project) / ".pipa" / "state" / "memory.db")
    candidates.append(config.state_dir() / "memory.db")
    for c in candidates:
        if c.exists():
            return c
    return None


def _recall_memory_db(toks: set[str], project: Path | None) -> tuple[bool, list[dict]]:
    db = _memory_db_path(project)
    if db is None:
        return False, []
    conds = []
    params: list[str] = []
    for t in sorted(toks):
        like = f"%{t}%"
        conds.append("(title LIKE ? OR path LIKE ? OR scope LIKE ?)")
        params.extend([like, like, like])
    sql = (
        "SELECT title, path, scope, content, as_of, valid_until "
        "FROM memories WHERE status = 'active' AND ("
        + " OR ".join(conds) + ")"
    )
    try:
        conn = sqlite3.connect(db)
    except sqlite3.Error:
        return False, []
    hits: list[dict] = []
    try:
        for title, path, scope, content, as_of, valid_until in conn.execute(sql, params):
            score = _match_score(
                toks,
                (title, 3),
                (path, 3),
                (scope, 2),
                (content, 1),
            )
            if score <= 0:
                continue
            snippet = _snippet(content or "", toks) if content else ""
            hits.append(_hit(
                "memory-db",
                title or (Path(path).stem if path else "(untitled)"),
                snippet or (scope or ""),
                path,
                score,
                as_of,
                valid_until,
            ))
    except sqlite3.Error:
        pass
    finally:
        conn.close()
    return True, hits


def _vault_dirs(project: Path | None) -> list[Path]:
    dirs = []
    if project:
        dirs.append(Path(project) / ".pipa" / "memory")
        dirs.append(Path(project) / ".pipa" / "extension" / "vault")
        dirs.append(Path(project) / ".harness_extension" / "vault")
    dirs.append(config.harness_root() / "vault")
    seen: set[Path] = set()
    unique = []
    for d in dirs:
        r = d.resolve()
        if r not in seen:
            seen.add(r)
            unique.append(d)
    return unique


def _recall_vault(toks: set[str], project: Path | None) -> tuple[bool, list[dict]]:
    dirs = _vault_dirs(project)
    existing = [d for d in dirs if d.is_dir()]
    if not existing:
        return False, []
    hits: list[dict] = []
    seen_files: set[Path] = set()
    for d in existing:
        for md in sorted(d.rglob("*.md")):
            try:
                real = md.resolve()
                if real in seen_files:
                    continue
                seen_files.add(real)
                content = md.read_text(errors="replace")
            except OSError:
                continue
            title_m = _TITLE_RE.search(content)
            title = title_m.group(1).strip() if title_m else md.stem
            headings = "\n".join(_HEADING_RE.findall(content))
            body_lines = [
                ln for ln in content.splitlines() if not _HEADING_RE.match(ln)
            ]
            body = "\n".join(body_lines)
            as_of, valid_until = _meta_dates(content)
            score = _match_score(
                toks,
                (md.stem, 3),
                (str(md.relative_to(d)), 3),
                (headings, 2),
                (body, 1),
            )
            if score <= 0:
                continue
            hits.append(_hit(
                "vault",
                title,
                _snippet(body, toks) if _match_score(toks, (body, 1)) else md.parent.name,
                str(md),
                score,
                as_of,
                valid_until,
            ))
    return True, hits


_GRAPH_LIST_KEYS = ("nodes", "entities", "vertices", "items", "elements")
_NODE_NAME_KEYS = ("name", "label", "id", "title")
_NODE_TYPE_KEYS = ("type", "kind", "category")
_NODE_PATH_KEYS = ("path", "file", "filepath")


def _load_graph_data(project: Path | None):
    roots = []
    if project:
        roots.append(Path(project))
    roots.append(config.harness_root())
    for root in roots:
        gfile = root / "graphify-out" / "graph.json"
        if not gfile.exists():
            continue
        try:
            data = json.loads(gfile.read_text())
        except (OSError, ValueError):
            continue
        if data is not None:
            return data
    return None


def _graph_nodes(data) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in _GRAPH_LIST_KEYS:
            val = data.get(key)
            if isinstance(val, list):
                return val
        for val in data.values():
            if isinstance(val, list):
                return val
    return []


def _node_field(node, keys) -> str | None:
    for k in keys:
        val = node.get(k)
        if isinstance(val, (str, int, float)) and str(val).strip():
            return str(val).strip()
    return None


def _recall_graph(toks: set[str], project: Path | None) -> tuple[bool, list[dict]]:
    data = _load_graph_data(project)
    if data is None:
        return False, []
    hits: list[dict] = []
    for node in _graph_nodes(data):
        if isinstance(node, str):
            name, extra, ntype, npath = node, "", None, None
        elif isinstance(node, dict):
            name = _node_field(node, _NODE_NAME_KEYS)
            ntype = _node_field(node, _NODE_TYPE_KEYS)
            npath = _node_field(node, _NODE_PATH_KEYS)
            extra = " ".join(
                str(v) for k, v in sorted(node.items())
                if isinstance(v, str) and k not in _NODE_NAME_KEYS
            )
        else:
            continue
        if not name:
            continue
        score = _match_score(toks, (name, 3), (ntype, 2), (extra, 1))
        if score <= 0:
            continue
        hits.append(_hit(
            "code-graph",
            name,
            ntype or extra,
            npath,
            score,
            None,
            None,
        ))
    return True, hits


def recall(query: str, project: Path | None = None, limit: int = 8) -> dict:
    """Query all memory stores at once and return fused, ranked hits.

    Returns {"results": [hit...], "sources_queried": [...]} where each hit is:
      {source, title, detail, path, score, as_of, valid_until, expired}
    Expired hits sort last and are never silently dropped.

    Args:
        query: free-text query; tokenized on lowercase alphanumeric runs.
        project: project root for its .pipa/ stores; None uses harness stores.
        limit: maximum number of results returned.
    """
    out: dict = {"results": [], "sources_queried": []}
    toks = _tokens(query)
    if not toks:
        return out
    hits: list[dict] = []

    found, db_hits = _recall_memory_db(toks, project)
    if found:
        out["sources_queried"].append("memory-db")
    hits.extend(db_hits)

    found, vault_hits = _recall_vault(toks, project)
    if found:
        out["sources_queried"].append("vault")
    hits.extend(vault_hits)

    found, graph_hits = _recall_graph(toks, project)
    if found:
        out["sources_queried"].append("code-graph")
    hits.extend(graph_hits)

    hits.sort(key=lambda h: (h["expired"], -h["score"]))
    out["results"] = hits[: max(0, limit)]
    return out
