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
