"""Runtime detection and machine-global wiring.

A runtime is an agent runner that consumes the shared harness markdown
(AGENTS.md, rules/, skills/, agents/) and talks to models through the
LiteLLM gateway. Each runtime ships its config templates under
clis/<name>/ and wires THE MACHINE (never the project).

Per-project runtime selection lives in <project>/.pipa/runtime (one word).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import config

# Fallback agent -> tier defaults, used ONLY when models/tiers.yaml cannot be
# read (a checkout mid-edit, or a stripped install). The owner is
# models/tiers.yaml::agent_tiers — see `agent_tiers()`. Two owners is how this
# drifted before: a hardcoded map here and a YAML map there, with a doctor
# check that only warned about the disagreement.
_FALLBACK_AGENT_TIERS = {
    "orchestrator": "mid",
    "dev": "mid",
    "qa": "low",
    "explorer": "lowest",
    "analyst": "high",
    "pm": "high",
    "architect": "high",
    "sm": "mid",
    "researcher": "high",
}


def agent_tiers() -> dict[str, str]:
    """{agent: tier} — the single owner is models/tiers.yaml::agent_tiers.

    Every consumer (opencode config rendering, dashboard, recommendations,
    doctor) reads this, so a user editing tiers.yaml changes behaviour
    everywhere at once. Falls back to `_FALLBACK_AGENT_TIERS` only when the
    YAML is unreadable.
    """
    from pipa.model_registry import TIER_ALIASES, agent_tier_defaults, normalize_tier

    declared = agent_tier_defaults()
    if declared:
        return declared
    return {a: t for a, t in _FALLBACK_AGENT_TIERS.items() if normalize_tier(t) in TIER_ALIASES}


def agent_tier(name: str) -> str:
    """Declared default tier for one agent ("" when undeclared)."""
    return agent_tiers().get(name, "")


RUNTIME_FILE = "runtime"


def primary_tier() -> str:
    """Tier driving the runtime primary model.

    User override (`orchestrator` entry in the tier-override store) wins;
    else the `orchestrator` default from models/tiers.yaml. "" when neither
    is a known tier — callers fall back to strongest-assigned.
    """
    from pipa.agent_tiers import override_for
    from pipa.model_registry import TIER_ALIASES, normalize_tier

    tier = normalize_tier(override_for("orchestrator") or "")
    if tier in TIER_ALIASES:
        return tier
    default = normalize_tier(agent_tier("orchestrator"))
    return default if default in TIER_ALIASES else ""


@dataclass
class Runtime:
    name: str
    label: str
    description: str
    binaries: list[str] = field(default_factory=list)
    npm_package: str | None = None
    install_hint: str = ""

    def installed(self) -> bool:
        return any(shutil.which(b) for b in self.binaries)


RUNTIMES: dict[str, Runtime] = {
    r.name: r
    for r in [
        Runtime(
            name="opencode",
            label="OpenCode",
            description="TUI + headless agent runner (opencode.ai)",
            binaries=["opencode"],
            install_hint="curl -fsSL https://opencode.ai/install | bash",
        ),
    ]
}


class RuntimeError_(Exception):
    pass


def names() -> list[str]:
    return list(RUNTIMES)


def installed() -> list[str]:
    return [n for n, r in RUNTIMES.items() if r.installed()]


def resolve(requested: str | None) -> str:
    """Resolve a requested runtime name ('auto' or None) to a concrete one.

    `opencode` is the only runtime, so this returns it unless the caller asks
    for something unknown — in which case it raises rather than guessing.
    """
    if requested and requested != "auto":
        if requested not in RUNTIMES:
            raise RuntimeError_(
                f"unknown runtime '{requested}' (choose: {', '.join(names())}, auto)"
            )
        return requested
    if "opencode" in RUNTIMES:
        return "opencode"
    found = installed()
    if found:
        return found[0]
    return "opencode"  # default target; `pipa up` will install it


def read_project_runtime(project: Path) -> str | None:
    f = project / config.PIPA_DIR / RUNTIME_FILE
    if f.exists():
        value = f.read_text().strip()
        return value or None
    return None


def write_project_runtime(project: Path, name: str) -> None:
    if name not in RUNTIMES:
        raise RuntimeError_(f"unknown runtime '{name}'")
    d = project / config.PIPA_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / RUNTIME_FILE).write_text(name + "\n")


def project_runtime(project: Path) -> str:
    """Effective runtime for a project: file, else auto-detect."""
    return resolve(read_project_runtime(project) or "auto")


# ── wiring ──────────────────────────────────────────────────────────────────

# Sentinel key stamped into every rendered runtime config. It is how a later
# `pipa up` knows the file is OURS and may be regenerated, versus a file the
# user wrote by hand which must be left alone. The previous guard was
# `"pipa" in text`, which matched the substring inside `sk-pipa-local`, inside
# the instruction globs and inside any comment — so it matched every config
# pipa had ever written, and the file was then never re-rendered again. Tier
# changes stopped reaching the runtime the day the file was first created.
WIRED_MARKER = "_pipa_generated"

# Strongest last: tier order doubles as the fallback order.
TIER_ORDER = ("lowest", "low", "mid", "high", "xhigh")


def _is_wired(gcfg: Path) -> bool:
    """True when gcfg carries our marker (safe to regenerate)."""
    try:
        return WIRED_MARKER in gcfg.read_text()
    except OSError:
        return False


def mcp_registry() -> dict[str, dict]:
    """Enabled MCP servers from the mcp/ registry — the single owner.

    Registry entry (mcp/<name>/config.json):
      {"name": "context7", "enabled": true,
       "mcp": {"type": "remote", "url": "...", ...}}
    Future integrations = drop a new folder; nothing else changes.

    A MISSING `enabled` key means enabled. The dashboard used to read the same
    file with the opposite default, so it rendered "disabled" for servers the
    runtime was in fact merging.

    Folders starting with "_" are scaffolding and never merged.
    """
    import json

    servers: dict[str, dict] = {}
    mcp_root = config.mcp_dir()
    if not mcp_root.is_dir():
        return servers
    for cfg in sorted(mcp_root.glob("*/config.json")):
        if cfg.parent.name.startswith("_"):
            continue  # scaffolding (_template) is never merged
        try:
            data = json.loads(cfg.read_text())
        except Exception:
            continue
        if not data.get("enabled", True):
            continue
        name = data.get("name") or cfg.parent.name
        block = data.get("mcp")
        if isinstance(block, dict):
            servers[name] = block
    return servers


def _mcp_fragments() -> tuple[dict, dict]:
    servers = mcp_registry()
    return servers, {f"{name}_*": "allow" for name in servers}




def _strip_jsonc(text: str) -> str:
    """Remove // comments (outside strings) and trailing commas."""
    import re

    out: list[str] = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        out.append(ch)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def render_opencode_config(root: Path) -> dict:
    """Load the global template, inject MCP registry + models, substitute paths."""
    import json

    rt_dir = root / "clis" / "opencode"
    cfg = json.loads(_strip_jsonc((rt_dir / "global.jsonc").read_text()))
    servers, perms = _mcp_fragments()
    cfg["mcp"] = servers
    cfg.setdefault("permission", {}).update(perms)
    cfg[WIRED_MARKER] = {
        "by": "pipa up / dashboard",
        "regenerate": "delete this file, or edit clis/opencode/global.jsonc",
    }

    from pipa.model_registry import runtime_model_list, tier_resolution, TIER_ALIASES

    provider = cfg.setdefault("provider", {}).setdefault("litellm", {})
    provider["models"] = {
        m["id"]: {"name": m["name"]} for m in runtime_model_list()
    }

    # Default models come from user tier assignments. The orchestrator
    # (primary-agent) tier pins the main model when it resolves; otherwise
    # the strongest assigned tier is the main model and the weakest is the
    # small model. No assignment -> template defaults stay untouched (user
    # configures tiers in the dashboard).
    resolved = [t for t in TIER_ALIASES if t in tier_resolution()]
    primary = primary_tier()
    if resolved:
        main = primary if primary in tier_resolution() else resolved[-1]
        cfg["model"] = f"litellm/{main}"
        cfg["small_model"] = f"litellm/{resolved[0]}"

    def walk(node):
        if isinstance(node, str):
            return node.replace("@PIPA_ROOT@", str(root))
        if isinstance(node, list):
            return [walk(x) for x in node]
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        return node

    return walk(cfg)


