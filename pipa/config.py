"""Shared path and config resolution for the pipa harness.

Resolution order for the install root:
  1. $PIPA_ROOT (explicit override)
  2. the directory containing this package (running from a checkout)
  3. ~/.pipa-harness (standard global install location)

Install layout: clis/ models/ mcp/ tools/ dashboard/ pipa/ plus the
contract markdown at the root (AGENTS.md, rules/, skills/, agents/).
Projects carry only thin overlays under <project>/.pipa/.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

PIPA_DIR = ".pipa"                       # per-project harness directory
LEGACY_EXTENSION_DIR = ".harness_extension"  # pre-refactor project layout
RUNTIME_MARKER = "runtime"               # inside .pipa/: selected runtime name

LITELLM_PORT = 4000
OLLAMA_PORT = 11434
DASHBOARD_PORT = 8080
LITELLM_URL = os.environ.get("LITELLM_URL", f"http://localhost:{LITELLM_PORT}")
LITELLM_KEY = os.environ.get("LITELLM_KEY", "sk-pipa-local")
OLLAMA_URL = os.environ.get("OLLAMA_URL", f"http://localhost:{OLLAMA_PORT}")

SESSION_LOG = "session.log.ndjson"       # inside <project>/.pipa/state/


def load_dotenv() -> None:
    """Load $PIPA_ROOT/.env into os.environ without overriding existing vars.

    Lets users keep provider keys (KILO_API_KEY, ...) out of shell rc files.
    Values are never printed or logged.
    """
    env_file = harness_root() / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


# ── install-root layout ─────────────────────────────────────────────────────

def harness_root() -> Path:
    """The shared harness installation (AGENTS.md, rules/, skills/, ...)."""
    env = os.environ.get("PIPA_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    pkg_root = Path(__file__).resolve().parent.parent
    if (pkg_root / "AGENTS.md").exists():
        return pkg_root
    return Path.home() / ".pipa-harness"


def state_dir() -> Path:
    """Harness-global runtime state (service pids/logs, ledger, registry)."""
    return harness_root() / "state"


def clis_dir() -> Path:
    return harness_root() / "clis"


def models_dir() -> Path:
    return harness_root() / "models"


def mcp_dir() -> Path:
    return harness_root() / "mcp"


# ── project resolution ──────────────────────────────────────────────────────

def git_root(start: Path | None = None) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(start or Path.cwd()),
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0:
            return Path(out.stdout.strip())
    except Exception:
        pass
    return None


def _is_pipa_project(pipa: Path) -> bool:
    """Thin layout (.pipa/rules|memory|skills) or legacy (.pipa/extension)."""
    if (pipa / RUNTIME_MARKER).is_file():
        return True
    if (pipa / "extension").is_dir():
        return True
    return any(
        (pipa / d).is_dir() for d in ("rules", "memory", "skills")
    )


def find_project(start: Path | None = None) -> Path | None:
    """Nearest directory with a .pipa/ project marker, walking up; else git root.

    A bare .pipa/ alone is not enough — tool caches must not hijack
    project detection.
    """
    cur = (start or Path.cwd()).resolve()
    for d in (cur, *cur.parents):
        pipa = d / PIPA_DIR
        if pipa.is_dir() and _is_pipa_project(pipa):
            return d
    return git_root(cur)


def pipa_dir(project: Path) -> Path:
    return project / PIPA_DIR


def project_state_dir(project: Path) -> Path:
    return pipa_dir(project) / "state"


def session_log_path(project: Path) -> Path:
    return project_state_dir(project) / SESSION_LOG


def projects_registry_path() -> Path:
    return state_dir() / "projects.json"


def register_project(project: Path, runtime: str) -> None:
    """Record a project in the global registry (dashboard/extensions view)."""
    path = projects_registry_path()
    try:
        entries = json.loads(path.read_text()) if path.exists() else []
    except Exception:
        entries = []
    entry = {"path": str(project), "runtime": runtime}
    entries = [e for e in entries if e.get("path") != entry["path"]]
    entries.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2) + "\n")


# ── LiteLLM model composer ──────────────────────────────────────────────────
#
# models/local/*.yaml   — always-on fragments (local ollama tier)
# models/cloud/*.yaml   — included only when their `requires:` env var is set;
#                         later fragments override earlier ones per alias, so
#                         cloud tiers upgrade local roles transparently.
# models/settings.yaml  — litellm_settings/router_settings/general_settings
# Composed result → models/.effective.yaml (gitignored), consumed by proxy.


def _fragment_models(path: Path) -> tuple[list[dict], str | None]:
    import yaml
    data = yaml.safe_load(path.read_text()) or {}
    requires = data.get("requires")
    if isinstance(requires, str):
        requires = [requires]
    missing = [k for k in (requires or []) if not os.environ.get(k)]
    return data.get("models") or [], (missing or None)


def compose_litellm_config(
    root: Path | None = None, force_all: bool = False
) -> tuple[Path, str | None]:
    """Assemble enabled model fragments into the effective gateway config.

    Returns (effective_config_path, warning_or_None).
    """
    root = root or harness_root()
    mdir = models_dir()
    try:
        import yaml  # noqa: F401
    except ImportError:
        raise RuntimeError(
            "PyYAML required to compose the gateway config — run: pip3 install pyyaml"
        )

    merged: dict[str, dict] = {}
    excluded: list[str] = []
    for sub in ("local", "cloud"):
        for frag in sorted((mdir / sub).glob("*.yaml")):
            models, missing = _fragment_models(frag)
            if missing and not force_all:
                excluded.append(f"{frag.name} (needs {', '.join(missing)})")
                continue
            for m in models:
                merged[m["model_name"]] = m

    settings_path = mdir / "settings.yaml"
    settings = yaml.safe_load(settings_path.read_text()) or {}

    header = (
        "# .effective.yaml — GENERATED by pipa from models/{local,cloud}/\n"
        "# fragments + settings.yaml. Edit the fragments, not this file.\n"
    )
    config = {
        "model_list": list(merged.values()),
        **settings,
    }
    effective = mdir / ".effective.yaml"
    text = header + yaml.safe_dump(config, sort_keys=False, default_flow_style=False)
    if not effective.exists() or effective.read_text() != text:
        effective.write_text(text)

    warning = None
    if excluded:
        warning = "gateway: cloud fragments skipped — " + "; ".join(excluded)
    return effective, warning


def pick_litellm_config(root: Path | None = None) -> tuple[Path, str | None]:
    """Back-compat wrapper over compose_litellm_config."""
    return compose_litellm_config(root)
