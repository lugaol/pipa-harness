"""MCP bridge convention (Phase 7): template self-test + registry hygiene."""
import json
import subprocess
import sys
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parents[1]
BRIDGE = HARNESS_ROOT / "mcp" / "_template" / "example_bridge.py"

if str(HARNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(HARNESS_ROOT))


def test_template_self_test_passes():
    r = subprocess.run([sys.executable, str(BRIDGE), "--self-test"],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["ok"] is True


def test_template_status_shape():
    r = subprocess.run([sys.executable, str(BRIDGE), "--status"],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    assert set(payload) == {"ok", "detail"}
    assert isinstance(payload["ok"], bool)


def test_template_tool_roundtrip_and_soft_failure():
    r = subprocess.run([sys.executable, str(BRIDGE), "--example", "ada"],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0
    assert json.loads(r.stdout) == {"greeting": "hello, ada"}
    bad = subprocess.run([sys.executable, str(BRIDGE), "--example", "  "],
                         capture_output=True, text=True, timeout=30)
    assert bad.returncode == 1
    assert "Traceback" not in bad.stderr  # soft failure, no traceback


def test_template_never_merges_into_registry():
    from pipa import config
    from pipa.runtime import _mcp_registry

    servers = _mcp_registry(config.harness_root())
    assert not any(str(v).startswith("python3 mcp/example") or k == "example"
                   for k, v in servers.items())
    from dashboard.data import mcp as mcp_data

    names = [s["name"] for s in mcp_data.list_servers()]
    assert "_template" not in names and "example" not in names
