"""Context-authoring store for rules/skills/agents markdown (+ MCP registry).

Pure + jailed: every user-supplied path resolves against a tier root and
must match an allowlisted glob pattern before any FS access. Global tier
sits at the harness install root; project tier sits at a registered
project's .pipa/ overlay. Memory notes live in data/memory.py.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import List, Optional, Tuple

from pipa import config
from data import projects as projects_data

TABS = ("rules", "skills", "agents", "mcp")
TIERS = ("global", "project")

MAX_WRITE_BYTES = 200 * 1024
_SKILL_SLUG_RE = re.compile(r"[a-z0-9-]+")
_FILE_STEM_RE = re.compile(r"[A-Za-z0-9._-]+")

# rel globs are relative to the tier base:
#   global  -> harness_root()          project -> <proj>/.pipa/
_PATTERNS = {
    ("global", "rules"): ("rules/*.md",),
    ("global", "skills"): ("skills/*/SKILL.md",),
    ("global", "agents"): ("agents/*.md",),
    ("project", "rules"): ("rules/*.md",),
    ("project", "skills"): ("skills/*/SKILL.md",),
    ("project", "agents"): ("agents-local/*.md",),
}


def list_projects() -> List[dict]:
    """Registry projects available to the project tier (dashboard has no cwd)."""
    return projects_data.registry_entries()


def tier_root(tier: str, project_path: Optional[str] = None) -> Optional[Path]:
    """Base dir for a tier.

    global  -> harness install root
    project -> the named registry project (falls back to find_project() when
               no name is given, which only works for same-cwd callers; with
               no cwd match either, the newest registry entry wins).
    """
    if tier == "global":
        return config.harness_root()
    if tier == "project":
        if project_path:
            if project_path not in {e.get("path") for e in list_projects()}:
                return None
            project = Path(project_path)
        else:
            try:
                project = config.find_project()
            except Exception:
                project = None
            if project is None:
                entries = list_projects()
                project = Path(entries[-1]["path"]) if entries else None
                if project is None:
                    return None
        return config.pipa_dir(project) if project.exists() else None
    return None


def _compiled_pattern(pat: str):
    """Glob→regex where * never crosses '/' and ** matches any depth."""
    parts = []
    for seg in pat.split("/"):
        if seg == "**":
            parts.append("(?:[^/]+/)*")
        else:
            parts.append("".join("[^/]*" if c == "*" else re.escape(c) for c in seg))
    return re.compile("^" + "/".join(parts) + "$")


def resolve_entry(tier: str, tab: str, rel: str,
                  project_path: Optional[str] = None) -> Optional[Path]:
    """Jail: resolve `rel` inside the tier base or return None.

    Rejects absolute paths, `..` segments, non-.md targets and anything
    outside the tier's allowlisted glob patterns.
    """
    base = tier_root(tier, project_path)
    if base is None or tab not in TABS or not rel:
        return None
    rel = str(rel).strip()
    if not rel or rel.startswith(("/", "\\")) or "\\" in rel or "\x00" in rel:
        return None
    parts = PurePosixPath(rel).parts
    if not parts or any(p in ("..", ".", "") for p in parts):
        return None
    if not rel.endswith(".md"):
        return None
    try:
        resolved = (base / rel).resolve()
        base_resolved = Path(base).resolve()
    except OSError:
        return None
    try:
        rel_posix = resolved.relative_to(base_resolved).as_posix()
    except ValueError:
        return None
    for pat in _PATTERNS.get((tier, tab), ()):
        if _compiled_pattern(pat).match(rel_posix):
            return resolved
    return None


def _title_of(path: Path) -> str:
    """First markdown heading, else the file stem."""
    try:
        for line in path.read_text(errors="replace").splitlines()[:40]:
            if line.startswith("#"):
                title = line.lstrip("#").strip()
                if title:
                    return title[:80]
    except OSError:
        pass
    return path.stem


def list_entries(tier: str, project_path: Optional[str], tab: str) -> List[dict]:
    """[{path_rel, title, size, size_h, mtime_h}] sorted by path."""
    base = tier_root(tier, project_path)
    if base is None or tab not in TABS:
        return []
    seen: set = set()
    out: List[dict] = []
    for pat in _PATTERNS.get((tier, tab), ()):
        try:
            matches = sorted(base.glob(pat))
        except OSError:
            continue
        for path in matches:
            key = str(path)
            if key in seen or not path.is_file():
                continue
            seen.add(key)
            try:
                stat = path.stat()
            except OSError:
                continue
            out.append({
                "path_rel": path.relative_to(base).as_posix(),
                "title": _title_of(path),
                "size": stat.st_size,
                "size_h": f"{stat.st_size / 1024:.1f} KB" if stat.st_size >= 1024
                          else f"{stat.st_size} B",
                "mtime_h": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
    out.sort(key=lambda e: e["path_rel"])
    return out


def read_entry(tier: str, project_path: Optional[str], tab: str, rel: str) -> Optional[str]:
    target = resolve_entry(tier, tab, rel, project_path)
    if target is None or not target.is_file():
        return None
    try:
        return target.read_text(errors="replace")
    except OSError:
        return None


def new_entry_path(tier: str, project_path: Optional[str], tab: str, name: str) -> Tuple[bool, str]:
    """Map a user-typed name to a jailed rel path ('skills/<slug>/SKILL.md'...)."""
    name = (name or "").strip().strip("/")
    if not name:
        return False, "name required"
    if tab == "skills":
        if not _SKILL_SLUG_RE.fullmatch(name):
            return False, "skill folder name must be lowercase [a-z0-9-]"
        return True, f"skills/{name}/SKILL.md"
    stem = name[:-3] if name.endswith(".md") else name
    if not stem or not _FILE_STEM_RE.fullmatch(stem):
        return False, "name may contain letters, digits, dot, dash, underscore"
    return True, f"{tab}/{stem}.md"


def write_entry(tier: str, project_path: Optional[str], tab: str, rel: str, content: str) -> Tuple[bool, str]:
    """Create/update one entry through the jail; rejects >200KB payloads."""
    payload = content.replace("\r\n", "\n")
    if len(payload.encode("utf-8")) > MAX_WRITE_BYTES:
        return False, f"refusing to write more than {MAX_WRITE_BYTES // 1024}KB"
    target = resolve_entry(tier, tab, rel, project_path)
    if target is None:
        return False, f"path rejected by jail: {rel}"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload)
    except OSError as exc:
        return False, f"write failed: {exc}"
    return True, ""


def delete_entry(tier: str, project_path: Optional[str], tab: str, rel: str) -> Tuple[bool, str]:
    target = resolve_entry(tier, tab, rel, project_path)
    if target is None:
        return False, f"path rejected by jail: {rel}"
    if not target.is_file():
        return False, f"no such entry: {rel}"
    try:
        target.unlink()
        if tab == "skills":
            skill_dir = target.parent
            if skill_dir.is_dir() and not any(skill_dir.iterdir()):
                skill_dir.rmdir()
    except OSError as exc:
        return False, f"delete failed: {exc}"
    return True, ""


def group_of(rel: str) -> str:
    """Memory grouping key: first subdir under the tier root, else '.'."""
    parts = PurePosixPath(str(rel)).parts
    return parts[0] if len(parts) > 1 else "."
