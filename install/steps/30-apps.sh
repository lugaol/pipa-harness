#!/bin/sh
# 30-apps.sh — OPTIONAL GUI apps (obsidian, emdash).
# Skip with: PIPA_SKIP_APPS=1 install/steps/30-apps.sh
set -eu
if [ "${PIPA_SKIP_APPS:-0}" = "1" ]; then
	echo "[apps] skipped (PIPA_SKIP_APPS=1)"
	exit 0
fi
cd "$(dirname "$0")/../.."
exec bin/pipa install apps
