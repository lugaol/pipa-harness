"""Tests for pipa.recall — unified memory fusion across three stores."""
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from pipa import recall as recall_mod
from pipa.recall import recall

SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE,
    title TEXT,
    content TEXT,
    scope TEXT,
    as_of DATE,
    valid_until DATE,
    status TEXT,
    embedding TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


def _make_db(db_path: Path, rows: list[tuple]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.executemany(
        "INSERT INTO memories (path, title, content, scope, as_of, valid_until,"
        " status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Harness root + project with one populated store of each kind."""
    harness = tmp_path / "harness"
    project = tmp_path / "project"
    future = (date.today() + timedelta(days=365)).isoformat()

    _make_db(project / ".pipa" / "state" / "memory.db", [
        ("notes/blow-detection.md", "Blow detection pipeline",
         "detect blow events via pressure sensor", "analysis",
         "2024-01-01", future, "active"),
        ("notes/unrelated.md", "Unrelated note",
         "nothing to see here", "analysis",
         None, None, "active"),
        ("notes/blow-old.md", "Old blow plan",
         "legacy blow handling", "decisions",
         "1999-01-01", "2000-01-01", "active"),
        ("notes/blow-superseded.md", "Superseded blow plan",
         "replaced blow logic", "decisions",
         None, None, "superseded-by-001"),
    ])
    vault = project / ".pipa" / "extension" / "vault"
    (vault / "research").mkdir(parents=True)
    (vault / "research" / "future-note.md").write_text(
        "---\nas_of: 2024-06-01\nvalid_until: %s\nstatus: active\n---\n"
        "# Future note about blow detection\nbody mentions blow calibration\n"
        % future
    )
    (vault / "decisions").mkdir(parents=True)
    (vault / "decisions" / "old-decision.md").write_text(
        "---\nvalid_until: 2020-01-01\nstatus: active\n---\n"
        "# Old decision on blow valves\nwe chose brass blow valves\n"
    )
    graph_dir = project / "graphify-out"
    graph_dir.mkdir()
    (graph_dir / "graph.json").write_text(json.dumps({
        "nodes": [
            {"id": "blow_sensor", "label": "BlowSensor",
             "type": "class", "path": "src/sensor.py"},
            {"id": "calibrate", "label": "calibrate", "type": "function"},
        ]
    }))

    harness_vault = harness / "vault"
    harness_vault.mkdir(parents=True)
    (harness_vault / "harness-note.md").write_text(
        "# Harness level note about litellm gateway\nrouting via aliases\n"
    )

    monkeypatch.setattr(recall_mod.config, "harness_root", lambda: harness)
    return harness, project


def test_fusion_orders_non_expired_first_then_score(env):
    _, project = env
    out = recall("blow detection", project=project)

    assert out["sources_queried"] == ["memory-db", "vault", "code-graph"]
    results = out["results"]
    assert [r["source"] for r in results[:3]] == [
        "memory-db", "vault", "code-graph",
    ]
    assert all(not r["expired"] for r in results[:3])
    assert all(r["expired"] for r in results[3:])
    scores = [r["score"] for r in results[:3]]
    assert scores == sorted(scores, reverse=True)
    assert results[0]["title"] == "Blow detection pipeline"


def test_expired_flagged_but_never_dropped(env):
    _, project = env
    out = recall("blow detection", project=project)
    expired = [r for r in out["results"] if r["expired"]]
    assert {r["source"] for r in expired} == {"memory-db", "vault"}
    assert any("Old blow plan" == r["title"] for r in expired)
    assert any("Old decision on blow valves" == r["title"] for r in expired)


def test_active_rows_exclude_superseded(env):
    _, project = env
    out = recall("blow detection", project=project)
    assert all("Superseded" not in r["title"] for r in out["results"])


def test_detail_is_bounded_snippet(env):
    _, project = env
    out = recall("blow detection", project=project)
    assert out["results"]
    for hit in out["results"]:
        assert len(hit["detail"]) <= 200
    top = out["results"][0]
    assert "blow" in top["detail"].lower()


def test_empty_and_missing_sources_tolerated(tmp_path, monkeypatch):
    bare_harness = tmp_path / "bare-harness"
    bare_project = tmp_path / "bare-project"
    bare_harness.mkdir()
    bare_project.mkdir()
    monkeypatch.setattr(recall_mod.config, "harness_root", lambda: bare_harness)

    out = recall("anything at all", project=bare_project)
    assert out == {"results": [], "sources_queried": []}

    out_empty_query = recall("   ", project=bare_project)
    assert out_empty_query == {"results": [], "sources_queried": []}


def test_corrupt_graph_json_falls_back_to_vault_only(env):
    harness, project = env
    (project / "graphify-out" / "graph.json").write_text("{not json")
    out = recall("litellm gateway", project=project)
    assert "code-graph" not in out["sources_queried"]
    assert [r["source"] for r in out["results"]] == ["vault"]
    assert "litellm" in out["results"][0]["title"].lower()


def test_harness_stores_used_when_project_has_none(env):
    harness, _ = env
    _make_db(harness / "state" / "memory.db", [
        ("vault/notes/gateway.md", "Gateway routing",
         "litellm alias routing rules", "architecture",
         None, None, "active"),
    ])

    no_store_project = harness.parent / "plain"
    no_store_project.mkdir()
    out = recall("litellm gateway", project=no_store_project)

    assert set(out["sources_queried"]) == {"memory-db", "vault"}
    sources = [r["source"] for r in out["results"]]
    assert sources[0] == "memory-db"
    assert any(r["path"] and "harness-note.md" in r["path"] for r in out["results"])
