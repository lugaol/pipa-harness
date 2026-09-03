"""Project registry: the single reader for state/projects.json.

registry_entries() is THE raw reader every other module must use
(context, agents). list_projects() adds runtime + rules/skills/memory
counts under each project's .pipa/.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from pipa import config
from pipa.runtime import names as runtime_names


def registry_entries() -> List[dict]:
    """Raw [{path, runtime}] rows; missing/corrupt registry → []."""
    path = config.projects_registry_path()
    try:
        entries = json.loads(path.read_text())
    except Exception:
        return []
    if not isinstance(entries, list):
        return []
    return [
        e for e in entries
        if isinstance(e, dict) and e.get("path")
    ]


def set_runtime(path_str: str, runtime: str) -> tuple[bool, str]:
    """Write <proj>/.pipa/runtime + re-register — path must be in the registry."""
    known = {p["path"] for p in list_projects()}
    if path_str not in known:
        return False, "path not in project registry"
    if runtime not in runtime_names():
        return False, f"runtime must be one of: {', '.join(runtime_names())}"
    project = Path(path_str)
    marker = config.pipa_dir(project) / config.RUNTIME_MARKER
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(runtime + "\n")
    except OSError as exc:
        return False, f"could not write runtime marker: {exc}"
    try:
        config.register_project(project, runtime)
    except Exception as exc:
        return False, f"could not update registry: {exc}"
    return True, ""


def _read_runtime(project: Path) -> str:
    runtime_file = config.pipa_dir(project) / config.RUNTIME_MARKER
    try:
        if runtime_file.is_file():
            return runtime_file.read_text().strip()
    except OSError:
        pass
    return ""


def _count_md(directory: Path, pattern: str = "*.md") -> int:
    try:
        if not directory.is_dir():
            return 0
        return sum(1 for p in directory.rglob(pattern) if p.is_file())
    except OSError:
        return 0


def _count_skills(directory: Path) -> int:
    try:
        if not directory.is_dir():
            return 0
        return sum(1 for p in directory.glob("*/SKILL.md") if p.is_file())
    except OSError:
        return 0


def _enrich(entry: dict) -> dict:
    project = Path(str(entry.get("path", ""))).expanduser()
    pipa = config.pipa_dir(project)
    ext = pipa / "extension"
    legacy_ext = project / config.LEGACY_EXTENSION_DIR
    rules = sum(_count_md(d) for d in (pipa / "rules", ext / "rules", legacy_ext / "rules"))
    skills = sum(
        _count_skills(d)
        for d in (pipa / "skills", ext / "skills", legacy_ext / "skills")
    )
    memory_files = sum(
        _count_md(d)
        for d in (pipa / "memory", ext / "vault")
    ) + (1 if (config.project_state_dir(project) / "memory.db").exists() else 0)
    return {
        "path": str(project),
        "name": project.name or str(project),
        "exists": project.is_dir(),
        "runtime": entry.get("runtime") or _read_runtime(project) or "auto",
        "rules": rules,
        "skills": skills,
        "memory": memory_files,
    }


def list_projects() -> List[dict]:
    """Registered projects enriched; missing/corrupt registry → []."""
    return [_enrich(entry) for entry in registry_entries()]
