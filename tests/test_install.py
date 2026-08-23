"""Contract tests for the install layer.

Covers only static guarantees (files exist, are executable, mention the right
entrypoints) — no network, no real installs. Repo root is derived from
__file__ so tests pass regardless of cwd.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install"
STEPS = INSTALL / "steps"

STEP_SCRIPTS = [
    "00-deps.sh",
    "10-core.sh",
    "20-runtimes.sh",
    "30-apps.sh",
    "40-wire.sh",
]

REQUIRED_MAKE_TARGETS = ["install", "update", "uninstall"]


def test_makefile_exists_with_required_targets():
    mk = INSTALL / "Makefile"
    assert mk.is_file(), f"missing {mk}"
    text = mk.read_text()
    for target in REQUIRED_MAKE_TARGETS:
        assert f"{target}:" in text, f"Makefile lacks target '{target}'"


def test_step_scripts_exist_and_are_executable():
    assert STEPS.is_dir(), f"missing {STEPS}"
    for name in STEP_SCRIPTS:
        p = STEPS / name
        assert p.is_file(), f"missing step script: {name}"
        assert os.access(p, os.X_OK), f"not executable (chmod +x): {name}"


def test_bootstrap_mentions_repo_url_and_dest():
    text = (ROOT / "bootstrap.sh").read_text()
    assert "REPO_URL" in text, "bootstrap.sh must honor REPO_URL override"
    assert ".pipa-harness" in text, "bootstrap.sh must target ~/.pipa-harness"


def test_install_sh_shims_to_installed_pipa():
    text = (ROOT / "install.sh").read_text()
    assert ".pipa-harness/bin/pipa" in text, (
        "install.sh must exec ~/.pipa-harness/bin/pipa"
    )
