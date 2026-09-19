"""pipa doctor — tier-system + gateway health diagnostics.

Fails (exit 1) on hard config errors; warnings never fail. Ported from
ia_harness tools/doctor.py, generalized: no hardcoded providers.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

from pipa import config
from pipa.model_registry import (
    TIER_ALIASES,
    agent_tier_defaults,
    normalize_tier,
    tier_assignments,
    tier_policy,
)


def _collect() -> list[dict]:
    """[(status, name, detail)] with status in pass|warn|fail."""
    checks: list[dict] = []

    def check(status: str, name: str, detail: str = "") -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    # ── 1. tier policy file ──────────────────────────────────────────
    policy = tier_policy()
    missing = [t for t in TIER_ALIASES if t not in policy]
    if missing:
        check("fail", "tiers.yaml", f"tiers missing: {', '.join(missing)}")
    else:
        thin = [t for t, p in policy.items()
                if not p.get("label") or not p.get("description")]
        if thin:
            check("fail", "tiers.yaml",
                  f"tiers without label/description: {', '.join(thin)}")
        else:
            check("pass", "tiers.yaml", f"{len(policy)} tiers documented")

    # ── 2. agent defaults vs code map ────────────────────────────────
    try:
        from pipa.runtime import AGENT_MODEL_MAP
    except ImportError:
        AGENT_MODEL_MAP = {}
    defaults = agent_tier_defaults()
    bad = {a: t for a, t in defaults.items() if not normalize_tier(t)}
    if bad:
        check("fail", "agent_tiers",
              f"unknown tiers: {', '.join(f'{a}={t}' for a, t in bad.items())}")
    else:
        drift = {a for a, t in AGENT_MODEL_MAP.items()
                 if a in defaults and normalize_tier(t) != defaults[a]}
        extra = {a for a in AGENT_MODEL_MAP if a not in defaults}
        if drift or extra:
            parts = []
            if drift:
                parts.append("drift: " + ", ".join(sorted(drift)))
            if extra:
                parts.append("unlisted in tiers.yaml: " + ", ".join(sorted(extra)))
            check("warn", "agent_tiers", "; ".join(parts))
        else:
            check("pass", "agent_tiers",
                  f"{len(defaults)} agents defaulted, in sync with runtime.py")

    # ── 3. providers registry ────────────────────────────────────────
    try:
        from pipa.providers import PROVIDERS

        if PROVIDERS:
            check("pass", "providers", f"{len(PROVIDERS)} providers wired")
        else:
            check("fail", "providers", "no providers in models/providers.yaml")
    except Exception as exc:
        check("fail", "providers", f"registry unreadable: {exc}")
        PROVIDERS = {}

    # ── 4. tier assignments resolve to discovered models ─────────────
    try:
        from pipa.model_registry import by_alias

        known = set(by_alias())
    except Exception:
        known = set()
    assigned = tier_assignments()
    if not assigned:
        check("warn", "tier-assignments", "no tiers assigned yet (Models page)")
    elif known:
        unknown = [f"{t}={a}" for t, a in assigned.items() if a not in known]
        if unknown:
            check("warn", "tier-assignments",
                  f"assigned to undiscovered models: {', '.join(unknown)}")
        else:
            check("pass", "tier-assignments",
                  f"{len(assigned)} tiers resolve to discovered models")
    else:
        check("warn", "tier-assignments",
              "discovery cache empty — run `pipa up` or Models → Refresh")

    # ── 5. generated gateway config in sync ──────────────────────────
    try:
        effective = config.models_dir() / ".effective.yaml"
        before = effective.read_text() if effective.exists() else None
        config.compose_litellm_config()
        after = effective.read_text() if effective.exists() else None
        if before is None:
            check("warn", "gateway-config", "generated .effective.yaml (was missing)")
        elif before != after:
            check("fail", "gateway-config",
                  ".effective.yaml was stale — regenerated, re-run consumers")
        else:
            check("pass", "gateway-config", "in sync with discovery + tiers")
    except Exception as exc:
        check("fail", "gateway-config", f"compose failed: {exc}")

    # ── 6. credentials for assigned tiers ────────────────────────────
    try:
        from pipa.providers import missing_keys
    except ImportError:
        missing_keys = lambda _a: []  # noqa: E731
    cred_missing = []
    for tier, alias in assigned.items():
        miss = missing_keys(alias)
        if miss:
            cred_missing.append(f"{tier} needs {', '.join(miss)}")
    if cred_missing:
        check("fail", "tier-credentials", "; ".join(cred_missing))
    elif assigned:
        check("pass", "tier-credentials", "keys present for assigned tiers")

    # ── 7. services (warnings only — `pipa up` starts them) ──────────
    try:
        req = urllib.request.Request(
            f"{config.LITELLM_URL}/v1/models",
            headers={"Authorization": f"Bearer {config.LITELLM_KEY}"},
        )
        with urllib.request.urlopen(req, timeout=5):
            check("pass", "gateway", "reachable")
    except Exception:
        check("warn", "gateway", "not reachable — run `pipa up`")
    try:
        with urllib.request.urlopen(config.OLLAMA_URL, timeout=2):
            check("pass", "ollama", "running")
    except Exception:
        check("warn", "ollama", "not running (local models unavailable)")

    return checks


def cmd_doctor(args) -> int:
    config.load_dotenv()
    checks = _collect()
    summary = {
        "pass": sum(1 for c in checks if c["status"] == "pass"),
        "warn": sum(1 for c in checks if c["status"] == "warn"),
        "fail": sum(1 for c in checks if c["status"] == "fail"),
    }
    if getattr(args, "json", False):
        print(json.dumps(
            {"checks": checks, "summary": summary, "timestamp": time.time()}))
    else:
        for c in checks:
            mark = {"pass": "OK", "warn": "WARN", "fail": "FAIL"}[c["status"]]
            print(f"  [{mark}] {c['name']}"
                  + (f": {c['detail']}" if c["detail"] else ""))
        print(f"\n  {summary['pass']} pass, {summary['warn']} warn, "
              f"{summary['fail']} fail")
    return 0 if summary["fail"] == 0 else 1
