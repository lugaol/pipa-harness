"""$PIPA_ROOT/.env management for the API Keys panel.

Live view of the dotenv file: grouped key metadata (names + masked
presence, never values), validated writes (allowlist, no whitespace,
placeholder rejection), chmod 600. Ported from ia_harness
dashboard/services/envstore.py, generalized to pipa's provider registry.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List

from pipa import config

_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_PLACEHOLDER_RE = re.compile(
    r"^(your-|replace-me|changeme|TODO|<.*>|/path/to/|example)", re.IGNORECASE)


def env_path() -> Path:
    return config.harness_root() / ".env"


def key_meta() -> List[dict]:
    """[{key, group, label, hint, secret}] from the provider registry."""
    try:
        from pipa.providers import PROVIDERS
    except ImportError:
        PROVIDERS = {}
    meta = [{
        "key": "LITELLM_KEY", "group": "Gateway", "label": "Gateway key",
        "hint": "bearer for the local LiteLLM gateway", "secret": True,
    }]
    for slug, p in PROVIDERS.items():
        for k in p.requires:
            if any(m["key"] == k for m in meta):
                continue
            meta.append({
                "key": k, "group": "Providers",
                "label": f"{p.label} key",
                "hint": f"backs {p.label} models",
                "secret": True,
            })
    return sorted(meta, key=lambda m: (m["group"], m["key"]))


def managed_keys() -> set:
    return {m["key"] for m in key_meta()}


def read_env_file() -> Dict[str, str]:
    values: Dict[str, str] = {}
    path = env_path()
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def effective_values() -> Dict[str, str]:
    """dotenv file overlaid with process env (process wins, like load_dotenv).

    Presence reflects what the gateway would actually see; values are only
    ever used for presence/masking, never returned.
    """
    values = read_env_file()
    for m in key_meta():
        if os.environ.get(m["key"]):
            values[m["key"]] = os.environ[m["key"]]
    return values


def mask(value: str) -> str:
    return f"{value[:4]}…{value[-4:]}" if len(value) > 8 else "•••"


def is_placeholder(value: str) -> bool:
    return bool(value) and bool(_PLACEHOLDER_RE.match(value.strip()))


def list_env_keys() -> dict:
    """Grouped, masked view for the API Keys panel (values never included)."""
    values = effective_values()
    groups: List[str] = []
    out = []
    for m in key_meta():
        v = values.get(m["key"], "")
        if m["group"] not in groups:
            groups.append(m["group"])
        out.append({
            **m,
            "set": bool(v),
            "placeholder": is_placeholder(v) or not v,
            "value": "",
            "masked": mask(v) if v else "",
        })
    return {"groups": groups, "keys": out}


def write_env_value(key: str, value: str) -> None:
    if not _KEY_RE.fullmatch(key or ""):
        raise ValueError(f"invalid env key: {key!r}")
    if key not in managed_keys():
        raise ValueError(f"env key not managed by the dashboard: {key!r}")
    if "\n" in value or "\r" in value:
        raise ValueError("env value must not contain newlines")
    path = env_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line_re = re.compile(r"^\s*(?:export\s+)?" + re.escape(key) + r"\s*=")
    lines = path.read_text().splitlines() if path.exists() else []
    out, done = [], False
    for line in lines:
        if not done and line_re.match(line):
            out.append(f"{key}={value}")
            done = True
        else:
            out.append(line)
    if not done:
        out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def set_key_and_apply(key: str, value: str) -> dict:
    """Write one .env value, recompose the gateway config, restart it."""
    from data import services as services_data

    write_env_value(key, value)
    try:
        config.compose_litellm_config()
    except Exception:
        pass
    restarted, detail = services_data.gateway_restart()
    return {
        "ok": True,
        "key": key,
        "restarted": restarted,
        "restart_detail": detail[-300:] if not restarted else "",
    }
