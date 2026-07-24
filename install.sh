#!/bin/bash
# install.sh — adopt the pipa_harness in any project.
# Usage: /path/to/pipa_harness/install.sh   (run from the target project root)
#
# Idempotent: copies harness files with cp -n (never overwrites existing),
# symlinks .opencode/ into the harness, and leaves an existing root AGENTS.md
# untouched. After install, edit harness/AGENTS.md for your project.
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

# 1. Copy the harness tree (idempotent — cp -n skips existing)
if [ "$HARNESS_SRC" != "$TARGET/harness" ] && [ ! -e "$TARGET/harness" ]; then
  echo "  + symlinking harness/ -> $HARNESS_SRC"
  ln -s "$HARNESS_SRC" "$TARGET/harness"
elif [ -e "$TARGET/harness" ] && [ "$HARNESS_SRC" != "$(readlink -f "$TARGET/harness" 2>/dev/null || echo "")" ]; then
  echo "  ~ harness/ already exists (leaving as-is)"
else
  echo "  ~ harness/ already linked"
fi

# 2. Root AGENTS.md — symlink if missing
if [ ! -e "$TARGET/AGENTS.md" ]; then
  echo "  + symlinking AGENTS.md -> harness/AGENTS.md"
  ln -s harness/AGENTS.md "$TARGET/AGENTS.md"
elif [ ! -L "$TARGET/AGENTS.md" ]; then
  echo "  ~ AGENTS.md exists (not a symlink, leaving your file untouched)"
fi

# 3. .opencode/ — create and populate if missing
mkdir -p "$TARGET/.opencode"
for f in opencode.jsonc setup-script.sh run-script.sh; do
  src="$HARNESS_SRC/templates/opencode-emdash/$f"
  dst="$TARGET/.opencode/$f"
  if [ -f "$src" ] && [ ! -e "$dst" ]; then
    echo "  + .opencode/$f"
    cp "$src" "$dst"
    [ "$f" != "opencode.jsonc" ] && chmod +x "$dst"
  fi
done

# 4. .graphifyignore if missing
if [ ! -e "$TARGET/.graphifyignore" ]; then
  echo "  + .graphifyignore"
  cat > "$TARGET/.graphifyignore" <<'EOF'
# graphify scope control
**/node_modules/**
**/build/**
**/dist/**
**/.git/**
**/dependencies/**
graphify-out/**
EOF
fi

# 5. .gitignore entries for harness artifacts
if ! grep -q "graphify-out/" "$TARGET/.gitignore" 2>/dev/null; then
  echo "  + .gitignore (harness artifacts)"
  cat >> "$TARGET/.gitignore" <<'EOF'

# pipa_harness
graphify-out/
.opencode/*.local.*
harness/state/*.local.md
EOF
fi

echo ""
echo "Done. Next steps:"
echo "  1. Start LiteLLM:  litellm --config harness/config/litellm.yaml --port 4000"
echo "  2. Health check:  python3 harness/bin/harness_status.py"
echo "  3. Run OpenCode:  opencode"
echo "  4. Edit harness/AGENTS.md with your project's facts + commands."
