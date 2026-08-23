#!/bin/sh
# bootstrap.sh — one-command installer for pipa_harness.
#
# curl|sh friendly:
#   curl -fsSL https://raw.githubusercontent.com/OWNER/pipa_harness/main/bootstrap.sh | sh
#
# What it does:
#   1. clone pipa_harness into ~/.pipa-harness (or update an existing checkout)
#   2. add ~/.pipa-harness/bin to your shell PATH (idempotent)
#   3. print next steps
#
# Environment overrides:
#   REPO_URL     git repo to clone   (default below; replace OWNER)
#   PIPA_BRANCH  branch/tag          (default: main)
#   PIPA_HOME    install location    (default: ~/.pipa-harness)
set -eu

REPO_URL="${REPO_URL:-https://github.com/OWNER/pipa_harness.git}"
PIPA_BRANCH="${PIPA_BRANCH:-main}"
DEST="${PIPA_HOME:-$HOME/.pipa-harness}"

say() { printf '[bootstrap] %s\n' "$*"; }

mkdir -p "$(dirname "$DEST")"

# 1. clone or update ──────────────────────────────────────────────────────────
if [ -d "$DEST/.git" ]; then
	say "updating existing checkout in $DEST"
	git -C "$DEST" pull --ff-only || {
		say "WARN: git pull failed — keeping existing files as-is"
	}
elif [ -e "$DEST" ]; then
	echo "ERROR: $DEST exists but is not a git checkout." >&2
	echo "Move it away or remove it, then re-run bootstrap.sh." >&2
	exit 1
else
	say "cloning $REPO_URL -> $DEST"
	git clone --depth=1 --branch "$PIPA_BRANCH" "$REPO_URL" "$DEST"
fi

[ -x "$DEST/bin/pipa" ] || {
	echo "ERROR: $DEST/bin/pipa missing after clone — check REPO_URL/branch." >&2
	exit 1
}

# 2. PATH line (idempotent) — mirrors services.persist_path() in pipa/services.py
line="export PATH=\"$DEST/bin:\$HOME/.opencode/bin:\$HOME/.local/bin:\$PATH\""
for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
	case "$rc" in
		*.zshrc)  [ -f "$rc" ] || [ "${SHELL##*/}" = zsh ] || continue ;;
		*.bashrc) [ -f "$rc" ] || [ "${SHELL##*/}" = bash ] || continue ;;
	esac
	if [ -f "$rc" ] && grep -qF "$DEST/bin" "$rc" 2>/dev/null; then
		say "PATH already in $(basename "$rc")"
	else
		{ printf '\n# pipa_harness (pipa CLI + runtimes + uv tools)\n%s\n' "$line"; } >>"$rc"
		say "PATH added to $(basename "$rc") (open a new terminal to pick it up)"
	fi
done

export PATH="$DEST/bin:$PATH"

# 3. next steps ───────────────────────────────────────────────────────────────
say "installed pipa_harness at $DEST"
say ""
say "Next steps:"
say "  pipa up            # tools + services + wire current project"
say "  pipa status        # health check"
say ""
say "Optional component installs:"
say "  cd $DEST && bin/pipa install <uv|ollama|litellm|graphify|dsh|opencode|apps>"
say "  make -C $DEST/install wire      # same as 'pipa up', no GUI apps/model pulls"
