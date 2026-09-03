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


def test_wire_opencode_installs_session_bus_plugin(home):
    runtime.wire_opencode(project=None, root=ROOT)
    plugin = home / ".config" / "opencode" / "plugin" / "pipa-session-bus.js"
    assert plugin.is_file()
    text = plugin.read_text()
    # placeholders substituted; hook target points at the harness bin
    assert "@@PIPA_BIN@@" not in text and "@@PIPA_RUNTIME@@" not in text
    assert (ROOT / "bin" / "pipa").as_posix() in text.replace("\\", "/")
    assert '"opencode"' in text

    # idempotent + create-only: never clobbers ANY existing plugin file
    actions = runtime.wire_opencode(project=None, root=ROOT)
    assert all(not a.startswith("+") for a in actions)
    plugin.write_text("// my own plugin\n")
    actions2 = runtime.wire_opencode(project=None, root=ROOT)
    assert plugin.read_text() == "// my own plugin\n"
    assert any(a.startswith("~ kept existing") and "pipa-session-bus" in a
               for a in actions2)


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


# ── model composer (dynamic discovery) ──────────────────────────────────────

def _seed_cache(state: Path, providers: dict) -> None:
    import json

    state.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "fetched_at": "2026-08-23T00:00:00Z",
        "providers": {
            slug: {"ok": True, "error": None, "models": models}
            for slug, models in providers.items()
        },
    }
    (state / "model_catalog.json").write_text(json.dumps(payload))


def test_composer_routes_discovered_models_per_key(monkeypatch, tmp_path):
    import yaml

    mdir = tmp_path / "models"
    mdir.mkdir()
    (mdir / "settings.yaml").write_text("litellm_settings:\n  callbacks: []\n")
    monkeypatch.setattr(config, "models_dir", lambda: mdir)
    monkeypatch.setattr(config, "state_dir", lambda: tmp_path / "state")
    monkeypatch.setattr(config, "load_dotenv", lambda: None)  # isolate real .env
    # earlier tests may have pulled real keys into os.environ via
    # model_registry's own load_dotenv — scrub so key-gating is hermetic
    from pipa.providers import PROVIDERS

    for p in PROVIDERS.values():
        for k in p.requires:
            monkeypatch.delenv(k, raising=False)
    _seed_cache(tmp_path / "state", {
        "ollama": [{"id": "qwen2.5-coder:14b", "name": ""}],
        "opencode-zen": [
            {"id": "mimo-v2.5-free", "name": ""},
            {"id": "deepseek-v4-flash-free", "name": ""},
        ],
        "kilo": [{"id": "stepfun/step-3.7-flash:free", "name": ""}],
    })

    path, warning = config.compose_litellm_config(root=tmp_path)
    data = yaml.safe_load(path.read_text())
    by_name = {m["model_name"]: m for m in data["model_list"]}
    # local discovered models stay always-on...
    assert by_name["qwen2.5-coder:14b"]["litellm_params"]["api_base"].startswith(
        "http://localhost:11434"
    )
    # ...cloud free models are skipped while their key is missing...
    assert warning and "(needs KILO_API_KEY)" in warning
    assert "(needs OPENCODE_ZEN_API_KEY)" in warning
    assert "stepfun/step-3.7-flash:free" not in by_name
    assert "mimo-v2.5-free" not in by_name

    # ...and route as soon as their keys are present.
    monkeypatch.setenv("KILO_API_KEY", "x")
    monkeypatch.setenv("OPENCODE_ZEN_API_KEY", "x")
    path2, _ = config.compose_litellm_config(root=tmp_path)
    data2 = yaml.safe_load(path2.read_text())
    by_name2 = {m["model_name"]: m for m in data2["model_list"]}
    assert by_name2["mimo-v2.5-free"]["litellm_params"]["api_base"] == "https://opencode.ai/zen/v1"
    assert "deepseek-v4-flash-free" in by_name2
    assert "stepfun/step-3.7-flash:free" in by_name2
    assert ".effective.yaml" in path.name


def test_thin_init_exposes_project_agents_to_opencode(tmp_path, monkeypatch):
    """pipa init links .pipa/agents-local into opencode's discovery path."""
    from pipa import config

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    # isolate the global project registry — init must not touch the real one
    monkeypatch.setattr(config, "state_dir", lambda: tmp_path / "state")

    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    (proj / ".pipa" / "agents-local").mkdir(parents=True)
    (proj / ".pipa" / "agents-local" / "jam-explorer.md").write_text("---\nname: jam-explorer\n---\n")

    actions = scaffold.init_project(proj, runtime_name="deepseek-harness", root=ROOT)

    link = proj / ".opencode" / "agent"
    assert link.is_symlink() and link.resolve() == (proj / ".pipa" / "agents-local").resolve()
    assert any("agents-local" in a for a in actions)
    # idempotent: second run keeps it
    scaffold.init_project(proj, runtime_name="deepseek-harness", root=ROOT)
    assert link.is_symlink()


def test_wire_dsh_enforces_owner_only_credentials(home, project):
    """dsh's credentials-local plugin rejects group/world-readable files."""
    runtime.wire_deepseek_harness(project=project, root=ROOT)
    creds = home / ".dsh" / ".credentials.yaml"
    assert (creds.stat().st_mode & 0o777) == 0o600

    # pre-existing too-permissive file gets tightened on the next wire
    runtime.wire_deepseek_harness(project=project, root=ROOT)
    creds.chmod(0o644)
    actions = runtime.wire_deepseek_harness(project=project, root=ROOT)
    assert (creds.stat().st_mode & 0o777) == 0o600
    assert any("600" in a for a in actions)
