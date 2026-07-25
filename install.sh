#!/bin/bash
# install.sh — adopt the pipa_harness in any project.
# Usage: /path/to/pipa_harness/install.sh   (run from the target project root)
#
# Idempotent: creates .harness_extension/ from templates, .opencode/ from
# templates, symlinks root AGENTS.md → .harness_extension/AGENTS.md, and
# leaves an existing root AGENTS.md untouched. After install, edit
# .harness_extension/AGENTS.md for your project.
set -eu

HARNESS_SRC="$(cd "$(dirname "$0")" && pwd)"
TARGET="$(pwd)"

if [ ! -d "$HARNESS_SRC/skills" ]; then
  echo "ERROR: harness source not found at $HARNESS_SRC" >&2; exit 1
fi
if [ ! -d "$TARGET/.git" ] && ! git -C "$TARGET" rev-parse --git-dir >/dev/null 2>&1; then
  echo "ERROR: $TARGET is not a git repo. Run from a project root." >&2; exit 1
fi

echo "Installing pipa_harness into: $TARGET"
echo "Harness source: $HARNESS_SRC"
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
echo "  1. Start LiteLLM:  litellm --config $HARNESS_SRC/config/litellm.yaml --port 4000"
echo "  2. Health check:  python3 $HARNESS_SRC/bin/harness_status.py"
echo "  3. Run OpenCode:  opencode"
echo "  4. Edit .harness_extension/AGENTS.md with your project's facts + commands."
