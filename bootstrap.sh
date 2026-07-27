#!/bin/bash
# bootstrap.sh — one-command install for pipa_harness.
#
# Run from anywhere (curl | bash) to install the harness into a fixed location,
# add it to PATH, and run the one-command setup.
#
#   curl -fsSL https://raw.githubusercontent.com/lugaol/pipa-harness/main/bootstrap.sh | bash
#
# Environment overrides:
#   PIPA_ROOT      install location (default: ~/.local/share/pipa-harness)
#   PIPA_REPO      git repo URL (default: https://github.com/lugaol/pipa-harness.git)
#   PIPA_BRANCH    branch/tag to checkout (default: main)
set -eu

PIPA_ROOT="${PIPA_ROOT:-$HOME/.local/share/pipa-harness}"
PIPA_REPO="${PIPA_REPO:-https://github.com/lugaol/pipa-harness.git}"
PIPA_BRANCH="${PIPA_BRANCH:-main}"

mkdir -p "$(dirname "$PIPA_ROOT")"

# ── clone or update ──────────────────────────────────────────────────────────
if [ -d "$PIPA_ROOT/.git" ]; then
  echo "[bootstrap] updating pipa_harness in $PIPA_ROOT"
  git -C "$PIPA_ROOT" fetch --depth=1 origin "$PIPA_BRANCH" || true
  git -C "$PIPA_ROOT" checkout "$PIPA_BRANCH" || true
  git -C "$PIPA_ROOT" pull --ff-only origin "$PIPA_BRANCH" || true
else
  echo "[bootstrap] cloning pipa_harness into $PIPA_ROOT"
  rm -rf "$PIPA_ROOT"
  git clone --depth=1 --branch "$PIPA_BRANCH" "$PIPA_REPO" "$PIPA_ROOT"
fi

# ── PATH ───────────────────────────────────────────────────────────────────────
line="export PATH=\"$PIPA_ROOT/bin:\$HOME/.opencode/bin:\$HOME/.local/bin:\$PATH\""
updated_rc=0
for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
  case "$rc" in
    *.zshrc)  [ -f "$rc" ] || [ "$(basename "${SHELL:-}")" = zsh ] || continue ;;
    *.bashrc) [ -f "$rc" ] || [ "$(basename "${SHELL:-}")" = bash ] || continue ;;
  esac
  if [ -f "$rc" ] && grep -qF "$PIPA_ROOT/bin" "$rc" 2>/dev/null; then
    echo "[bootstrap] PATH already in $(basename "$rc")"
  else
    { echo ""; echo "# pipa_harness (added by bootstrap.sh)"; echo "$line"; } >> "$rc"
    echo "[bootstrap] PATH added to $(basename "$rc")"
    updated_rc=1
  fi
done

export PATH="$PIPA_ROOT/bin:$HOME/.opencode/bin:$HOME/.local/bin:$PATH"

# ── run the one-command setup ──────────────────────────────────────────────────
echo "[bootstrap] running pipa-up..."
exec "$PIPA_ROOT/bin/pipa-up.sh" "$@"
