#!/bin/sh
# emdash worktree setup — runs when a new worktree is created.
# Bootstraps submodules and installs deps so the agent can build immediately.
set -eu

echo "[setup] git submodules..."
git submodule update --init --recursive 2>/dev/null || echo "[setup] (no submodules)"

# Detect + install deps by project type
if [ -f package.json ]; then
  echo "[setup] node deps..."
  npm install 2>/dev/null || echo "[setup] npm install failed (continuing)"
elif [ -f requirements.txt ]; then
  echo "[setup] python deps..."
  pip3 install -r requirements.txt 2>/dev/null || echo "[setup] pip install failed (continuing)"
elif [ -f Cargo.toml ]; then
  echo "[setup] rust deps (fetched on build)..."
elif [ -f build.gradle ]; then
  echo "[setup] gradle deps (fetched on build)..."
fi

echo "[setup] done."
