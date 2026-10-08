#!/usr/bin/env python3
"""
Agent evals for pipa_harness.
Run with: python tools/evals/run.py

Every check returns {"pass": bool, "msg": str}. Nothing else. A bare bool in
the result dict is silently dropped by the pass/fail rollup below, which is
how this suite came to report 0 failures while every agent was missing the
reporting mandate. Keep the shape uniform.

Checks, per agent file:
  1. reports_delegation   — ends with the `{"event":"delegation",...}` line
                            that `pipa contract` parses (AGENTS.md Reporting)
  2. no_hardcoded_model   — frontmatter pins a TIER alias, never a model id
                            (AGENTS.md: "a hardcoded id is a future HTTP 400")
  3. has_approval_gates   — git push/commit gated behind an ask
  4. uses_bus             — reads the sibling bus before exploring
Role-specific: explorer cites file:line, qa forbids "looks good",
dev references the golden rules.

Exit 0 = pass, 1 = at least one check failed.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
AGENTS_DIR = ROOT / "agents"
_ext_base = ROOT.parent
EXT_AGENTS_DIR = next(
    (
        _ext_base / rel
        for rel in (".pipa/agents-local", ".pipa/extension/agents", ".harness_extension/agents")
        if (_ext_base / rel).exists()
    ),
    _ext_base / ".pipa" / "agents-local",
)

# Tier aliases the gateway resolves from state/tier_assignments.json. An agent
# frontmatter `model:` must be litellm/<one of these>, never a concrete id.
TIER_ALIASES = ("lowest", "low", "mid", "high", "xhigh")


def _check(passed, msg, fail_msg=None):
    """Uniform check shape. Keeps the rollup honest."""
    return {"pass": bool(passed), "msg": msg if passed else (fail_msg or msg)}


def check_delegation_report(content):
    """Every agent ends with the machine-readable delegation line."""
    ok = '"event":"delegation"' in content.replace(" ", "")
    return _check(ok, "delegation report line present",
                  "missing the {\"event\":\"delegation\",...} report line "
                  "(AGENTS.md Reporting; `pipa contract` reads these)")


def check_no_hardcoded_model(content, fm):
    """Frontmatter `model:` must be a tier alias, not a model id."""
    model = (fm.get("model") or "").strip()
    if not model:
        return _check(True, "no model pin (inherits the runtime default)")
    bare = model.split("/", 1)[-1]
    ok = bare in TIER_ALIASES
    return _check(
        ok, f"model pinned to tier {bare!r}",
        f"model {model!r} hardcodes a model id — use a tier alias "
        f"(litellm/<{'|'.join(TIER_ALIASES)}>) so tier changes take effect",
    )


def check_approval_gates(content):
    """git push/commit must be impossible without the user.

    Two acceptable shapes, both real gates:
      * bash denied outright (router: it classifies, it never touches the repo)
      * git push/commit set to "ask" (agents that may legitimately commit)
    OpenCode permission actions are allow | ask | deny — "ask" IS the gate.
    """
    low = content.lower()
    denied = re.search(r'(?m)^\s*bash:\s*(\n\s+)?"\*?\*?"?\s*:\s*deny\b', low) or \
        re.search(r'"git (push|commit)"\s*:\s*deny', low)
    asked = re.search(r'"git (push|commit)"\s*:\s*(ask|approval)', low)
    return _check(bool(denied or asked), "git push/commit gated",
                  'no git gate — either deny bash, or permission: "git push": ask')


def check_uses_bus(content):
    """Agents read the sibling bus before broad exploration."""
    return _check("pipa bus read" in content, "reads the bus",
                  "never reads the sibling bus (`pipa bus read --to <agent>`)")


def check_file_line_refs(content):
    return _check("file:line" in content.lower(), "cites file:line",
                  "must cite file:line so the caller can navigate")


def check_qa_no_looks_good(content):
    """qa must FORBID the phrase, not merely omit it."""
    low = content.lower()
    forbids = re.search(r'(never|do not|don\'t|no \w+ may)\s+[^.\n]{0,30}looks good', low)
    return _check(bool(forbids), "forbids 'looks good'",
                  "must forbid 'looks good' outright — verdicts are PASS/FAIL + evidence")


def check_dev_golden_rules(content):
    return _check("golden rules" in content.lower(), "references golden rules",
                  "must reference the golden rules")


def _frontmatter(text):
    """Flat `key: value` frontmatter (PIPA's subset — no nested maps)."""
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    out = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.startswith((" ", "\t", "#")) or ":" not in line:
            continue
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip().strip("'\"")
    return out


def run_evals():
    results = []
    agent_files = sorted(AGENTS_DIR.glob("*.md")) + sorted(EXT_AGENTS_DIR.glob("*.md"))
    for f in agent_files:
        content = f.read_text()
        name = f.stem.lower()
        checks = {
            "delegation_report": check_delegation_report(content),
            "no_hardcoded_model": check_no_hardcoded_model(content, _frontmatter(content)),
            "approval_gates": check_approval_gates(content),
            "uses_bus": check_uses_bus(content),
        }
        if "explorer" in name:
            checks["file_line_refs"] = check_file_line_refs(content)
        if "qa" in name or "verifier" in name:
            checks["qa_no_looks_good"] = check_qa_no_looks_good(content)
        if "dev" in name or "implementer" in name:
            checks["dev_golden_rules"] = check_dev_golden_rules(content)
        results.append({"file": str(f.relative_to(ROOT)), "checks": checks})
    return results


def main() -> int:
    results = run_evals()
    failures = [
        {"file": r["file"], "check": name, "why": c["msg"]}
        for r in results
        for name, c in r["checks"].items()
        if not c["pass"]
    ]
    total = sum(len(r["checks"]) for r in results)
    print(json.dumps(
        {"total": total, "failed": len(failures), "failures": failures,
         "results": results},
        indent=2,
    ))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())