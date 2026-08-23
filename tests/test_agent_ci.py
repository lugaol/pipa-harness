"""Tests for Agent CI: composite action, workflow trigger, docs."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_yaml(relpath):
    return yaml.safe_load((ROOT / relpath).read_text())


def test_action_is_composite():
    action = load_yaml("action.yml")
    assert action["runs"]["using"] == "composite"


def test_workflow_triggers_on_pull_request():
    workflow = load_yaml(".github/workflows/agent-evals.yml")
    triggers = workflow.get("on", workflow.get(True))
    assert "pull_request" in triggers


def test_docs_exist_and_mention_eval_runner():
    docs = ROOT / "docs" / "AGENT_CI.md"
    assert docs.exists()
    assert "run.py" in docs.read_text()
