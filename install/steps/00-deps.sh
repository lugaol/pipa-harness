#!/bin/sh
# 00-deps.sh — verify base tooling before any component installs.
set -eu
for tool in git rsync python3; do
	command -v "$tool" >/dev/null 2>&1 || {
		echo "ERROR: required tool '$tool' not found on PATH" >&2
		echo "Install it first (e.g. via your package manager or developer tools)." >&2
		exit 1
	}
done
echo "[deps] ok: git rsync python3"
# tmux is required for OmO Team Mode + review grids — warn, don't fail.
if command -v tmux >/dev/null 2>&1; then
	echo "[deps] ok: $(tmux -V)"
else
	echo "WARN: tmux not found — OmO Team Mode and review grids need it." >&2
	echo "  macOS: brew install tmux | Linux: sudo apt install tmux" >&2
fi