def _render_session_bus_plugin(root: Path) -> str:
    """Session-bus plugin source with wire-time substitutions."""
    template = root / "clis" / "opencode" / "plugin" / "pipa-session-bus.js"
    bin_path = root / "bin" / "pipa"
    return (
        template.read_text()
        .replace("@@PIPA_BIN@@", str(bin_path))
        .replace("@@PIPA_RUNTIME@@", "opencode")
    )


def _render_memory_plugin(root: Path) -> str:
    """Memory-context plugin source with wire-time substitutions."""
    template = root / "clis" / "opencode" / "plugin" / "pipa-memory-context.js"
    bin_path = root / "bin" / "pipa"
    return template.read_text().replace("@@PIPA_BIN@@", str(bin_path))


def _write_plugin(gdir: Path, filename: str, content: str, actions: list,
                  purpose: str) -> None:
    """Create-only plugin install: existing files are never overwritten."""
    plugin_src = gdir / "plugin" / filename
    if plugin_src.exists():
        actions.append(f"~ kept existing {plugin_src}")
    else:
        plugin_src.parent.mkdir(parents=True, exist_ok=True)
        plugin_src.write_text(content)
        actions.append(f"+ wrote {plugin_src} ({purpose})")


def effective_agent_tier(name: str) -> str:
    """The tier an agent should actually run on.

    Precedence: user override (dashboard Agents page, state/
    agent_llm_overrides.json) > declared default (models/tiers.yaml).

    A tier the gateway cannot route — never assigned, or assigned to a model
    whose API key is missing — is not usable. Rather than emit a frontmatter
    that dies at request time, fall back to the strongest routable tier, so
    every agent always has a working model. Returns "" when no tier at all is
    routable (then the runtime default applies).
    """
    from pipa.agent_tiers import override_for
    from pipa.model_registry import normalize_tier, tier_resolution

    resolved = tier_resolution()
    routable = [t for t in TIER_ORDER if t in resolved]
    for candidate in (normalize_tier(override_for(name) or ""), agent_tier(name)):
        if candidate in routable:
            return candidate
    return routable[-1] if routable else ""


