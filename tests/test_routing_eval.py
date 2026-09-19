"""Routing evals (Phase 6): validator unit tests + fixture validity."""
import json
import sys
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parents[1]
EVALS_DIR = HARNESS_ROOT / "evals"

if str(HARNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(HARNESS_ROOT))
sys.path.insert(0, str(EVALS_DIR))

import validate


def _cases():
    return json.loads((EVALS_DIR / "routing.json").read_text())["cases"]


def test_fixture_passes_validator():
    cases = _cases()
    assert validate.validate_cases(cases) == []


def test_fixture_has_scale_and_negatives():
    cases = _cases()
    assert len(cases) >= 20
    assert sum(1 for c in cases if c.get("should_trigger") is False) >= 5


def test_unknown_slug_rejected():
    errs = validate.validate_cases(
        [{"id": "x", "prompt": "p", "expect_slugs": ["vhal"]}]
        + [{"id": f"p{i}", "prompt": "p"} for i in range(20)]
        + [{"id": f"n{i}", "prompt": "p", "should_trigger": False} for i in range(5)]
    )
    assert any("unknown slug 'vhal'" in e for e in errs)


def test_union_cap_rejected():
    errs = validate.validate_cases(
        [{"id": "x", "prompt": "p",
          "expect_slugs": ["base", "impl", "security", "review"]}]
    )
    assert any(">3 violates union cap" in e for e in errs)


def test_negative_case_must_not_expect():
    errs = validate.validate_cases(
        [{"id": "x", "prompt": "p", "should_trigger": False,
          "expect_slugs": ["impl"]}]
    )
    assert any("negative case must not expect" in e for e in errs)


def test_missing_prompt_rejected():
    errs = validate.validate_cases([{"id": "x"}])
    assert any("missing prompt" in e for e in errs)


def test_vocab_matches_task_router_doc():
    """Slugs in routing.json must all appear in rules/task-router.md."""
    doc = (HARNESS_ROOT / "rules" / "task-router.md").read_text()
    used = {s for c in _cases() for key in ("expect_slugs", "min_slugs", "forbidden_slugs")
            for s in c.get(key, []) or []}
    assert used <= validate.VOCAB
    for slug in validate.VOCAB:
        assert f"`{slug}`" in doc, f"slug {slug} missing from task-router.md"
