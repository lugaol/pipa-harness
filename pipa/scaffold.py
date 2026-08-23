"""Project scaffolding (.pipa/) and migration between layouts.

pipa init     — create a THIN project overlay (global install does the rest)
pipa migrate  — legacy .harness_extension/ -> old .pipa/extension/ layout
pipa init on an existing legacy project offers the same via migrate_to_thin

Thin per-project layout (everything else lives in the global install):

  project/
  ├── AGENTS.md              ← symlink → .pipa/AGENTS.md (project facts only)
  └── .pipa/
      ├── runtime            ← "opencode" | "deepseek-harness"
      ├── AGENTS.md          ← real file: name, build/test cmds, quirks
      ├── rules/*.md         ← project context (HARD/SOFT rules)
      ├── memory/            ← decisions/ research/ notes (as_of/valid_until)
      ├── skills/            ← OPTIONAL project-only skills (override global)
      └── state/             ← session bus, memory.db, scratch (gitignored)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from . import config, runtime as runtimes

RUNTIME_ONLY_FILES = {"opencode.jsonc", "pipa-up"}

GITIGNORE_ENTRIES = [
    "graphify-out/",
    f"{config.PIPA_DIR}/state/",
    f"{config.PIPA_DIR}/memory.db",
    ".opencode",
    f"{config.PIPA_DIR}/*.local.*",
]


class ScaffoldError(Exception):
    pass


# ── detection ───────────────────────────────────────────────────────────────

def detect_name(target: Path) -> str:
    pj = target / "package.json"
    if pj.exists():
        try:
            name = json.loads(pj.read_text()).get("name", "")
            if name:
                return name
        except Exception:
            pass
    for fname in ("pyproject.toml", "Cargo.toml"):
        f = target / fname
        if f.exists():
            m = re.search(r'\[project\]\s*\n[^\n]*name\s*=\s*"([^"]+)"', f.read_text()) or \
                re.search(r'\[package\]\s*\n[^\n]*name\s*=\s*"([^"]+)"', f.read_text())
            if m:
                return m.group(1)
    try:
        url = subprocess.run(
            ["git", "-C", str(target), "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return re.sub(r".*/", "", url).replace(".git", "")
    except Exception:
        pass
    return target.name


def detect_build(target: Path) -> str:
    if (target / "gradlew").exists():
        return "./gradlew assembleDebug"
    if (target / "package.json").exists():
        return "npm run build"
    if (target / "Cargo.toml").exists():
        return "cargo build"
    if (target / "Makefile").exists():
        return "make"
    if (target / "pyproject.toml").exists() or (target / "setup.py").exists():
        return "pip install -e ."
    return "none detected — add your build command"


def detect_test(target: Path) -> str:
    if (target / "gradlew").exists():
        return "./gradlew test"
    if (target / "package.json").exists():
        return "npm test"
    if (target / "Cargo.toml").exists():
        return "cargo test"
    mk = target / "Makefile"
    if mk.exists() and re.search(r"^test:", mk.read_text(), re.MULTILINE):
        return "make test"
    if (target / "pyproject.toml").exists() or (target / "requirements.txt").exists():
        return "pytest"
    return "none detected — add your test command"


# ── template helpers ────────────────────────────────────────────────────────

def _scaffold_templates(root: Path) -> Path:
    return root / "templates" / "project_scaffold"


def _copy_tree(src: Path, dst: Path, actions: list[str]) -> None:
    for item in sorted(src.rglob("*")):
        if not item.is_file():
            continue
        rel = item.relative_to(src)
        if rel.name in RUNTIME_ONLY_FILES:
            continue
        target = dst / rel
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        actions.append(f"+ {target}")


def fill_agents_md(target: Path) -> dict[str, str]:
    """Fill AGENTS.md placeholders from detected project facts. Idempotent."""
    agents = None
    for c in (
        target / config.PIPA_DIR / "AGENTS.md",
        target / config.PIPA_DIR / "extension" / "AGENTS.md",
        target / config.LEGACY_EXTENSION_DIR / "AGENTS.md",
        target / "AGENTS.md",
    ):
        if c.exists() and not c.is_symlink():
            agents = c
            break
        if c.is_symlink() and c.resolve().exists():
            agents = c.resolve()
            break
    if agents is None:
        return {}
    facts = {
        "name": detect_name(target),
        "build": detect_build(target),
        "test": detect_test(target),
    }
    text = agents.read_text()
    replacements = {
        "{{PROJECT_NAME}}": facts["name"],
        "{{PROJECT_DESCRIPTION}}": f"One-line description of {facts['name']}.",
        "{{BUILD_COMMAND}}": facts["build"],
        "{{TEST_COMMAND}}": facts["test"],
        "<Project name>": facts["name"],
        "<build command>": facts["build"],
        "<test command>": facts["test"],
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    agents.write_text(text)
    return facts


# ── init (thin layout) ──────────────────────────────────────────────────────

def is_legacy_layout(target: Path) -> bool:
    return (target / config.PIPA_DIR / "extension").is_dir()


def init_project(
    target: Path,
    runtime_name: str = "auto",
    project_type: str = "generic",
    root: Path | None = None,
) -> list[str]:
    """Scaffold a thin .pipa/ overlay in a project. Idempotent.

    Legacy projects (old .pipa/extension layout) are migrated to thin
    automatically instead of being duplicated.
    """
    root = root or config.harness_root()
    target = target.resolve()
    actions: list[str] = []

    if not (target / ".git").exists() and not config.git_root(target):
        raise ScaffoldError(f"{target} is not a git repo")

    name = runtimes.resolve(runtime_name)
    actions.append(f"runtime: {name}")

    pipa_dir = config.pipa_dir(target)

    # Legacy layout: convert, don't duplicate.
    if is_legacy_layout(target):
        actions.extend(migrate_to_thin(target, root))

    # 1. Thin overlay files from templates/project_scaffold/
    src = _scaffold_templates(root)
    if not src.exists():
        raise ScaffoldError(f"scaffold templates not found: {src}")
    _copy_tree(src, pipa_dir, actions)

    # 1b. project-type overlay (rules land beside the base ones)
    template_dir = root / "templates" / "project" / project_type
    if template_dir.is_dir():
        for item in sorted(template_dir.rglob("*")):
            if item.is_file():
                rel = item.relative_to(template_dir)
                dest = pipa_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)
        actions.append(f"+ overlay project-type template: {project_type}")
    elif project_type != "generic":
        actions.append(f"!! project-type template '{project_type}' not found, using generic")

    # 2. .pipa/runtime + state/
    runtimes.write_project_runtime(target, name)
    (pipa_dir / "state").mkdir(parents=True, exist_ok=True)
    actions.append(f"+ {pipa_dir / 'runtime'} ({name})")

    # 3. Root AGENTS.md symlink → .pipa/AGENTS.md
    agents_link = target / "AGENTS.md"
    rel_target = f"{config.PIPA_DIR}/AGENTS.md"
    if not agents_link.exists() and not agents_link.is_symlink():
        agents_link.symlink_to(rel_target)
        actions.append(f"+ AGENTS.md -> {rel_target}")
    elif agents_link.is_symlink() and os.readlink(agents_link) != rel_target \
            and "extension" in os.readlink(agents_link):
        agents_link.unlink()
        agents_link.symlink_to(rel_target)
        actions.append(f"+ AGENTS.md re-pointed -> {rel_target}")
    elif not agents_link.is_symlink():
        actions.append("~ AGENTS.md exists (not a symlink, leaving untouched)")

    # 4. Runtime wiring is machine-global now (writes ~/.config, ~/.dsh)
    actions.extend(runtimes.wire(name, target, root))

    # 5. .graphifyignore from the scaffold templates
    gi_src = _scaffold_templates(root) / ".graphifyignore"
    if gi_src.exists() and not (target / ".graphifyignore").exists():
        shutil.copy2(gi_src, target / ".graphifyignore")
        actions.append("+ .graphifyignore")

    # 6. .gitignore entries
    gitignore = target / ".gitignore"
    existing = gitignore.read_text() if gitignore.exists() else ""
    missing = [e for e in GITIGNORE_ENTRIES if e not in existing]
    if missing:
        with gitignore.open("a") as f:
            f.write("\n# pipa_harness\n" + "\n".join(missing) + "\n")
        actions.append("+ .gitignore (harness artifacts)")

    # 7. Register globally (dashboard/extensions view)
    try:
        config.register_project(target, name)
    except Exception:
        pass

    # 8. Auto-fill AGENTS.md placeholders
    facts = fill_agents_md(target)
    if facts:
        actions.append(
            f"+ AGENTS.md placeholders filled "
            f"(name={facts['name']}, build={facts['build']}, test={facts['test']})"
        )
    return actions


# ── legacy -> thin migration ────────────────────────────────────────────────

def migrate_to_thin(target: Path, root: Path | None = None) -> list[str]:
    """Convert the old .pipa/extension/ layout to the thin overlay."""
    root = root or config.harness_root()
    pipa_dir = config.pipa_dir(target)
    ext = pipa_dir / "extension"
    actions: list[str] = []
    if not ext.is_dir():
        return actions

    def move(src: Path, dst: Path, label: str) -> None:
        if not src.exists() or dst.exists():
            if dst.exists():
                actions.append(f"~ kept existing {label}")
            return
        shutil.move(str(src), str(dst))
        actions.append(f"+ {label}")

    move(ext / "rules", pipa_dir / "rules", ".pipa/rules/")
    move(ext / "vault", pipa_dir / "memory", ".pipa/memory/")
    move(ext / "skills", pipa_dir / "skills", ".pipa/skills/")
    move(ext / "specs", pipa_dir / "specs", ".pipa/specs/")
    move(ext / "agents", pipa_dir / "agents-local", ".pipa/agents-local/")

    # AGENTS.md becomes the thin root-of-truth inside .pipa/
    move(ext / "AGENTS.md", pipa_dir / "AGENTS.md", ".pipa/AGENTS.md")
    link = target / "AGENTS.md"
    if link.is_symlink() and "extension" in os.readlink(link):
        link.unlink()
        link.symlink_to(f"{config.PIPA_DIR}/AGENTS.md")
        actions.append("+ AGENTS.md -> .pipa/AGENTS.md")

    # Generated runtime configs are obsolete (wiring is global now)
    shutil.rmtree(pipa_dir / "opencode", ignore_errors=True)
    shutil.rmtree(pipa_dir / "deepseek-harness", ignore_errors=True)
    stale_oc = target / ".opencode"
    if stale_oc.is_symlink():
        stale_oc.unlink()
        actions.append("- removed stale .opencode symlink")
    if ext.is_dir():
        shutil.rmtree(ext, ignore_errors=True)
        actions.append("- removed .pipa/extension/")
    return actions


# ── migrate legacy .harness_extension/ (pre-.pipa era) ─────────────────────

def migrate_project(target: Path, root: Path | None = None) -> list[str]:
    """Move a legacy (.harness_extension/) project into .pipa/, then thin it."""
    root = root or config.harness_root()
    target = target.resolve()
    actions: list[str] = []
    pipa_dir = config.pipa_dir(target)
    legacy = target / config.LEGACY_EXTENSION_DIR

    if not legacy.exists() and not pipa_dir.exists():
        raise ScaffoldError(
            f"nothing to migrate in {target} (no {config.LEGACY_EXTENSION_DIR}/)"
        )
    pipa_dir.mkdir(exist_ok=True)

    def _move(src: Path, dst: Path) -> None:
        if not src.exists() or dst.exists():
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["git", "-C", str(target), "mv", str(src), str(dst)],
                check=True, capture_output=True,
            )
        except Exception:
            shutil.move(str(src), str(dst))
        actions.append(f"+ moved {src.relative_to(target)} -> {dst.relative_to(target)}")

    if legacy.exists():
        legacy_state = legacy / "state"
        if legacy_state.exists():
            _move(legacy_state, pipa_dir / "state")
        for item in sorted(legacy.iterdir()):
            _move(item, pipa_dir / "extension" / item.name)
        try:
            legacy.rmdir()
        except OSError:
            pass

    # Old .pipa/runtime default was opencode; keep whatever exists.
    if runtimes.read_project_runtime(target) is None:
        runtimes.write_project_runtime(target, "opencode")
        actions.append("+ .pipa/runtime (opencode)")

    (pipa_dir / "state").mkdir(exist_ok=True)

    gitignore = target / ".gitignore"
    existing = gitignore.read_text() if gitignore.exists() else ""
    missing = [e for e in GITIGNORE_ENTRIES if e not in existing]
    if missing:
        with gitignore.open("a") as f:
            f.write("\n# pipa_harness (migrated)\n" + "\n".join(missing) + "\n")
        actions.append("+ .gitignore (harness artifacts)")

    actions.extend(migrate_to_thin(target, root))
    return actions


# ── extension health check ──────────────────────────────────────────────────

PLACEHOLDERS = (
    "{{PROJECT_NAME}}", "{{PROJECT_DESCRIPTION}}", "{{BUILD_COMMAND}}",
    "{{TEST_COMMAND}}", "<Project name>", "<build command>", "<test command>",
)


def check_extension(target: Path) -> list[tuple[bool, str]]:
    checks: list[tuple[bool, str]] = []
    pipa_dir = config.pipa_dir(target)
    checks.append((pipa_dir.is_dir(), f"{config.PIPA_DIR}/ directory exists"))

    agents_md = pipa_dir / "AGENTS.md"
    if not agents_md.exists():  # legacy fallback
        agents_md = pipa_dir / "extension" / "AGENTS.md"
    checks.append(((target / "AGENTS.md").exists(), "root AGENTS.md exists"))
    if agents_md.exists():
        filled = not any(p in agents_md.read_text() for p in PLACEHOLDERS)
        checks.append((filled, "AGENTS.md placeholders are filled"))
    else:
        checks.append((False, ".pipa/AGENTS.md is missing"))

    name = runtimes.read_project_runtime(target)
    checks.append((name is not None, f"runtime selected: {name or 'MISSING'}"))

    # Runtime wiring is global — verify the global artifacts exist.
    home = Path.home()
    if name == "opencode":
        cfg = home / ".config" / "opencode" / "opencode.jsonc"
        ok = cfg.exists() and "pipa" in cfg.read_text()
        checks.append((ok, "opencode global config wired"))
    elif name == "deepseek-harness":
        cfg = home / ".dsh" / "cordis.patch.yml"
        checks.append((cfg.exists(), "~/.dsh/cordis.patch.yml wired"))
    return checks
