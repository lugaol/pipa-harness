"""Memory notes: jailed CRUD over the vault layer + recall fan-out.

Scopes:
  global   <harness>/vault/**/*.md
  project  <proj>/.pipa/memory/**/*.md (canonical; legacy extension
           vaults are listed read-only for compatibility)

Every path is resolved against its scope root and must stay inside it.
Notes carry optional `valid_until:` / `as_of:` frontmatter lines; expiry
management rewrites just those lines in the note header.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path, PurePosixPath
from typing import List, Optional, Tuple

from pipa import config

MAX_WRITE_BYTES = 200 * 1024
_SCOPES = ("global", "project")
_FILE_STEM_RE = re.compile(r"[A-Za-z0-9._-]+")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_VALID_UNTIL_RE = re.compile(r"^valid_until:\s*(\S*)\s*$", re.MULTILINE)

_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _scope_roots(scope: str, project_path: Optional[str],
                 writable_only: bool = False) -> List[Path]:
    """Candidate roots for a scope; may not exist yet (first-note case)."""
    roots: List[Path] = []
    if scope == "global":
        roots.append(config.harness_root() / "vault")
    elif scope == "project":
        project = _resolve_project(project_path)
        if project is not None:
            pipa = config.pipa_dir(project)
            roots.append(pipa / "memory")
            if not writable_only:
                ext = pipa / "extension" / "vault"
                legacy = project / config.LEGACY_EXTENSION_DIR / "vault"
                if ext.is_dir():
                    roots.append(ext)
                if legacy.is_dir():
                    roots.append(legacy)
    return roots


def _resolve_project(project_path: Optional[str]) -> Optional[Path]:
    from data import projects as projects_data

    entries = projects_data.registry_entries()
    known = {e["path"] for e in entries}
    if project_path:
        return Path(project_path) if project_path in known else None
    try:
        found = config.find_project()
    except Exception:
        found = None
    if found is not None:
        return found
    return Path(entries[-1]["path"]).expanduser() if entries else None


def scopes_available(project_path: Optional[str]) -> dict:
    """{scope: bool} — which pickers to enable in the UI."""
    return {
        s: bool(_scope_roots(s, project_path)) or s == "global"
        for s in _SCOPES
    }


def _parse_valid_until(content: str) -> Optional[str]:
    m = _VALID_UNTIL_RE.search(content)
    raw = m.group(1) if m else ""
    dm = _DATE_RE.search(raw)
    return dm.group(0) if dm else None


def _is_expired(valid_until: Optional[str]) -> bool:
    if not valid_until:
        return False
    try:
        return date.fromisoformat(valid_until) < date.today()
    except ValueError:
        return False


def list_notes(scope: str, project_path: Optional[str] = None) -> List[dict]:
    """[{root, path_rel, title, group, size_h, mtime_h, valid_until,
    expired, readonly}] sorted by (group, path_rel)."""
    out: List[dict] = []
    for root in _scope_roots(scope, project_path):
        if not root.is_dir():
            continue
        writable = root.name != "vault" or scope == "global"
        for md in sorted(root.rglob("*.md")):
            try:
                stat = md.stat()
                content = md.read_text(errors="replace")
            except OSError:
                continue
            title_m = _TITLE_RE.search(content)
            rel = md.relative_to(root).as_posix()
            vu = _parse_valid_until(content)
            parts = PurePosixPath(rel).parts
            out.append({
                "root": str(root),
                "path_rel": rel,
                "title": title_m.group(1).strip()[:80] if title_m else md.stem,
                "group": parts[0] if len(parts) > 1 else ".",
                "size_h": f"{stat.st_size / 1024:.1f} KB" if stat.st_size >= 1024
                          else f"{stat.st_size} B",
                "mtime_h": _stamp(stat.st_mtime),
                "valid_until": vu,
                "expired": _is_expired(vu),
                "readonly": not writable,
                "scope": scope,
            })
    out.sort(key=lambda n: (n["group"], n["path_rel"]))
    return out


def _stamp(ts: float) -> str:
    from datetime import datetime
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def resolve_note(scope: str, rel: str,
                 project_path: Optional[str] = None) -> Optional[Path]:
    """Jail: `rel` must stay inside a WRITABLE scope root; .md only."""
    if scope not in _SCOPES or not rel:
        return None
    rel = str(rel).strip()
    if rel.startswith(("/", "\\")) or "\\" in rel or "\x00" in rel:
        return None
    parts = PurePosixPath(rel).parts
    if not parts or any(p in ("..", ".", "") for p in parts):
        return None
    if not rel.endswith(".md"):
        return None
    for root in _scope_roots(scope, project_path, writable_only=True):
        try:
            resolved = (root / rel).resolve()
            inside = resolved.relative_to(root.resolve())
        except (OSError, ValueError):
            continue
        return resolved if str(inside) == rel else None
    return None


def read_note(scope: str, rel: str,
              project_path: Optional[str] = None) -> Optional[str]:
    target = resolve_note(scope, rel, project_path)
    if target is None or not target.is_file():
        return None
    try:
        return target.read_text(errors="replace")
    except OSError:
        return None


def new_note_path(scope: str, name: str) -> Tuple[bool, str]:
    """'my-decision' → 'decisions/my-decision.md'; explicit subdirs allowed."""
    name = (name or "").strip().strip("/")
    if not name:
        return False, "name required"
    stem = name[:-3] if name.endswith(".md") else name
    for part in PurePosixPath(stem).parts:
        if not _FILE_STEM_RE.fullmatch(part):
            return False, "name may contain letters, digits, dot, dash, underscore"
    first = PurePosixPath(stem).parts[0]
    if first not in ("decisions", "research", "architecture", "notes"):
        stem = f"notes/{stem}"
    return True, f"{stem}.md"


def write_note(scope: str, rel: str, content: str,
               project_path: Optional[str] = None) -> Tuple[bool, str]:
    payload = content.replace("\r\n", "\n")
    if len(payload.encode("utf-8")) > MAX_WRITE_BYTES:
        return False, f"refusing to write more than {MAX_WRITE_BYTES // 1024}KB"
    target = resolve_note(scope, rel, project_path)
    if target is None:
        return False, f"path rejected by jail: {rel}"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload)
    except OSError as exc:
        return False, f"write failed: {exc}"
    return True, ""


def delete_note(scope: str, rel: str,
                project_path: Optional[str] = None) -> Tuple[bool, str]:
    target = resolve_note(scope, rel, project_path)
    if target is None:
        return False, f"path rejected by jail: {rel}"
    if not target.is_file():
        return False, f"no such note: {rel}"
    try:
        target.unlink()
    except OSError as exc:
        return False, f"delete failed: {exc}"
    return True, ""


def set_expiry(scope: str, rel: str, valid_until: Optional[str],
               project_path: Optional[str] = None) -> Tuple[bool, str]:
    """Rewrite/insert/remove the `valid_until:` line. '' clears it.

    A far-future date ('extend') keeps a note active; clearing removes the
    constraint entirely; a past date marks it expired.
    """
    content = read_note(scope, rel, project_path)
    if content is None:
        return False, f"cannot read {rel}"
    if valid_until:
        dm = _DATE_RE.search(valid_until)
        if not dm:
            return False, "date must be YYYY-MM-DD"
        line = f"valid_until: {dm.group(0)}"
    else:
        line = None
    if _VALID_UNTIL_RE.search(content):
        new = _VALID_UNTIL_RE.sub(
            "" if line is None else line.replace("\\", "\\\\"),
            content, count=1,
        )
    elif line is not None:
        # insert into an existing frontmatter block, else open one
        if content.startswith("---\n"):
            head, sep, rest = content.partition("\n---\n")
            new = f"{head}\n{line}{sep}{rest}"
        else:
            new = f"---\n{line}\n---\n\n{content}"
    else:
        new = content
    if new != content:
        ok, msg = write_note(scope, rel, new, project_path)
        if not ok:
            return ok, msg
    return True, ""


def extend_years(scope: str, rel: str, years: int = 1,
                 project_path: Optional[str] = None) -> Tuple[bool, str]:
    target = date.today().replace(year=date.today().year + years)
    return set_expiry(scope, rel, target.isoformat(), project_path)


def recall(query: str, project_path: Optional[str], limit: int = 12) -> dict:
    """Fan-out over memory-db + vault + code-graph with expiry-aware ranking."""
    try:
        from pipa.recall import recall as do_recall
        return do_recall(query, project=Path(project_path) if project_path else None,
                         limit=limit)
    except Exception as exc:
        return {"results": [], "sources_queried": [], "error": str(exc)}
