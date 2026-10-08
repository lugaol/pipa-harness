"""pipa doctor — tier-system + gateway health diagnostics.

Fails (exit 1) on hard config errors; warnings never fail. Ported from
ia_harness tools/doctor.py, generalized: no hardcoded providers.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

from pipa import config
from pipa.model_registry import (
    TIER_ALIASES,
    agent_tier_defaults,
    normalize_tier,
    tier_assignments,
    tier_policy,
    undeclared_agent_tiers,
)


def _instruction_globs(text: str) -> list[str]:
    """Instruction globs from a rendered runtime config, JSONC-tolerant."""
    try:
        from pipa.runtime import _strip_jsonc

        import json

        cfg = json.loads(_strip_jsonc(text))
    except Exception:
        return []
    value = cfg.get("instructions")
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value] if isinstance(value, list) else []


def collect_checks() -> list[dict]:
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

    # ── 2. agent tier defaults (single owner: models/tiers.yaml) ─────
    defaults = agent_tier_defaults()
    undeclared = undeclared_agent_tiers()
    if undeclared:
        check("fail", "agent_tiers",
              "tiers naming an unroutable tier: "
              + ", ".join(f"{a}={t}" for a, t in sorted(undeclared.items())))
    if not defaults:
        check("warn", "agent_tiers", "no agent_tiers declared — using the built-in fallback")
    else:
        check("pass", "agent_tiers",
              f"{len(defaults)} agents defaulted from tiers.yaml")

    # ── 3. providers registry ────────────────────────────────────────
    try:
        from pipa.providers import PROVIDERS, PROVIDER_WARNINGS

        if PROVIDERS:
            detail = f"{len(PROVIDERS)} providers wired"
            check("warn" if PROVIDER_WARNINGS else "pass", "providers",
                  f"{detail} — {'; '.join(PROVIDER_WARNINGS)}"
                  if PROVIDER_WARNINGS else detail)
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
    # A missing env key is only a problem if it actually blocks the model.
    # A model can be served by more than one provider, and the credential check
    # walks the catalog in dict order — so an unset key for a provider that
    # merely *also* lists the alias used to fail tiers that call fine. Trust a
    # recorded live probe over inferred wiring whenever one exists.
    try:
        from pipa.providers import missing_keys
    except ImportError:
        missing_keys = lambda _a: []  # noqa: E731
    try:
        verif_path = config.state_dir() / "model_verification.json"
        probed: dict[str, bool] = {}
        if verif_path.is_file():
            raw = json.loads(verif_path.read_text())
            probed = {
                k: bool(v.get("ok"))
                for k, v in raw.items()
                if k != "_checked_at" and isinstance(v, dict)
            }
    except (OSError, ValueError):
        probed = {}
    cred_missing, cred_ok = [], 0
    for tier, alias in assigned.items():
        if probed.get(alias) is True:
            cred_ok += 1          # proven callable — keys are demonstrably fine
            continue
        miss = missing_keys(alias)
        if miss and probed.get(alias) is not True:
            cred_missing.append(f"{tier} needs {', '.join(miss)}")
    if cred_missing:
        check("fail", "tier-credentials", "; ".join(cred_missing))
    elif assigned:
        suffix = f" ({cred_ok} confirmed by live probe)" if cred_ok else ""
        check("pass", "tier-credentials", f"keys present for assigned tiers{suffix}")

    # ── 7. split-brain: is the CLI on PATH the same code the agent reads? ──
    #
    # This is the failure that costs a newcomer the most time. `bootstrap.sh`
    # clones into ~/.pipa-harness and puts it on PATH, but a user working in a
    # git checkout points opencode at THAT checkout. Two copies, no warning:
    # `pipa <cmd>` runs one version while the agent reads another, so a fix
    # appears to do nothing.
    try:
        import shutil
        import subprocess as _sp

        on_path = shutil.which("pipa")
        here = Path(__file__).resolve().parent.parent.parent
        if not on_path:
            check("warn", "cli-on-path",
                  "pipa not on PATH — add ~/.pipa-harness/bin to your shell PATH")
        else:
            cli_root = Path(on_path).resolve().parent.parent
            if cli_root == here:
                check("pass", "cli-on-path", f"pipa runs this checkout ({here})")
            else:
                check("fail", "cli-on-path",
                      f"SPLIT-BRAIN: `pipa` on PATH is {cli_root}, "
                      f"but the agent config points at {here}. Fix with: "
                      f"make -C {here}/install path (or put {here}/bin on PATH "
                      f"ahead of {cli_root / 'bin'})")
    except Exception as exc:  # noqa: BLE001
        check("warn", "cli-on-path", f"could not determine: {exc}")

    # ── 8. is the project's AGENTS.md actually loaded by the agent? ──
    try:
        cfg_path = Path.home() / ".config/opencode/opencode.jsonc"
        if cfg_path.is_file():
            text = cfg_path.read_text(encoding="utf-8", errors="ignore")
            instructions = _instruction_globs(text)
            # Semantic, not a literal-substring test. It used to require the
            # exact token `"AGENTS.md"` in quotes, which a rendered config can
            # never satisfy: pipa substitutes @PIPA_ROOT@, so the entry reads
            # "/Users/.../AGENTS.md". The check therefore failed on every
            # correctly-rendered config.
            has_project = any(
                g.endswith("AGENTS.md") or g == "AGENTS.md" for g in instructions
            )
            has_overlay = any(".pipa/" in g for g in instructions)
            if has_project and has_overlay:
                check("pass", "agent-instructions",
                      "project AGENTS.md and .pipa/ overlay are both loaded")
            elif not has_project:
                check("fail", "agent-instructions",
                      "opencode.jsonc does not load project AGENTS.md — "
                      "add \"AGENTS.md\" or \".pipa/AGENTS.md\" to "
                      "instructions, or `pipa init` output is invisible "
                      "to the agent")
            else:
                check("warn", "agent-instructions",
                      "opencode.jsonc does not load the .pipa/ overlay "
                      "(.pipa/AGENTS.md, .pipa/rules/*.md)")
        else:
            check("warn", "agent-instructions",
                  f"no {cfg_path} — cannot verify what the agent loads")
    except Exception as exc:  # noqa: BLE001
        check("warn", "agent-instructions", f"could not read config: {exc}")

    # ── 9. services (warnings only — `pipa up` starts them) ──────────
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
    checks = collect_checks()
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
