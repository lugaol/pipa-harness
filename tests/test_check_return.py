"""tools/check-subagent-return.sh — scope + secrets gate."""
import subprocess
import sys
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = HARNESS_ROOT / "tools" / "check-subagent-return.sh"


def _run(*args, cwd):
    return subprocess.run(
        [str(SCRIPT), *args], cwd=cwd,
        capture_output=True, text=True, timeout=60)


def _repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "code.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    return repo


def test_clean_tree_passes(tmp_path):
    assert _run(cwd=_repo(tmp_path)).returncode == 0


def test_scope_violation_with_allow(tmp_path):
    repo = _repo(tmp_path)
    (repo / "code.py").write_text("x = 2\n")
    r = _run("--allow", "nothing-here", cwd=repo)
    assert r.returncode == 1
    assert "CHECK-FAIL scope: code.py" in r.stdout


def test_allow_prefix_passes(tmp_path):
    repo = _repo(tmp_path)
    (repo / "code.py").write_text("x = 2\n")
    assert _run("--allow", "code", cwd=repo).returncode == 0


def test_secret_pattern_fails(tmp_path):
    repo = _repo(tmp_path)
    (repo / "code.py").write_text('token = "AKIAIOSFODNN7EXAMPLE"\n')
    r = _run(cwd=repo)
    assert r.returncode == 1
    assert "CHECK-FAIL secrets" in r.stdout


def test_usage_error(tmp_path):
    r = _run("--bogus", cwd=tmp_path)
    assert r.returncode == 2


def test_script_is_executable_and_no_hardcoded_paths():
    import os

    assert os.access(SCRIPT, os.X_OK)
    assert "/Users/" not in SCRIPT.read_text()
