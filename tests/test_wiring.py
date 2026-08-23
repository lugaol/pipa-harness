"""Behavioral wiring tests: runtime.wire_* global-only wiring and
scaffold.check_extension against throwaway tmp projects/home dirs.
"""
from pathlib import Path

import pytest

from pipa import config, runtime, scaffold

ROOT = Path(__file__).resolve().parents[1]

USER_PATCH_TEXT = "- id: my-own-route\n  config:\n    provider: custom\n"


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def project(tmp_path) -> Path:
    p = tmp_path / "proj"
    (p / ".pipa").mkdir(parents=True)
    return p


def test_wire_dsh_writes_global_patch_and_creds(home, project):
    actions = runtime.wire_deepseek_harness(project=project, root=ROOT)

    patch = home / ".dsh" / "cordis.patch.yml"
    assert patch.exists()
    text = patch.read_text()
    assert "@LITELLM_URL@" not in text
    assert config.LITELLM_URL in text
    assert "pipa" in text[:200]

    creds = home / ".dsh" / ".credentials.yaml"
    assert creds.exists()
    assert "LITELLM_API_KEY" in creds.read_text()


def test_wire_dsh_is_global_only_no_project_files(home, project):
    """Thin projects carry no runtime config — wiring lands in ~/.dsh only."""
    runtime.wire_deepseek_harness(project=project, root=ROOT)
    assert not (project / ".pipa" / "deepseek-harness").exists()
    assert not (project / ".pipa" / "opencode").exists()


def test_wire_dsh_idempotent(home, project):
    runtime.wire_deepseek_harness(project=project, root=ROOT)
    actions = runtime.wire_deepseek_harness(project=project, root=ROOT)
    assert all(not a.startswith("+") for a in actions)


def test_wire_dsh_never_overwrites_user_patch(home, project):
    dsh_home = home / ".dsh"
    dsh_home.mkdir(parents=True)
    user_patch = dsh_home / "cordis.patch.yml"
    user_patch.write_text(USER_PATCH_TEXT)

    actions = runtime.wire_deepseek_harness(project=project, root=ROOT)

    assert user_patch.read_text() == USER_PATCH_TEXT
    assert any(a.startswith("~ kept existing") for a in actions)


def test_wire_opencode_global_only(home):
    actions = runtime.wire_opencode(project=None, root=ROOT)
    gcfg = home / ".config" / "opencode" / "opencode.jsonc"
    assert gcfg.exists()
    text = gcfg.read_text()
    assert "@PIPA_ROOT@" not in text and "@MCP_BLOCK@" not in text
    assert ROOT.as_posix() in text.replace("\\", "/")
    # project overlay globs present so per-project rules load at launch
    assert ".pipa/rules/*.md" in text
    assert any(a.startswith("+") or a.startswith("~") for a in actions)


def test_wire_opencode_merges_mcp_registry(home):
    import json
    mcp_cfg = ROOT / "mcp" / "context7" / "config.json"
    if not mcp_cfg.exists():
        pytest.skip("mcp registry scaffold missing")
    runtime.wire_opencode(project=None, root=ROOT)
    gcfg = home / ".config" / "opencode" / "opencode.jsonc"
    text = gcfg.read_text()
    body = "\n".join(
        ln for ln in text.splitlines() if not ln.strip().startswith("//")
    )
    data = json.loads(body)
    assert "context7" in data["mcp"]
    assert "context7_*" in data["permission"]


def test_gitignore_entries_match_thin_layout():
    joined = "\n".join(scaffold.GITIGNORE_ENTRIES)
    assert f"{config.PIPA_DIR}/state/" in joined
    # generated per-project runtime configs no longer exist
    assert f"{config.PIPA_DIR}/deepseek-harness/" not in joined


def test_check_extension_reports_global_dsh_wiring(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    dsh = fake_home / ".dsh"
    dsh.mkdir(parents=True)
    (dsh / "cordis.patch.yml").write_text("# pipa-managed\n[]\n")
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    target = tmp_path / "fake-proj"
    pipa = target / ".pipa"
    pipa.mkdir(parents=True)
    (pipa / "runtime").write_text("deepseek-harness\n")
    (pipa / "AGENTS.md").write_text(
        "# fake-proj\nAll placeholders are filled already.\n"
    )
    (target / "AGENTS.md").write_text("# fake-proj (root)\n")

    results = {label: ok for ok, label in scaffold.check_extension(target)}
    assert results["runtime selected: deepseek-harness"] is True
    assert results["~/.dsh/cordis.patch.yml wired"] is True


def test_check_extension_accepts_legacy_extension_layout(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    dsh = fake_home / ".dsh"
    dsh.mkdir(parents=True)
    (dsh / "cordis.patch.yml").write_text("# pipa-managed\n[]\n")
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    target = tmp_path / "legacy-proj"
    pipa = target / ".pipa"
    (pipa / "extension").mkdir(parents=True)
    (pipa / "runtime").write_text("deepseek-harness\n")
    (pipa / "extension" / "AGENTS.md").write_text("# legacy\nfilled.\n")
    (target / "AGENTS.md").write_text("# legacy (root)\n")

    results = {label: ok for ok, label in scaffold.check_extension(target)}
    assert results[".pipa/ directory exists"] is True
    assert results["AGENTS.md placeholders are filled"] is True


# ── model composer ──────────────────────────────────────────────────────────

def test_composer_includes_local_excludes_locked_cloud(monkeypatch, tmp_path):
    monkeypatch.delenv("KILO_API_KEY", raising=False)
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(config, "models_dir", lambda: ROOT / "models")

    path, warning = config.compose_litellm_config(root=tmp_path)
    text = path.read_text()
    assert "qwen2.5-coder" in text            # local tier present
    assert "kilo-auto/free" not in text       # kilo excluded (no key)
    assert warning and "kilo.yaml" in warning
    assert ".effective.yaml" in path.name


def test_composer_upgrades_roles_when_keys_present(monkeypatch, tmp_path):
    monkeypatch.setenv("KILO_API_KEY", "test-kilo")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)
    monkeypatch.setattr(config, "models_dir", lambda: ROOT / "models")

    import yaml
    path, _ = config.compose_litellm_config(root=tmp_path)
    data = yaml.safe_load(path.read_text())
    by_name = {m["model_name"]: m for m in data["model_list"]}
    # cloud fragment overrides the local primary alias
    assert by_name["primary"]["litellm_params"]["api_base"].startswith("https://api.kilo.ai")
    # kimi deep stays local (no key)
    assert "moonshot" not in by_name["deep"]["litellm_params"].get("api_base", "")
    assert "callbacks" in data.get("litellm_settings", {})
