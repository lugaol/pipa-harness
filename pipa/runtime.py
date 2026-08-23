"""Runtime detection and machine-global wiring.

A runtime is an agent runner that consumes the shared harness markdown
(AGENTS.md, rules/, skills/, agents/) and talks to models through the
LiteLLM gateway. Each runtime ships its config templates under
clis/<name>/ and wires THE MACHINE (never the project): opencode renders
~/.config/opencode/opencode.jsonc (with the mcp/ registry merged in);
dsh writes ~/.dsh/cordis.patch.yml + .credentials.yaml.

Per-project runtime selection lives in <project>/.pipa/runtime (one word).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import config

# pipa agent -> LiteLLM model alias (used when generating runtime configs)
AGENT_MODEL_MAP = {
    "dev": "primary",
    "qa": "fast",
    "explorer": "explore",
    "analyst": "deep",
    "pm": "deep",
    "architect": "deep",
    "sm": "primary",
    "researcher": "deep",
}

RUNTIME_FILE = "runtime"


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
        Runtime(
            name="deepseek-harness",
            label="DeepSeek Harness",
            description="DeepSeek agent harness with native NDJSON session log",
            binaries=["deepseek-harness", "dsh"],
            npm_package="@deepseek-ai/dsh",
            install_hint="npm install -g @deepseek-ai/dsh",
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

    Auto-detection prefers DeepSeek Harness when available.
    """
    if requested and requested != "auto":
        if requested not in RUNTIMES:
            raise RuntimeError_(
                f"unknown runtime '{requested}' (choose: {', '.join(names())}, auto)"
            )
        return requested
    found = installed()
    if "deepseek-harness" in found:
        return "deepseek-harness"
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

def _symlink(target: Path | str, link: Path, actions: list[str]) -> None:
    if link.is_symlink() or link.exists():
        if link.is_symlink() and os.readlink(link) == str(target):
            return
        actions.append(f"~ kept existing {link}")
        return
    link.symlink_to(target)
    actions.append(f"+ {link} -> {target}")


def _mcp_registry(root: Path) -> dict[str, dict]:
    """Enabled MCP servers from the mcp/ registry.

    Registry entry (mcp/<name>/config.json):
      {"name": "context7", "enabled": true,
       "mcp": {"type": "remote", "url": "...", ...}}
    Future integrations = drop a new folder; nothing else changes.
    """
    import json

    servers: dict[str, dict] = {}
    mcp_root = config.mcp_dir()
    if not mcp_root.is_dir():
        return servers
    for cfg in sorted(mcp_root.glob("*/config.json")):
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


def _mcp_fragments(root: Path) -> tuple[dict, dict]:
    servers = _mcp_registry(root)
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
    """Load the global template, inject MCP registry + permissions, substitute paths."""
    import json

    rt_dir = root / "clis" / "opencode"
    cfg = json.loads(_strip_jsonc((rt_dir / "global.jsonc").read_text()))
    servers, perms = _mcp_fragments(root)
    cfg["mcp"] = servers
    cfg.setdefault("permission", {}).update(perms)

    def walk(node):
        if isinstance(node, str):
            return node.replace("@PIPA_ROOT@", str(root))
        if isinstance(node, list):
            return [walk(x) for x in node]
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        return node

    return walk(cfg)


def wire_opencode(project: Path, root: Path) -> list[str]:
    """Global-only OpenCode wiring: ~/.config/opencode (config + shared agents).

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
    if gcfg.exists() and "pipa" in gcfg.read_text():
        actions.append(f"~ kept existing {gcfg} (delete it to re-render)")
    else:
        gdir.mkdir(parents=True, exist_ok=True)
        import json

        gcfg.write_text(json.dumps(render_opencode_config(root), indent=2) + "\n")
        actions.append(f"+ wrote {gcfg}")
    _symlink(root / "agents", gdir / "agent", actions)
    return actions


def wire_deepseek_harness(project: Path, root: Path) -> list[str]:
    """Wire dsh to the LiteLLM gateway via its real patch format.

    dsh config is machine-global: we write ~/.dsh/cordis.patch.yml (machine
    layer, outranks per-profile layers) — only when missing or already
    pipa-managed, never over user edits — plus ~/.dsh/.credentials.yaml with
    the LITELLM_API_KEY ref on fresh installs (dsh resolves apiKeyEnv from
    env or that file; no key ever in YAML). Projects carry nothing.
    """
    actions: list[str] = []
    rt_dir = root / "clis" / "deepseek-harness"
    template = rt_dir / "cordis.patch.yml"
    if not template.exists():
        actions.append(f"!! missing template {template}")
        return actions

    text = template.read_text().replace("@LITELLM_URL@", config.LITELLM_URL)

    dsh_home = Path.home() / ".dsh"
    patch = dsh_home / "cordis.patch.yml"
    if patch.exists() and "pipa" not in patch.read_text()[:200]:
        actions.append(f"~ kept existing {patch}")
    else:
        dsh_home.mkdir(parents=True, exist_ok=True)
        if not patch.exists() or patch.read_text() != text:
            patch.write_text(text)
            actions.append(f"+ wrote {patch}")

    creds = dsh_home / ".credentials.yaml"
    if not creds.exists():
        creds.write_text(
            "version: 1\nrefs:\n"
            f"  LITELLM_API_KEY: {config.LITELLM_KEY}\n"
        )
        actions.append(f"+ wrote {creds} (LITELLM_API_KEY ref)")
    elif "LITELLM_API_KEY" not in creds.read_text():
        actions.append(
            f"~ add 'LITELLM_API_KEY: {config.LITELLM_KEY}' under refs in {creds}"
        )
    return actions


WIRERS = {
    "opencode": wire_opencode,
    "deepseek-harness": wire_deepseek_harness,
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
