#!/usr/bin/env python3
"""
Agent evals for pipa_harness.
Run with: python tools/evals/run.py

Evals check:
1. All agent files require harness transparency in their output rules
2. @explorer definition mandates file:line refs
3. @qa definition returns PASS/FAIL, never "looks good"
4. @dev definition respects golden rules
5. All agent files have HITL approval gates
"""
import json
import re
import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).parent.parent.parent / "agents"
_ext_base = Path(__file__).parent.parent.parent.parent
EXT_AGENTS_DIR = next(
    (
        _ext_base / rel
        for rel in (".pipa/agents-local", ".pipa/extension/agents", ".harness_extension/agents")
        if (_ext_base / rel).exists()
    ),
    _ext_base / ".pipa" / "agents-local",
)

def check_transparency_rule(content):
    """Check if agent definition requires harness transparency in output."""
    return "Harness transparency" in content or "harness transparency" in content.lower()

def check_explorer_file_line_rule(content):
    """@explorer must mandate file:line refs."""
    return "file:line" in content.lower()

def check_qa_no_looks_good(content):
    """@qa must never say 'looks good'."""
    return "looks good" in content.lower()

def check_dev_golden_rules(content):
    """@dev must reference golden rules."""
    return "golden rules" in content.lower()

def check_approval_gates(content):
    """All agents must gate git push/commit behind a user prompt.

    OpenCode permission actions are allow | ask | deny — "ask" IS the
    approval gate (legacy frontmatter used the invalid value "approval").
    """
    low = content.lower()
    gated = re.search(r'"git (push|commit)"\s*:\s*(ask|approval)', low)
    return bool(gated) and "git push" in low

def run_evals():
    results = []
    agent_files = list(AGENTS_DIR.glob("*.md")) + list(EXT_AGENTS_DIR.glob("*.md"))
    for f in agent_files:
        content = f.read_text()
        result = {
            "file": str(f.relative_to(Path(__file__).parent.parent.parent)),
            "has_transparency_rule": check_transparency_rule(content),
            "has_approval_gates": check_approval_gates(content),
        }
        if "explorer" in f.name:
            result["explorer_file_line_rule"] = {"pass": check_explorer_file_line_rule(content), "msg": "file:line rule present"}
        if "qa" in f.name or "verifier" in f.name:
            result["qa_no_looks_good"] = {"pass": check_qa_no_looks_good(content), "msg": "looks good forbidden"}
        if "dev" in f.name or "implementer" in f.name:
            result["dev_golden_rules"] = {"pass": check_dev_golden_rules(content), "msg": "golden rules referenced"}
        results.append(result)
    return results

if __name__ == "__main__":
    results = run_evals()
    failed = [r for r in results if not all(v.get("pass", True) for v in r.values() if isinstance(v, dict))]
    print(json.dumps({"total": len(results), "failed": len(failed), "results": results}, indent=2))
    sys.exit(1 if failed else 0)
