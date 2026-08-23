#!/bin/sh
# emdash worktree run — runs when the agent starts in a worktree.
# Verifies the build is green before the agent begins work.
set -eu

if [ -f package.json ]; then
  echo "[run] npm run build..." && npm run build 2>&1 | tail -n 20
elif [ -f Cargo.toml ]; then
  echo "[run] cargo build..." && cargo build 2>&1 | tail -n 20
elif [ -f build.gradle ]; then
  echo "[run] gradle assembleDebug..." && ./gradlew assembleDebug 2>&1 | tail -n 20
elif [ -f Makefile ]; then
  echo "[run] make..." && make 2>&1 | tail -n 20
else
  echo "[run] no build system detected — skipping."
fi