def render_agents(root: Path, gdir: Path) -> list[str]:
    """Materialise <gdir>/agent/*.md from agents/*.md with tiers applied.

    Rendered rather than symlinked because the effective tier is not a property
    of the source file: it is the override store and the current tier
    assignments. A symlink froze agents at whatever model id was written in the
    frontmatter, which is what made the dashboard's per-agent tier picker a
    no-op. Files are written only when their content changes, so this is cheap
    to run on every `pipa up`.

    Never writes through a symlinked out_dir — see the guard below.
    """
    import re

    src_dir = root / "agents"
    out_dir = gdir / "agent"
    actions: list[str] = []
    if not src_dir.is_dir():
        return actions
    if out_dir.is_symlink():
        # An earlier version symlinked ~/.config/opencode/agent at the source
        # tree, and a render through that link rewrote the harness's own
        # agents/*.md — silently, because the write "succeeded". Replace the
        # link with a real directory before rendering.
        actions.append(f"~ replaced symlink {out_dir} with a rendered directory")
        out_dir.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)
    for src in sorted(src_dir.glob("*.md")):
        text = src.read_text()
        tier = effective_agent_tier(src.stem)
        if tier:
            text = re.sub(
                r"(?m)^model: .*$", f"model: litellm/{tier}", text, count=1
            )
        dest = out_dir / src.name
        if dest.exists() and not dest.is_symlink() and dest.read_text() == text:
            continue
        if dest.is_symlink():
            dest.unlink()
        dest.write_text(text)
        actions.append(f"+ agent/{src.name} on tier {tier or '(runtime default)'}")
    return actions


