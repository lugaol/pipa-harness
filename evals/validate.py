#!/usr/bin/env python3
"""Router eval validator: checks routing.json shape + slug vocabulary + budget.

Usage: python3 evals/validate.py [--strict]
- Validates every case has id/prompt and (expect_slugs|min_slugs|should_trigger).
- Validates slugs against the router's Slug column vocabulary (rules/task-router.md).
- Fails on >3 expected slugs (union cap), unknown slugs, or negative cases
  that expect a forbidden slug.
Exit 0 = pass. Wire to CI + run on every router/skill edit.
Ported from ia_harness evals/validate.py, generalized (no AOSP slugs).
"""
import json
import sys
from pathlib import Path

VOCAB = {
    "base", "playbook", "memory", "impl", "network", "build-failure",
    "hard-bug", "tdd", "build", "full-test", "perf", "security",
    "review", "merge", "multi-story", "handoff", "meta", "docs",
    "delegate", "triage",
}


def validate_cases(cases: list) -> list:
    """Return a list of error strings (empty = pass). Pure: no I/O."""
    errors: list[str] = []
    if len(cases) < 20:
        errors.append(f"need >=20 cases, have {len(cases)}")
    negs = [c for c in cases if c.get("should_trigger") is False]
    if len(negs) < 5:
        errors.append(f"need >=5 negative cases, have {len(negs)}")
    for c in cases:
        cid = c.get("id", "?")
        if not c.get("prompt"):
            errors.append(f"{cid}: missing prompt")
        for key in ("expect_slugs", "min_slugs", "forbidden_slugs"):
            for s in c.get(key, []) or []:
                if s not in VOCAB:
                    errors.append(f"{cid}: unknown slug {s!r} in {key}")
        exp = c.get("expect_slugs", []) or []
        if len(exp) > 3:
            errors.append(f"{cid}: expect_slugs >3 violates union cap (base+2)")
        if c.get("should_trigger") is False:
            for s in exp:
                errors.append(f"{cid}: negative case must not expect {s!r}")
        if "--strict" in sys.argv and not c.get("should_trigger") is False and not exp:
            errors.append(f"{cid}: positive case needs expect_slugs")
    return errors


VERDICT_REQUIRED = ("status", "criteria", "build")


def validate_verdict(verdict: dict) -> list:
    """Return error strings for a QA verdict dict (empty = pass). Pure: no I/O.

    Mirrors evals/qa-verdict.schema.json without a jsonschema dependency:
    required keys, PASS/FAIL status, non-empty criteria with per-criterion
    result + evidence, and status/criteria consistency (FAIL needs a fail,
    PASS needs no fail).
    """
    errors: list[str] = []
    if not isinstance(verdict, dict):
        return ["verdict must be an object"]
    for key in VERDICT_REQUIRED:
        if key not in verdict:
            errors.append(f"missing required key: {key}")
    allowed = {*VERDICT_REQUIRED, "story", "route_tier", "model_id"}
    for key in verdict:
        if key not in allowed:
            errors.append(f"unknown key: {key!r}")
    if verdict.get("status") not in ("PASS", "FAIL"):
        errors.append("status must be PASS or FAIL")
    criteria = verdict.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        errors.append("criteria must be a non-empty list")
        return errors
    results = []
    for i, c in enumerate(criteria):
        if not isinstance(c, dict):
            errors.append(f"criteria[{i}]: must be an object")
            continue
        if not c.get("criterion"):
            errors.append(f"criteria[{i}]: missing criterion")
        if c.get("result") not in ("pass", "fail"):
            errors.append(f"criteria[{i}]: result must be pass or fail")
        if not c.get("evidence"):
            errors.append(f"criteria[{i}]: missing evidence (command output or file:line)")
        results.append(c.get("result"))
    if verdict.get("status") == "FAIL" and "fail" not in results:
        errors.append("FAIL verdict needs at least one failing criterion")
    if verdict.get("status") == "PASS" and "fail" in results:
        errors.append("PASS verdict must not contain a failing criterion")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parent
    cases = json.loads((root / "routing.json").read_text())["cases"]
    errors = validate_cases(cases)
    negs = sum(1 for c in cases if c.get("should_trigger") is False)
    if errors:
        print(f"[FAIL] routing eval: {len(errors)} error(s)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"[OK] routing eval: {len(cases)} cases ({negs} negative), vocab + cap OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
