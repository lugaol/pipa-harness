#!/usr/bin/env python3
# pipa-init-project.py — detect project facts and fill AGENTS.md placeholders.
#
# Usage: pipa-init-project.py [project-root]
#
# Detects project name, build command, and test command from common project
# files, then fills the scaffolded .harness_extension/AGENTS.md in place.
# Safe to re-run: replacements are literal and idempotent for the detected
# values (but may overwrite manual edits if they exactly match the old values).
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def find_agents(target: Path) -> Path:
    candidates = [
        target / ".harness_extension" / "AGENTS.md",
        target / "AGENTS.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    print(f"ERROR: no AGENTS.md found in {target}", file=sys.stderr)
    sys.exit(1)


def detect_name(target: Path) -> str:
    # package.json
    package_json = target / "package.json"
    if package_json.exists():
        try:
            name = json.loads(package_json.read_text()).get("name", "")
            if name:
                return name
        except Exception:
            pass

    # pyproject.toml
    pyproject = target / "pyproject.toml"
    if pyproject.exists():
        m = re.search(r"\[project\]\s*\n[^\n]*name\s*=\s*\"([^\"]+)\"", pyproject.read_text())
        if m:
            return m.group(1)

    # Cargo.toml
    cargo = target / "Cargo.toml"
    if cargo.exists():
        m = re.search(r"\[package\]\s*\n[^\n]*name\s*=\s*\"([^\"]+)\"", cargo.read_text())
        if m:
            return m.group(1)

    # git remote
    try:
        url = subprocess.run(
            ["git", "-C", str(target), "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return re.sub(r".*/", "", url).replace(".git", "")
    except Exception:
        pass

    # directory name
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
    makefile = target / "Makefile"
    if makefile.exists() and re.search(r"^test:", makefile.read_text(), re.MULTILINE):
        return "make test"
    if (target / "pyproject.toml").exists() or (target / "requirements.txt").exists():
        return "pytest"
    return "none detected — add your test command"


def main() -> int:
    target = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
    agents = find_agents(target)

    name = detect_name(target)
    build = detect_build(target)
    test = detect_test(target)

    text = agents.read_text()
    replacements = {
        "{{PROJECT_NAME}}": name,
        "{{PROJECT_DESCRIPTION}}": f"One-line description of {name}.",
        "{{BUILD_COMMAND}}": build,
        "{{TEST_COMMAND}}": test,
        "<Project name>": name,
        "<build command>": build,
        "<test command>": test,
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    agents.write_text(text)

    print(f"Initialized {agents}:")
    print(f"  name:  {name}")
    print(f"  build: {build}")
    print(f"  test:  {test}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