def refresh_agents(root: Path | None = None) -> list[str]:
    """Re-render the deployed agent files after an override change.

    The dashboard persists tier overrides to state/agent_llm_overrides.json;
    until this runs, the change lives in state and every deployed agent keeps
    the tier it was last rendered with — the save looks successful while the
    agent ignores it. Called by the dashboard write paths; `pipa up` reaches
    the same render through wire_opencode. Skipped when the runtime was never
    wired, so a dashboard save never creates a global config dir as a side
    effect. Returns the render actions (empty when nothing changed).
    """
    root = root or config.harness_root()
    gdir = Path.home() / ".config" / "opencode"
    if not gdir.is_dir():
        return []
    return render_agents(root, gdir)


def wire_opencode(project: Path, root: Path) -> list[str]:
    """Global-only OpenCode wiring: ~/.config/opencode (config + shared agents
    + session-bus plugin).

    Projects carry no opencode files — the global config's instruction globs
    pick up each project's AGENTS.md and .pipa/rules/*.md at launch time.
    """
    actions: list[str] = []
    gdir = Path.home() / ".config" / "opencode"
    gcfg = gdir / "opencode.jsonc"
    template = root / "clis" / "opencode" / "global.jsonc"
    if not template.exists():
        actions.append(f"!! missing template {template}")
        return actions
    if gcfg.exists() and _is_wired(gcfg):
        actions.append(f"~ kept existing {gcfg} (delete it to re-render)")
    else:
        gdir.mkdir(parents=True, exist_ok=True)
        import json

        gcfg.write_text(json.dumps(render_opencode_config(root), indent=2) + "\n")
        actions.append(f"+ wrote {gcfg}")
    actions.extend(render_agents(root, gdir))

    # session bus: auto-discovered plugin forwards events via `pipa hook`.
    # Create-only: an existing file (user's or ours) is never overwritten —
    # delete it to get a fresh render.
    plugin_src = gdir / "plugin" / "pipa-session-bus.js"
    plugin_template = root / "clis" / "opencode" / "plugin" / "pipa-session-bus.js"
    if not plugin_template.exists():
        actions.append(f"!! missing session-bus plugin template {plugin_template}")
    else:
        _write_plugin(gdir, "pipa-session-bus.js",
                      _render_session_bus_plugin(root), actions,
                      "session bus → pipa hook")

    # memory context: auto-loads a bounded recall digest into prompts.
    mem_template = root / "clis" / "opencode" / "plugin" / "pipa-memory-context.js"
    if not mem_template.exists():
        actions.append("!! missing memory-context plugin template")
    else:
        _write_plugin(gdir, "pipa-memory-context.js",
                      _render_memory_plugin(root), actions,
                      "memory digest → system prompt")
    return actions




WIRERS = {
    "opencode": wire_opencode,
}


def wire(name: str, project: Path, root: Path | None = None) -> list[str]:
    root = root or config.harness_root()
    return WIRERS[name](project, root)


def ensure_installed(name: str, status_only: bool = False) -> tuple[bool, str]:
    """Make sure the runtime binary is available; install when allowed."""
    rt = RUNTIMES[name]
    if rt.installed():
        return True, f"{rt.label}: installed"
    if status_only:
        return False, f"{rt.label}: MISSING ({rt.install_hint})"
    if rt.npm_package:
        if not shutil.which("npm"):
            return False, f"{rt.label}: npm not found — install Node.js first"
        r = subprocess.run(["npm", "install", "-g", rt.npm_package])
        if r.returncode == 0 and rt.installed():
            return True, f"{rt.label}: installed via npm"
        return False, f"{rt.label}: npm install failed — {rt.install_hint}"
    if name == "opencode":
        r = subprocess.run(
            "curl -fsSL https://opencode.ai/install | bash", shell=True
        )
        os.environ["PATH"] = f"{Path.home() / '.opencode' / 'bin'}:{os.environ['PATH']}"
        if r.returncode == 0 and rt.installed():
            return True, f"{rt.label}: installed"
    return False, f"{rt.label}: install failed — {rt.install_hint}"
