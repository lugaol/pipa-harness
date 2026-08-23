"""Agent discovery + per-agent model overrides.

Frontmatter discovery over <harness>/agents/*.md plus the extension agent
dirs of registered projects (.pipa/extension/agents, legacy
.harness_extension/agents). Overrides persist at state/agent_llm_overrides.json.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pipa import config

OVERRIDES_FILE = "agent_llm_overrides.json"
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def parse_frontmatter(text: str) -> Tuple[dict, str]:
    """Ported from the old dashboard: flat `key: value` frontmatter only."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm: Dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip('"').strip("'")
    return fm, m.group(2)


def _registry_projects() -> List[Path]:
    path = config.projects_registry_path()
    try:
        entries = json.loads(path.read_text())
    except Exception:
        return []
    if not isinstance(entries, list):
        return []
    out: List[Path] = []
    for entry in entries:
        try:
            raw = entry.get("path") if isinstance(entry, dict) else None
        except AttributeError:
            raw = None
        if not raw:
            continue
        project = Path(str(raw)).expanduser()
        if project.is_dir():
            out.append(project)
    return out


def _project_agent_dirs(project: Path) -> List[Path]:
    dirs = []
    for rel in (".pipa/agents-local", ".pipa/extension/agents", ".harness_extension/agents"):
        cand = project / rel
        if cand.is_dir():
            dirs.append(cand)
    return dirs


def _agent_bases(root: Path) -> List[Tuple[Path, str]]:
    bases: List[Tuple[Path, str]] = [(root / "agents", "harness")]
    for project in _registry_projects():
        for d in _project_agent_dirs(project):
            bases.append((d, project.name))
    return bases


def discover_agents() -> List[dict]:
    """[{name, description, mode, model, permission, source}] deduped by path."""
    root = config.harness_root()
    agents: List[dict] = []
    seen = set()
    for base, source in _agent_bases(root):
        if not base.is_dir():
            continue
        for f in sorted(base.glob("*.md")):
            key = str(f)
            if key in seen:
                continue
            seen.add(key)
            try:
                text = f.read_text(errors="replace")
            except OSError:
                continue
            fm, _body = parse_frontmatter(text)
            agents.append({
                "name": fm.get("name", f.stem),
                "description": fm.get("description", ""),
                "mode": fm.get("mode", ""),
                "model": fm.get("model", ""),
                "permission": fm.get("permission", ""),
                "source": source,
            })
    return agents


# ── overrides store ─────────────────────────────────────────────────────────

def overrides_path() -> Path:
    return config.state_dir() / OVERRIDES_FILE


def load_overrides() -> dict:
    """{agent_name_or_path: {"model": str}}; {} when absent/corrupt."""
    try:
        data = json.loads(overrides_path().read_text())
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def save_overrides(data: dict) -> None:
    path = overrides_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def set_override(agent: str, model: str) -> None:
    """Set (non-empty model) or clear (empty model) one agent's override."""
    if not agent:
        return
    overrides = load_overrides()
    if model.strip():
        overrides[agent] = {"model": model.strip()}
    else:
        overrides.pop(agent, None)
    save_overrides(overrides)


def override_for(agent_name: str) -> Optional[str]:
    row = load_overrides().get(agent_name) or load_overrides().get(f"agents/{agent_name}.md")
    if isinstance(row, dict):
        model = row.get("model")
        return str(model) if model else None
    return None
