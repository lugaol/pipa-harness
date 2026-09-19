"""QA-verdict eval: structured verdicts validate against the schema rules."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))

from validate import validate_verdict

GOOD_PASS = {
    "status": "PASS",
    "story": "specs/refactor-a-dedup/PLAN.md (A3)",
    "criteria": [
        {"criterion": "routes byte-identical",
         "result": "pass",
         "evidence": "pytest tests/test_api.py -q: 42 passed"},
        {"criterion": "state restored after live roundtrips",
         "result": "pass",
         "evidence": "state/tier_assignments.json identical before/after"},
    ],
    "build": "python3 -m pytest tests/ -q: 198 passed",
    "route_tier": "mid",
}

GOOD_FAIL = {
    "status": "FAIL",
    "story": "specs/demo/01.md",
    "criteria": [
        {"criterion": "tests green",
         "result": "fail",
         "evidence": "pytest: 1 failed — tests/test_x.py::test_y (assert 200 == 500)",
         "file": "tests/test_x.py:12"},
    ],
    "build": "python3 -m pytest tests/ -q: 1 failed, 197 passed",
}


def test_valid_pass_verdict():
    assert validate_verdict(GOOD_PASS) == []


def test_valid_fail_verdict():
    assert validate_verdict(GOOD_FAIL) == []


def test_rejects_missing_keys():
    assert validate_verdict({"status": "PASS"}) != []


def test_rejects_bad_status():
    bad = dict(GOOD_PASS, status="MAYBE")
    assert validate_verdict(bad) != []


def test_rejects_criterion_without_evidence():
    bad = dict(GOOD_PASS)
    bad["criteria"] = [{"criterion": "x", "result": "pass", "evidence": ""}]
    assert validate_verdict(bad) != []


def test_rejects_inconsistent_fail():
    bad = dict(GOOD_PASS, status="FAIL")
    assert validate_verdict(bad) != []


def test_rejects_inconsistent_pass():
    bad = dict(GOOD_FAIL, status="PASS")
    assert validate_verdict(bad) != []


def test_rejects_unknown_keys():
    bad = dict(GOOD_PASS, emulator="N/A")
    assert validate_verdict(bad) != []
