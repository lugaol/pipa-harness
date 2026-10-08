"""Agent discovery + per-agent tier overrides.

Frontmatter discovery over <harness>/agents/*.md plus the project agent
dirs of registered projects (.pipa/agents-local, legacy extension dirs).
Overrides persist at state/agent_llm_overrides.json.

Thin adapter: the frontmatter parser is pipa.commands.agents.parse_frontmatter,
which owns it. The copy that used to live here anchored on `^---\\n` and split
on every colon, so an agent authored with CRLF line endings lost its entire
frontmatter in the dashboard — model, description and all — while the CLI saw it
perfectly.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from pipa import config
from pipa.commands.agents import parse_frontmatter  # re-export: one parser
from data import projects as projects_data

__all__ = ["parse_frontmatter", "discover_agents"]


def _registry_projects() -> List[Path]:
    out: List[Path] = []
    for entry in projects_data.registry_entries():
        project = Path(str(entry["path"])).expanduser()
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


def _agent_bases(root: Path) -> List[tuple[Path, str]]:
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
# Single owner: pipa.agent_tiers. Re-exported here so page modules keep a
# stable import surface.

from pipa.agent_tiers import (
    OVERRIDES_FILE,
    load_overrides,
    override_for,
    overrides_path,
    reset_override,
    save_overrides,
    set_tier_override,
)
