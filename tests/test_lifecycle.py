"""Lifecycle commands (update/diagnose) + Install job runner (Phase 4)."""
import sys
import time
from pathlib import Path
from types import SimpleNamespace

HARNESS_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = HARNESS_ROOT / "dashboard"

for _p in (str(HARNESS_ROOT), str(DASHBOARD_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def test_version_prints(capsys):
    from pipa.commands.lifecycle import cmd_version

    assert cmd_version(SimpleNamespace()) == 0
    out = capsys.readouterr().out
    assert out.startswith("pipa ")


def test_update_refuses_dirty_tree(monkeypatch, capsys):
    import pipa.commands.lifecycle as lifecycle

    monkeypatch.setattr(
        lifecycle, "_git",
        lambda args, timeout=20: (True, " M dirty-file\n")
        if args[:2] == ["status", "--porcelain"] else (False, ""),
    )
    assert lifecycle.cmd_update(SimpleNamespace()) == 1
    assert "local changes" in capsys.readouterr().err


def test_update_fast_forwards_when_clean(monkeypatch, capsys):
    import pipa.commands.lifecycle as lifecycle

    calls = []

    def fake_git(args, timeout=20):
        calls.append(args)
        if args[:2] == ["status", "--porcelain"]:
            return True, ""
        return True, "Already up to date."

    monkeypatch.setattr(lifecycle, "_git", fake_git)
    assert lifecycle.cmd_update(SimpleNamespace()) == 0
    assert ["pull", "--ff-only"] in calls


def test_check_update_offline_is_best_effort(monkeypatch, capsys):
    import pipa.commands.lifecycle as lifecycle

    monkeypatch.setattr(
        lifecycle, "_git",
        lambda args, timeout=20: (True, "abc123")
        if args[:2] == ["rev-parse", "HEAD"] else (False, ""),
    )
    assert lifecycle.cmd_check_update(SimpleNamespace()) == 0
    assert "unreachable" in capsys.readouterr().out


def test_diagnose_always_zero_and_complete(monkeypatch, tmp_path, capsys):
    import pipa.commands.lifecycle as lifecycle
    from pipa import config

    mdir = tmp_path / "models"
    mdir.mkdir()
    (mdir / "settings.yaml").write_text("litellm_settings: {}\n")
    monkeypatch.setattr(config, "models_dir", lambda: mdir)
    monkeypatch.setattr(config, "state_dir", lambda: tmp_path / "state")
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    assert lifecycle.cmd_diagnose(SimpleNamespace()) == 0
    out = capsys.readouterr().out
    for marker in ("port 4000", "port 11434", "gateway-config", "ollama probe"):
        assert marker in out, marker


def test_install_runner_scrubs_secrets(monkeypatch):
    from data import installer

    monkeypatch.setenv("LITELLM_KEY", "sk-dummy-secret-abcdef")
    result = installer.run(
        "echo-test",
        [sys.executable, "-c", "print('key=sk-dummy-secret-abcdef done')"],
    )
    assert result["ok"] is True
    for _ in range(100):
        snap = installer.snapshot()
        if not snap["running"]:
            break
        time.sleep(0.05)
    lines = installer.snapshot()["lines"]
    assert lines and lines[0].startswith("$")
    output = [ln for ln in lines if not ln.startswith("$")]
    assert output, "job produced no output lines"
    assert "sk-dummy-secret-abcdef" not in "\n".join(output)
    assert "***" in "\n".join(output)


def test_install_runner_single_flight():
    from data import installer

    first = installer.run(
        "slow-job",
        [sys.executable, "-c", "import time; time.sleep(30)"],
    )
    assert first["ok"] is True
    try:
        second = installer.run("other", [sys.executable, "-c", "print(1)"])
        assert second["ok"] is False
        assert "still running" in second["error"]
    finally:
        proc = installer._job["proc"]
        proc.kill()
        proc.wait()
        for _ in range(100):
            if not installer.snapshot()["running"]:
                break
            time.sleep(0.05)
        assert installer.snapshot()["running"] is False


def test_install_unknown_component_rejected():
    from data import installer

    result = installer.run_install("not-a-component")
    assert result["ok"] is False
    assert "unknown component" in result["error"]


def test_install_page_module_and_template():
    import importlib

    module = importlib.import_module("pages.install")
    assert len(module.router.routes) > 0
    assert (HARNESS_ROOT / "dashboard" / "templates" / "install.html").is_file()
    routes = [getattr(r, "path", "") for r in module.router.routes]
    assert "/api/install/run" in routes and "/api/install/log" in routes
