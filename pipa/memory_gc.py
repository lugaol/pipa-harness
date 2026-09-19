"""Retention GC for harness state (dry-run by default).

Single owner for state retention: summaries rollup + scratch prune.
Never touches the spend ledger, the session bus, or vault knowledge.

Summaries (state/summaries/*.md) older than SUMMARIES_RETENTION_DAYS
(default 180) are appended into monthly rollups under
state/summaries/rollups/ and then deleted. Scratch files
(state/scratch/**) older than SCRATCH_RETENTION_DAYS (default 30) are
pruned outright (binary/shots — nothing to roll up).

Never touches: the spend ledger, the session bus, vault knowledge notes.
Over-budget vault notes are REPORTED only (memory-hygiene budgets:
vault <= 100 lines, project memory <= 150) — knowledge is never auto-pruned.

Usage:
  pipa memory-gc [--apply] [--manifest]
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

VAULT_BUDGET = 100
PROJECT_MEMORY_BUDGET = 150


def _cutoff(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")


def collect_candidates(state_dir: Path, vault: Path,
                       summaries_days: int = 180,
                       scratch_days: int = 30) -> dict:
    """{rel_path: (action, reason)} eligible for GC. Pure sink: no I/O writes.

    actions: "rollup" (summaries -> monthly rollup), "prune" (scratch),
    "report" (over-budget vault notes — human decides).
    """
    out: dict[str, tuple[str, str]] = {}
    summaries_cut, scratch_cut = _cutoff(summaries_days), _cutoff(scratch_days)

    summaries = state_dir / "summaries"
    if summaries.is_dir():
        for note in sorted(summaries.glob("*.md")):
            if note.name == "README.md":
                continue
            if DATE_RE.fullmatch(note.stem[:10]) and note.stem[:10] < summaries_cut:
                out[f"summaries/{note.name}"] = (
                    "rollup", f"summary older than {summaries_days}d")

    scratch = state_dir / "scratch"
    if scratch.is_dir():
        for f in sorted(scratch.rglob("*")):
            if not f.is_file():
                continue
            try:
                mtime = datetime.fromtimestamp(
                    f.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d")
            except OSError:
                continue
            if mtime < scratch_cut:
                out[f"scratch/{f.relative_to(scratch).as_posix()}"] = (
                    "prune", f"scratch older than {scratch_days}d")

    for scope, root, budget in (
            ("vault", vault, VAULT_BUDGET),):
        if not root.is_dir():
            continue
        for note in sorted(root.rglob("*.md")):
            if "hindsight" in note.parts and note.name == "README.md":
                continue
            try:
                lines = sum(1 for _ in note.open(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            if lines > budget:
                out[f"{scope}/{note.relative_to(root).as_posix()}"] = (
                    "report", f"{lines} lines over budget {budget}")
    return out


def _rollup_dest(state_dir: Path, name: str) -> Path:
    return state_dir / "summaries" / "rollups" / f"{name[:7]}.md"


def apply_gc(state_dir: Path, candidates: dict) -> dict:
    """Roll up summaries, prune scratch. Returns counts. Report-only left alone."""
    rolled: dict[str, list[str]] = {}
    for rel, (action, _reason) in sorted(candidates.items()):
        if action != "rollup":
            continue
        src = state_dir / rel
        try:
            body = src.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if body:
            rolled.setdefault(rel, []).append(
                f"\n<!-- rolled up from {rel} -->\n{body}\n")
    rollups_written = 0
    for rel, chunks in sorted(rolled.items()):
        dest = _rollup_dest(state_dir, Path(rel).name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        existing = dest.read_text(encoding="utf-8") if dest.exists() else ""
        dest.write_text((existing.rstrip() + "\n" if existing.strip() else "")
                        + "".join(chunks), encoding="utf-8")
        rollups_written += 1
    pruned, deleted = 0, 0
    for rel, (action, _reason) in sorted(candidates.items()):
        if action not in ("rollup", "prune"):
            continue
        try:
            (state_dir / rel).unlink()
            if action == "rollup":
                pruned += 1
            else:
                deleted += 1
        except OSError:
            continue
    reported = sum(1 for _, (a, _) in candidates.items() if a == "report")
    return {"rollups_written": rollups_written, "summaries_pruned": pruned,
            "scratch_deleted": deleted, "reported": reported}


