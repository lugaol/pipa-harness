#!/bin/bash
# install.sh — adopt the pipa_harness in any project.
# Usage: /path/to/pipa_harness/install.sh [project-type]   (run from the target project root)
#
# project-type: generic (default) | android | ... see templates/project/
#
# Idempotent: creates .harness_extension/ from templates, .opencode/ from
# templates, symlinks root AGENTS.md → .harness_extension/AGENTS.md, and
# leaves an existing root AGENTS.md untouched. After install, the project is
# ready to use; AGENTS.md placeholders are auto-filled from detected facts.
set -eu

HARNESS_SRC="$(cd "$(dirname "$0")" && pwd)"
TARGET="$(pwd)"
PROJECT_TYPE="${1:-${PIPA_PROJECT_TYPE:-generic}}"

if [ ! -d "$HARNESS_SRC/skills" ]; then
  echo "ERROR: harness source not found at $HARNESS_SRC" >&2; exit 1
fi
if [ ! -d "$TARGET/.git" ] && ! git -C "$TARGET" rev-parse --git-dir >/dev/null 2>&1; then
  echo "ERROR: $TARGET is not a git repo. Run from a project root." >&2; exit 1
fi

echo "Installing pipa_harness into: $TARGET"
echo "Harness source: $HARNESS_SRC"
echo "Project type: $PROJECT_TYPE"
echo ""

# 1. .harness_extension/ — scaffold if missing
if [ ! -d "$TARGET/.harness_extension" ]; then
  echo "  + scaffolding .harness_extension/"
  mkdir -p "$TARGET/.harness_extension"
  (cd "$HARNESS_SRC/templates/extension" && find . -type f ! -name opencode.jsonc ! -path "./.opencode/*" | while read -r f; do
    mkdir -p "$TARGET/.harness_extension/$(dirname "$f")"
    [ -e "$TARGET/.harness_extension/$f" ] || cp "$f" "$TARGET/.harness_extension/$f"
  done)
else
  echo "  ~ .harness_extension/ already exists"
fi

# 1b. Overlay project-type template (if it exists)
TEMPLATE_DIR="$HARNESS_SRC/templates/project/$PROJECT_TYPE"
if [ -d "$TEMPLATE_DIR" ]; then
  echo "  + overlaying project-type template: $PROJECT_TYPE"
  (cd "$TEMPLATE_DIR" && find . -type f | while read -r f; do
    mkdir -p "$TARGET/.harness_extension/$(dirname "$f")"
    cp "$f" "$TARGET/.harness_extension/$f"
  done)
else
  [ "$PROJECT_TYPE" != generic ] && echo "  !! project-type template '$PROJECT_TYPE' not found, using generic" >&2
fi

# 2. Root AGENTS.md — symlink if missing
if [ ! -e "$TARGET/AGENTS.md" ]; then
  echo "  + symlinking AGENTS.md -> .harness_extension/AGENTS.md"
  ln -s .harness_extension/AGENTS.md "$TARGET/AGENTS.md"
elif [ ! -L "$TARGET/AGENTS.md" ]; then
  echo "  ~ AGENTS.md exists (not a symlink, leaving your file untouched)"
fi

# 3. .opencode/ — create and populate if missing
mkdir -p "$TARGET/.opencode"
for f in setup-script.sh run-script.sh; do
  src="$HARNESS_SRC/templates/extension/.opencode/$f"
  dst="$TARGET/.opencode/$f"
  if [ -f "$src" ] && [ ! -e "$dst" ]; then
    echo "  + .opencode/$f"
    cp "$src" "$dst"
    chmod +x "$dst"
  fi
done
src="$HARNESS_SRC/templates/extension/opencode.jsonc"
dst="$TARGET/.opencode/opencode.jsonc"
if [ -f "$src" ] && [ ! -e "$dst" ]; then
  echo "  + .opencode/opencode.jsonc"
  cp "$src" "$dst"
fi

# 3b. .opencode/agent -> .harness_extension/agents (OpenCode subagent discovery)
if [ ! -e "$TARGET/.opencode/agent" ]; then
  echo "  + .opencode/agent -> .harness_extension/agents"
  ln -s ../.harness_extension/agents "$TARGET/.opencode/agent"
fi

# 3c. pipa-up wrapper -> project root (so the project can re-run its own setup)
if [ ! -e "$TARGET/pipa-up" ]; then
  echo "  + pipa-up -> project root"
  cp "$HARNESS_SRC/templates/extension/pipa-up" "$TARGET/pipa-up"
  chmod +x "$TARGET/pipa-up"
fi

# 3d. Auto-fill AGENTS.md placeholders from detected project facts
if [ -x "$HARNESS_SRC/bin/pipa-init-project.py" ]; then
  echo "  + auto-filling AGENTS.md placeholders"
  "$HARNESS_SRC/bin/pipa-init-project.py" "$TARGET" || echo "  !! auto-fill failed (continuing)" >&2
fi

# 4. .graphifyignore if missing
if [ ! -e "$TARGET/.graphifyignore" ]; then
  echo "  + .graphifyignore"
  cp "$HARNESS_SRC/templates/extension/.graphifyignore" "$TARGET/.graphifyignore"
fi

# 5. .gitignore entries for harness artifacts
if ! grep -q "graphify-out/" "$TARGET/.gitignore" 2>/dev/null; then
  echo "  + .gitignore (harness artifacts)"
  cat >> "$TARGET/.gitignore" <<'EOF'

# pipa_harness
graphify-out/
.opencode/*.local.*
.harness_extension/state/*.local.md
.harness_extension/state/scratch/
EOF
fi

echo ""
echo "Done. Next steps:"
echo "  1. Run the harness:      pipa-up"
echo "  2. Health check:       python3 $HARNESS_SRC/bin/harness_status.py"
echo "  3. Start OpenCode:     cd $TARGET && opencode"
echo "  4. Review .harness_extension/AGENTS.md and add project-specific golden rules."
