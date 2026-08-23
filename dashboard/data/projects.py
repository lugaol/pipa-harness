"""Project registry reader with lightweight per-project enrichment.

Reads state/projects.json (written by pipa.config.register_project) and
adds runtime + rules/skills/memory counts under each project's .pipa/.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from pipa import config


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
    path = config.projects_registry_path()
    try:
        entries = json.loads(path.read_text())
    except Exception:
        return []
    if not isinstance(entries, list):
        return []
    out: List[dict] = []
    for entry in entries:
        if isinstance(entry, dict) and entry.get("path"):
            out.append(_enrich(entry))
    return out
