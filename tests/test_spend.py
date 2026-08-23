"""Tests for the pipa spend ledger aggregator (pipa/spend.py)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipa import spend  # noqa: E402

ROWS = [
    {
        "event": "spend",
        "ts": "2026-08-20T10:00:00+00:00",
        "status": "success",
        "model": "gpt-4o-mini",
        "alias": "fast",
        "tokens_in": 100,
        "tokens_out": 50,
        "cost_usd": 0.0002,
        "latency_ms": 120.5,
    },
    {
        "event": "spend",
        "ts": "2026-08-21T11:00:00+00:00",
        "status": "success",
        "model": "gpt-4o-mini",
        "alias": "fast",
        "tokens_in": 200,
        "tokens_out": 80,
        "cost_usd": 0.0004,
        "latency_ms": 95.0,
    },
    {
        "event": "spend",
        "ts": "2026-08-22T12:00:00+00:00",
        "status": "success",
        "model": "gemini/gemini-2.5-flash",
        "alias": "explore",
        "tokens_in": 1000,
        "tokens_out": 400,
        "cost_usd": 0.0009,
        "latency_ms": 300.25,
    },
]

SECRET = "TOP SECRET PROMPT TEXT"
HOSTILE_ROW = {  # a row that illegally carries content fields — must never surface
    "event": "spend",
    "ts": "2026-08-22T13:00:00+00:00",
    "model": "gpt-4o-mini",
    "alias": "fast",
    "tokens_in": 10,
    "tokens_out": 5,
    "cost_usd": 0.0,
    "prompt": SECRET,
    "messages": [{"role": "user", "content": SECRET}],
}


@pytest.fixture()
def ledger(tmp_path):
    path = tmp_path / "spend.ndjson"
    lines = [json.dumps(r) for r in ROWS]
    lines.append('{"event": "spend", "ts": "broken"')  # corrupt line, must be skipped
    lines.append(json.dumps(HOSTILE_ROW))
    path.write_text("\n".join(lines) + "\n")
    return path


def test_load_skips_corrupt_lines(ledger):
    rows = spend.load(ledger)
    assert len(rows) == len(ROWS) + 1
    assert all(isinstance(r, dict) and r.get("ts") for r in rows)


def test_summarize_totals(ledger):
    s = spend.summarize(ledger)
    assert s["rows"] == 4
    assert s["tokens_in"] == 1310
    assert s["tokens_out"] == 535
    assert s["cost_usd"] == pytest.approx(0.0015)
    assert s["first_ts"] == ROWS[0]["ts"]
    assert s["last_ts"] == HOSTILE_ROW["ts"]


def test_by_model_aggregation(ledger):
    m = spend.summarize(ledger)["by_model"]["gpt-4o-mini"]
    assert m["calls"] == 3
    assert m["tokens_in"] == 310
    assert m["tokens_out"] == 135
    assert m["cost_usd"] == pytest.approx(0.0006)
    g = spend.summarize(ledger)["by_model"]["gemini/gemini-2.5-flash"]
    assert g == {"calls": 1, "tokens_in": 1000, "tokens_out": 400, "cost_usd": pytest.approx(0.0009)}


def test_by_alias_aggregation(ledger):
    s = spend.summarize(ledger)
    assert s["by_alias"]["fast"]["calls"] == 3
    assert s["by_alias"]["explore"]["calls"] == 1


def test_since_filters_rows(ledger):
    s = spend.summarize(ledger, since="2026-08-22T00:00:00+00:00")
    assert s["rows"] == 2
    assert s["tokens_in"] == 1010
    assert set(s["by_alias"]) == {"explore", "fast"}


def test_missing_file_never_raises(tmp_path):
    missing = tmp_path / "nope.ndjson"
    assert spend.load(missing) == []
    s = spend.summarize(missing)
    assert s["rows"] == 0 and s["tokens_in"] == 0 and s["cost_usd"] == 0.0
    assert isinstance(spend.format_report(s), str)


def test_default_path_env_then_home(monkeypatch):
    monkeypatch.setenv("PIPA_SPEND_LOG", "/tmp/pipa-test-spend.ndjson")
    assert spend.default_path() == Path("/tmp/pipa-test-spend.ndjson")
    monkeypatch.delenv("PIPA_SPEND_LOG", raising=False)
    assert spend.default_path() == Path.home() / ".pipa" / "spend.ndjson"


def test_report_and_summary_leak_no_content(ledger):
    summary = spend.summarize(ledger)
    blob = json.dumps(summary)
    report = spend.format_report(summary)
    for text in (blob, report):
        assert SECRET not in text
        assert "prompt" not in text.lower()
        assert "messages" not in text.lower()
