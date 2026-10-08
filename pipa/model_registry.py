"""Model registry — single source of truth for human-readable model naming.

Derives {alias -> ModelEntry} from the provider discovery cache
(state/model_catalog.json) — the same source pipa.config's composer
consumes. There is no static model list: models are whatever providers
report. Which model backs each tier (lowest..xhigh) is ALWAYS a user
decision made in the dashboard and stored in state/tier_assignments.json —
nothing is auto-classified. Every user-facing surface (dashboard,
opencode config, docs) renders names through this module so a model
always reads like "Moonshot - Kimi K2.7 Code", never "kimi-code".
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlparse

from pipa import config

TIER_ALIASES = ("lowest", "low", "mid", "high", "xhigh")
TIER_ASSIGNMENTS_FILE = "tier_assignments.json"

# Pre-2026-08 tier names found in old frontmatter/override stores.
LEGACY_TIER_MAP = {
    "primary": "mid",
    "fast": "low",
    "deep": "high",
    "explore": "lowest",
}


def normalize_tier(name: str) -> str:
    """Map legacy tier aliases onto the current five; '' when unknown."""
    t = (name or "").strip().lower()
    if t in TIER_ALIASES:
        return t
    return LEGACY_TIER_MAP.get(t, "")

PROVIDER_LABELS = {
    "moonshot": "Moonshot",
    "moonshotai": "Moonshot",
    "kimi": "Kimi",
    "kilo": "Kilo",
    "kilo-auto": "Kilo",
    "openrouter": "OpenRouter",
    "opencode": "OpenCode",
    "opencode-zen": "OpenCode Zen",
    "typesafe-jev": "Jev",
    "stepfun": "StepFun",
    "nvidia": "NVIDIA",
    "google": "Google",
    "cohere": "Cohere",
    "qwen": "Qwen",
    "deepseek": "DeepSeek",
    "z-ai": "Z.AI",
    "ollama": "Ollama",
}

# Raw model ids whose generic pretty-form reads badly.
PRETTY_OVERRIDES = {
    "x-preview-f-free": "Ox Alpha Free",  # OpenCode Zen stealth id
}

_DROP_TOKENS = {"it", "free", "preview"}
_UPPER_TOKENS = {"ai": "AI", "llm": "LLM", "api": "API", "vl": "VL", "ocr": "OCR", "mimo": "MiMo"}
_SIZE_RE = re.compile(r"^a?\d+(\.\d+)?[bkm]$")


@dataclass(frozen=True)
class ModelEntry:
    alias: str
    backend: str
    provider_slug: str
    provider_label: str
    model_label: str
    kind: str
    fragment: str
    active: bool

    @property
    def display(self) -> str:
        return f"{self.provider_label} - {self.model_label}"

    @property
    def slug(self) -> str:
        return f"{self.provider_slug}/{_slugify(self.model_label)}"


def pretty_model_name(raw: str) -> str:
    """'kimi-k2.7-code' -> 'Kimi K2.7 Code'; 'qwen2.5-coder:14b' -> 'Qwen2.5 Coder 14B'."""
    text = raw.strip().lower()
    if text in PRETTY_OVERRIDES:
        return PRETTY_OVERRIDES[text]
    flags: List[str] = []
    if ":" in text:
        base, _, suffix = text.partition(":")
        if suffix == "free":
            flags.append("Free")
        elif suffix:
            base = f"{base} {suffix}"
        text = base
    elif text.endswith("-free"):
        flags.append("Free")
        text = text[: -len("-free")]
    out: List[str] = []
    for tok in re.split(r"[-_/\s]+", text):
        if not tok:
            continue
        if tok in _DROP_TOKENS:
            continue
        if tok in _UPPER_TOKENS:
            out.append(_UPPER_TOKENS[tok])
        elif _SIZE_RE.match(tok):
            out.append(tok.upper())
        else:
            out.append(tok[:1].upper() + tok[1:])
    label = " ".join(out)
    for flag in reversed(flags):
        label = f"{label} {flag}" if label else flag
    return label


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9._/-]+", "-", text.lower()).strip("-.")
    return re.sub(r"-{2,}", "-", s)


def classify(backend: str, api_base: str = "", cloud: bool = False) -> tuple[str, str]:
    """-> (provider_slug, model_part) from a litellm backend string."""
    host = urlparse(api_base).hostname or ""
    if "moonshot" in host:
        return "moonshot", backend.split("/", 1)[-1]
    if backend.startswith("kilo-auto/"):
        return "kilo-auto", backend.split("/", 1)[1]
    if backend.startswith("openrouter/"):
        parts = backend.split("/")
        org = parts[1] if len(parts) > 2 else "openrouter"
        model = "/".join(parts[2:]) if len(parts) > 2 else backend.split("/", 1)[1]
        return org, model
    if backend.startswith("stepfun/"):
        return "stepfun", backend.split("/", 1)[1]
    if backend.startswith("ollama/") or backend.startswith("ollama_chat/"):
        return "ollama", backend.split("/", 1)[1]
    if backend.startswith("openai/"):
        model = backend.split("/", 1)[1]
        if host.startswith(("localhost", "127.", "0.0.0.0")):
            return "ollama", model
        if "opencode.ai" in host:
            return "opencode", model
        if api_base:
            return "openai-compatible", model
        return "ollama", model
    return "other", backend


def provider_label(slug: str) -> str:
    if slug in PROVIDER_LABELS:
        return PROVIDER_LABELS[slug]
    if slug == "openai-compatible":
        return "OpenAI-compatible"
    return slug.replace("-", " ").title()


def make_entry(alias: str, params: dict, fragment: str, kind: str, active: bool,
               provider_slug: str = "") -> ModelEntry:
    """Build a ModelEntry.

    `provider_slug`, when given, is authoritative: it comes from
    pipa.providers.resolve_backing. `classify` then only has to work out the
    model part. Without it, a provider whose backend string is not
    self-describing (kimi uses a bare `{id}` plus an api_base) fell through to
    the "other" branch and rendered as "Other - K3 256K" in the picker and on
    every tier row.
    """
    backend = str((params or {}).get("model") or "")
    api_base = str((params or {}).get("api_base") or "")
    if provider_slug:
        slug = provider_slug
        model_part = _model_part(backend, api_base)
    else:
        slug, model_part = classify(backend, api_base, cloud=kind == "cloud")
    if slug == "kilo-auto":
        label = "Auto Free" if model_part == "free" else pretty_model_name(model_part)
    else:
        label = pretty_model_name(model_part)
    return ModelEntry(
        alias=alias,
        backend=backend,
        provider_slug=slug,
        provider_label=provider_label(slug),
        model_label=label or alias,
        kind=kind,
        fragment=fragment,
        active=active,
    )


def _model_part(backend: str, api_base: str = "") -> str:
    """The model half of a litellm backend string, when the provider is known.

    litellm accepts either `<provider>/<model>` or a bare `<model>` paired with
    an `api_base`. Both forms are in use here, so both are stripped.
    """
    for prefix in ("ollama_chat/", "openrouter/", "openai/"):
        if backend.startswith(prefix):
            return backend[len(prefix):]
    if "/" in backend and not backend.startswith("kilo-auto/"):
        head, _, rest = backend.partition("/")
        # openrouter-style ids carry an org: org/model[/variant]
        if head in ("openrouter", "kilo-auto", "stepfun", "ollama") and rest:
            return rest
        if "/" in rest:
            return rest
        return backend
    return backend


def _discovered_entries() -> List[ModelEntry]:
    """ModelEntry per discovered model, straight from the provider cache.

    Provider attribution comes from `pipa.providers.resolve_backing`, the same
    owner the gateway composer uses. This used to attribute a duplicated id to
    whichever provider came first while the composer let the last one win, so a
    model the gateway served happily through kilo was marked inactive here
    (openrouter's key is unset) and dropped from the model picker.
    """
    try:
        from pipa.providers import PROVIDERS, cached_catalog, resolve_backing
    except ImportError:
        return []
    config.load_dotenv()
    catalog = cached_catalog()
    backing = resolve_backing(catalog)
    out: List[ModelEntry] = []
    seen: set[str] = set()
    for slug, p in PROVIDERS.items():
        entry = catalog.get(slug) or {}
        active = all(bool(os.environ.get(k)) for k in p.requires)
        for m in entry.get("models") or []:
            mid = m["id"]
            if mid in seen or backing.get(mid) != slug:
                continue  # another provider backs this id
            seen.add(mid)
            out.append(make_entry(
                mid, p.litellm_params(mid),
                f"{slug} (discovered)", p.kind, active,
                provider_slug=slug,
            ))
    return out


def entries(active_only: bool = False) -> List[ModelEntry]:
    """All discovered models as entries; dedup by provider-reported id."""
    out = _discovered_entries()
    if active_only:
        out = [e for e in out if e.active]
    return out


def by_alias() -> Dict[str, ModelEntry]:
    return {e.alias: e for e in entries()}


# ── tier assignments (user-owned, set from the dashboard) ───────────────────

def tier_assignments_path() -> Path:
    return config.state_dir() / TIER_ASSIGNMENTS_FILE


def tier_assignments() -> Dict[str, str]:
    """{tier -> model alias} exactly as the user configured it; {} when unset."""
    try:
        data = json.loads(tier_assignments_path().read_text())
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    clean: Dict[str, str] = {}
    for key, value in data.items():
        t = normalize_tier(str(key))
        if t and isinstance(value, str) and value.strip():
            clean[t] = value.strip()
    return {t: clean[t] for t in TIER_ALIASES if t in clean}


def apply_tiers(assignments: dict) -> Tuple[bool, str, list]:
    """Validate + persist a {tier: alias} batch in one call.

    Single owner for batch tier writes — both dashboard batch endpoints
    (`PUT /api/tier-models`, `POST /api/tiers/batch`) call this instead of
    looping `set_tier_assignment` themselves. Returns (ok, msg, warnings);
    warnings name models whose API key is missing (saved anyway).
    """
    from pipa.providers import missing_keys

    if not isinstance(assignments, dict) or not assignments:
        return False, "tiers must be a non-empty mapping of tier -> model", []
    unknown = [t for t in assignments if normalize_tier(t) not in TIER_ALIASES]
    if unknown:
        return False, f"unknown tier: {', '.join(unknown)}", []
    known = set(by_alias())
    for tier, alias in assignments.items():
        model = (alias or "").strip()
        if not model:
            return False, f"tier {tier} needs a model", []
        if model not in known:
            return False, f"unknown model {model!r} - not in the model catalog", []
    warnings = []
    for tier, alias in assignments.items():
        model = alias.strip()
        ok, msg = set_tier_assignment(normalize_tier(tier), model)
        if not ok:
            return False, msg, []
        missing = missing_keys(model)
        if missing:
            warnings.append(f"{model} needs {', '.join(missing)}")
    return True, "saved", warnings


def set_tier_assignment(tier: str, alias: str) -> Tuple[bool, str]:
    """Assign one tier to a discovered model (alias) — or clear with ''.

    The user decides every mapping; nothing is inferred from providers.
    """
    t = normalize_tier(tier)
    if not t:
        return False, f"unknown tier '{tier}' (choose: {', '.join(TIER_ALIASES)})"
    alias = (alias or "").strip()
    data = tier_assignments()
    if alias:
        if alias not in by_alias():
            return False, f"unknown model '{alias}'"
        data[t] = alias
    else:
        data.pop(t, None)
    ordered = {k: data[k] for k in TIER_ALIASES if k in data}
    path = tier_assignments_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ordered, indent=2) + "\n")
    try:
        config.compose_litellm_config()
    except Exception:
        pass  # gateway recomposes on next `pipa up` anyway
    return True, f"{t} -> {alias or '(default)'}"


def tier_resolution() -> Dict[str, ModelEntry]:
    """Tier -> concrete model, strictly as assigned by the user.

    Unassigned tiers are absent; tiers whose model's API key is missing
    resolve but carry active=False so the UI can flag them.
    """
    by = by_alias()
    result: Dict[str, ModelEntry] = {}
    for tier, alias in tier_assignments().items():
        e = by.get(alias)
        if e is not None:
            result[tier] = e
    return result


def seed_default_tiers() -> Dict[str, str]:
    """First-run convenience: fill ALL five tiers from discovery when the
    user has assigned none.

    Heuristic (deterministic, no quality data): prefer local Ollama models
    for the cheapest tiers (always-on, $0), cloud/free-tier models for the
    stronger ones. The user owns these mappings and can change any of them
    on the dashboard Models page — this only fires when tier_assignments()
    is empty. Returns {tier: alias} written, or {} when skipped.
    """
    if tier_assignments():
        return {}
    es = [e for e in entries(active_only=True)]
    if not es:
        return {}
    local = sorted((e for e in es if e.provider_slug == "ollama"),
                   key=lambda e: e.alias)
    cloud = sorted((e for e in es if e.provider_slug != "ollama"),
                   key=lambda e: e.alias)
    if not local and not cloud:
        return {}

    def pick(seq, i, fallback_seq):
        if seq:
            return seq[i % len(seq)].alias
        if fallback_seq:
            return fallback_seq[i % len(fallback_seq)].alias
        return ""

    plan = {
        "lowest": pick(local, 0, cloud),
        "low": pick(local, min(1, max(len(local) - 1, 0)), cloud),
        "mid": pick(cloud, 0, local),
        "high": pick(cloud, min(1, max(len(cloud) - 1, 0)), local),
        "xhigh": pick(cloud, (len(cloud) - 1) if cloud else 0, local),
    }
    plan = {t: a for t, a in plan.items() if a}
    path = tier_assignments_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(
        {t: plan[t] for t in TIER_ALIASES if t in plan}, indent=2) + "\n")
    try:
        config.compose_litellm_config()
    except Exception:
        pass
    return plan


def display_alias(alias: str) -> str:
    """Pretty display for any gateway alias; passthrough for unknown ids."""
    e = by_alias().get(alias)
    return e.display if e else alias


def provider_groups(active_only: bool = False) -> List[dict]:
    """[{slug,label,entries}] sorted: cloud providers alphabetical, Ollama last."""
    groups: Dict[str, List[ModelEntry]] = {}
    for e in entries():
        if active_only and not e.active:
            continue
        groups.setdefault(e.provider_slug, []).append(e)
    out = [
        {"slug": slug, "label": provider_label(slug), "entries": items}
        for slug, items in groups.items()
    ]
    out.sort(key=lambda g: (g["slug"] == "ollama", g["label"].lower()))
    for g in out:
        g["entries"].sort(key=lambda e: e.alias)
    return out


def verification(refresh: bool = False) -> "Verification":
    """The live-probe cache written by `pipa-check models`.

    Single owner: state/model_verification.json. The dashboard, the picker and
    the doctor all read it, so a model the probe rejected does not reappear as
    healthy elsewhere.

    Memoised per resolved path, not globally — a caller that redirects the
    state dir (every test fixture does) must not keep reading the previous
    directory's probe results.
    """
    global _VERIFICATION, _VERIFICATION_KEY
    key = str(config.state_dir() / VERIFICATION_FILE)
    if refresh or _VERIFICATION is None or key != _VERIFICATION_KEY:
        _VERIFICATION = Verification.load(Path(key))
        _VERIFICATION_KEY = key
    return _VERIFICATION


_VERIFICATION: Optional["Verification"] = None
_VERIFICATION_KEY = ""
VERIFICATION_FILE = "model_verification.json"


class Verification:
    """{model id -> {ok, detail}} from the last live probe.

    `empty` distinguishes "nobody has probed yet" from "everything failed".
    The first means trust nothing and show everything; the second means trust
    the cache.
    """

    def __init__(self, rows: dict, checked_at: str = "") -> None:
        self.rows = rows
        self.checked_at = checked_at

    @classmethod
    def load(cls, path: Path) -> "Verification":
        try:
            data = json.loads(path.read_text())
        except Exception:
            return cls({})
        if not isinstance(data, dict):
            return cls({})
        rows = {
            k: v for k, v in data.items()
            if k != "_checked_at" and isinstance(v, dict)
        }
        return cls(rows, str(data.get("_checked_at") or ""))

    @property
    def empty(self) -> bool:
        return not self.rows

    def ok(self, model: str) -> bool:
        """True when the model is usable, or has not been probed.

        Fails OPEN on an unprobed model only while the cache is empty, so a
        fresh install is never left with an empty picker. Once a probe has run,
        an unprobed id is treated as not usable — otherwise every new model
        would slip into the picker between probes.
        """
        if self.empty:
            return True
        row = self.rows.get(model)
        return bool(row and row.get("ok"))


def runtime_model_list() -> List[Dict[str, str]]:
    """Ordered [{id, name}] for the opencode model picker.

    Tier aliases first, then explicit ids, then descriptive provider/model ids.

    Only models the gateway can actually serve appear. Two filters, in this
    order:

    1. `active` — every env key the owning provider needs is present.
    2. verified callable — `pipa-check models` live-probes the whole catalog
       and caches the result in state/model_verification.json. Without this
       filter the picker advertised every discovered model, including the ones
       the probe had just proven broken ("free tier can only be used from
       within OpenCode", HTTP 429, HTTP 401). The user picks one, the session
       dies, and it looks like the harness is at fault — precisely the failure
       invariant 3 exists to prevent. The probe work was already being done;
       nothing read the result.

    When there is no verification data yet (fresh install), only filter (1)
    applies, so the picker is never empty just because nobody has run the
    check. Tier aliases are never filtered out: dropping one breaks every
    agent pinned to it, which is a worse failure than a dead model in a list.
    """
    resolved = tier_resolution()
    es = {e.alias: e for e in entries(active_only=True)}
    seen: set[str] = set()
    out: List[Dict[str, str]] = []

    def add(mid: str, name: str) -> None:
        if mid and mid not in seen:
            seen.add(mid)
            out.append({"id": mid, "name": name})

    for tier in TIER_ALIASES:
        e = resolved.get(tier)
        if e is not None and e.active:
            add(tier, e.display)
    extras: List[tuple[str, str]] = []
    for alias, e in es.items():
        if not verification().ok(alias):
            continue
        extras.append((alias, e.display))
        extras.append((e.slug, e.display))
    for mid, name in sorted(extras):
        add(mid, name)
    return out


def tier_policy() -> Dict[str, dict]:
    """Descriptive policy per tier from models/tiers.yaml (labels, budgets).

    Returns {tier: {label, description, cost_ceiling_usd_per_1m,
    latency_target_ms, min_context, max_steps}}. Includes `jev` — a documented
    decision-model tier that is not gateway-routable, so callers that iterate
    TIER_ALIASES still ignore it, but it is no longer silently dropped.
    Assignments are NOT here — see tier_assignments().
    """
    try:
        import yaml
    except ImportError:
        return {}
    try:
        raw = yaml.safe_load(
            (config.models_dir() / "tiers.yaml").read_text()) or {}
    except Exception:
        return {}
    tiers = raw.get("tiers") or {}
    known = (*TIER_ALIASES, "jev")
    return {t: tiers[t] for t in known if isinstance(tiers.get(t), dict)}


def agent_tier_defaults() -> Dict[str, str]:
    """{agent -> default tier} from models/tiers.yaml agent_tiers (validated).

    The single owner of agent tier defaults; every consumer goes through here.
    Rows naming a tier the gateway cannot route are dropped, and reported by
    `pipa doctor` — silently discarding them (as `router: jev` once was) hid a
    category error rather than fixing it.
    """
    try:
        import yaml
    except ImportError:
        return {}
    try:
        raw = yaml.safe_load(
            (config.models_dir() / "tiers.yaml").read_text()) or {}
    except Exception:
        return {}
    out: Dict[str, str] = {}
    for agent, tier in (raw.get("agent_tiers") or {}).items():
        t = normalize_tier(str(tier))
        if t:
            out[str(agent)] = t
    return out


def undeclared_agent_tiers() -> Dict[str, str]:
    """{agent -> tier} rows in tiers.yaml that no gateway tier can satisfy."""
    try:
        import yaml
    except ImportError:
        return {}
    try:
        raw = yaml.safe_load(
            (config.models_dir() / "tiers.yaml").read_text()) or {}
    except Exception:
        return {}
    return {
        str(agent): str(tier)
        for agent, tier in (raw.get("agent_tiers") or {}).items()
        if not normalize_tier(str(tier))
    }
