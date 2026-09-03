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
# URL/key settings resolve lazily from os.environ (see __getattr__ below) so
# that $PIPA_ROOT/.env — loaded at import time — is honored.
_LAZY_ENV_DEFAULTS = {
    "LITELLM_URL": f"http://localhost:{LITELLM_PORT}",
    "LITELLM_KEY": "sk-pipa-local",
    "OLLAMA_URL": f"http://localhost:{OLLAMA_PORT}",
}

SESSION_LOG = "session.log.ndjson"       # inside <project>/.pipa/state/


def __getattr__(name: str):
    """PEP 562: resolve LITELLM_URL / LITELLM_KEY / OLLAMA_URL at access time."""
    default = _LAZY_ENV_DEFAULTS.get(name)
    if default is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return os.environ.get(name, default)


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
# Model lists are DISCOVERED from providers (pipa.providers) and cached in
# state/model_catalog.json; this composer projects that cache + user tier
# assignments into .effective.yaml.
# models/settings.yaml  — litellm_settings/router_settings/general_settings
# Composed result → models/.effective.yaml (gitignored), consumed by proxy.


def compose_litellm_config(
    root: Path | None = None, force_all: bool = False
) -> tuple[Path, str | None]:
    """Assemble DISCOVERED provider models into the effective gateway config.

    Reads the discovery cache (state/model_catalog.json, refreshed by
    pipa.providers / the dashboard / `pipa up`). No static model fragments
    exist; only models reported by providers get routed. Returns
    (effective_config_path, warning_or_None).
    """
    try:
        import yaml
    except ImportError:
        raise RuntimeError(
            "PyYAML required to compose the gateway config — run: pip3 install pyyaml"
        )

    root = root or harness_root()
    mdir = models_dir()
    load_dotenv()

    merged: dict[str, dict] = {}
    excluded: list[str] = []
    from pipa.providers import PROVIDERS, cached_catalog

    catalog = cached_catalog()
    for slug, p in PROVIDERS.items():
        entry = catalog.get(slug) or {}
        if not entry.get("ok"):
            excluded.append(f"{p.label}: not discovered yet")
            continue
        missing = [k for k in p.requires if not os.environ.get(k)]
        if missing and not force_all:
            excluded.append(f"{p.label} (needs {', '.join(missing)})")
            continue
        for m in entry.get("models") or []:
            merged[m["id"]] = {
                "model_name": m["id"],
                "litellm_params": p.litellm_params(m["id"]),
            }

    # Tier aliases: user-assigned via the dashboard, projected onto whatever
    # discovered model each tier points at.
    import copy

    from pipa.model_registry import make_entry, tier_assignments

    for tier, target in tier_assignments().items():
        base = merged.get(target)
        if base is not None and tier not in merged:
            merged[tier] = {
                **base,
                "model_name": tier,
                "litellm_params": copy.deepcopy(base["litellm_params"]),
            }

    # Descriptive aliases: every model also reachable as "provider/model" so
    # users can pick "moonshot/kimi-k2.7-code" instead of opaque ids.
    existing_names = set(merged)
    for m in list(merged.values()):
        e = make_entry(str(m["model_name"]), m.get("litellm_params") or {}, "", "local", True)
        if e.slug and e.slug != str(m["model_name"]) and e.slug not in existing_names:
            merged[e.slug] = {**m, "model_name": e.slug}
            existing_names.add(e.slug)

    settings_path = mdir / "settings.yaml"
    settings = yaml.safe_load(settings_path.read_text()) or {}

    header = (
        "# .effective.yaml — GENERATED by pipa from live provider discovery\n"
        "# (state/model_catalog.json) + settings.yaml. Model lists come from\n"
        "# the wire, never from static files.\n"
    )
    config_out = {
        "model_list": list(merged.values()),
        **settings,
    }
    effective = mdir / ".effective.yaml"
    text = header + yaml.safe_dump(config_out, sort_keys=False, default_flow_style=False)
    if not effective.exists() or effective.read_text() != text:
        effective.write_text(text)

    warning = None
    if excluded:
        warning = "gateway: providers skipped — " + "; ".join(excluded)
    return effective, warning


def pick_litellm_config(root: Path | None = None) -> tuple[Path, str | None]:
    """Back-compat wrapper over compose_litellm_config."""
    return compose_litellm_config(root)


# Load $PIPA_ROOT/.env at import so every consumer of the lazy URL/key
# settings above (CLI, dashboard, services) sees user overrides.
load_dotenv()
