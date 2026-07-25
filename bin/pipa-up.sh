#!/bin/bash
# pipa-up.sh — one command, everything running.
#
# Run it ANYWHERE: installs missing tools, starts services, sets up the
# global OpenCode config, and — when run from a project root — scaffolds
# .harness_extension/ (rules, skills, agents, AGENTS.md, memory) so the
# project is wired in one shot.
#
#   tools:    uv · ollama · litellm · graphify (+mcp) · opencode · obsidian · emdash
#   services: ollama serve (:11434) + litellm gateway (:4000)
#   global:   PATH in shell rc + ~/.config/opencode (base config + agents)
#   project:  .harness_extension/ + root AGENTS.md + .opencode/ (idempotent)
#
# Usage:
#   bin/pipa-up.sh              install missing pieces, start services, wire project
#   bin/pipa-up.sh --status     report only, change nothing
#   bin/pipa-up.sh --stop       stop the services started by this script
#   bin/pipa-up.sh --no-pull    skip ollama model downloads
#   bin/pipa-up.sh --no-apps    skip GUI apps (obsidian, emdash)
#
# Platforms: macOS (brew for GUI apps) and Linux (apt/dnf/pacman/flatpak/
# AppImage, best effort). Idempotent: safe to re-run anytime.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE="$ROOT/state"
CONFIG="$ROOT/config/litellm.yaml"
LITELLM_PORT=4000
OLLAMA_PORT=11434
mkdir -p "$STATE"

MODE=up
PULL_MODELS=1
GUI_APPS=1
for arg in "$@"; do
  case "$arg" in
    --status)  MODE=status ;;
    --stop)    MODE=stop ;;
    --no-pull) PULL_MODELS=0 ;;
    --no-apps) GUI_APPS=0 ;;
    -h|--help) grep '^#' "$0" | head -20; exit 0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

# extra PATH locations where installers drop binaries
export PATH="$ROOT/bin:$HOME/.local/bin:$HOME/.opencode/bin:$PATH"

OS="$(uname -s)"            # Darwin | Linux
ARCH="$(uname -m)"          # arm64 | x86_64
DASHBOARD_STARTED=0

say()  { printf '%s\n' "$*"; }
ok()   { say "  [ok] $*"; }
add()  { say "  [++] $*"; }
warn() { say "  [!!] $*" >&2; }
have() { command -v "$1" >/dev/null 2>&1; }

wait_http() { # wait_http <url> <seconds> — 0 on response
  url="$1"; n=0
  while [ "$n" -lt "$2" ]; do
    curl -s -m 2 -o /dev/null "$url" && return 0
    n=$((n+2)); sleep 2
  done
  return 1
}

# ── stop mode ─────────────────────────────────────────────────────────────
if [ "$MODE" = "stop" ]; then
  say "Stopping pipa services..."
  [ -f "$STATE/litellm.pid" ] && kill "$(cat "$STATE/litellm.pid")" 2>/dev/null && rm -f "$STATE/litellm.pid" && ok "litellm stopped"
  [ -f "$STATE/ollama.pid" ] && kill "$(cat "$STATE/ollama.pid")" 2>/dev/null && rm -f "$STATE/ollama.pid" && ok "ollama stopped (only the instance started by pipa-up)"
  [ -f "$STATE/dashboard.pid" ] && kill "$(cat "$STATE/dashboard.pid")" 2>/dev/null && rm -f "$STATE/dashboard.pid" && ok "dashboard stopped"
  exit 0
fi

# ── installers (each: check → install or skip) ─────────────────────────────

ensure_uv() {
  have uv && { ok "uv"; return; }
  [ "$MODE" = status ] && { warn "uv: MISSING"; return; }
  add "installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  have uv && ok "uv installed" || { warn "uv install failed"; exit 1; }
}

ensure_ollama() {
  have ollama && { ok "ollama"; return; }
  [ "$MODE" = status ] && { warn "ollama: MISSING"; return; }
  add "installing ollama..."
  if [ "$OS" = Darwin ] && have brew; then
    brew install ollama || brew install --cask ollama
  elif [ "$OS" = Linux ]; then
    curl -fsSL https://ollama.com/install.sh | sh
  else
    warn "no brew — install ollama manually: https://ollama.com/download"; return
  fi
  have ollama && ok "ollama installed" || warn "ollama install failed"
}

ensure_litellm() {
  have litellm && { ok "litellm"; return; }
  [ "$MODE" = status ] && { warn "litellm: MISSING"; return; }
  add "installing litellm[proxy]..."
  uv tool install 'litellm[proxy]' || uv tool install --force 'litellm[proxy]'
  have litellm && ok "litellm installed" || warn "litellm install failed"
}

ensure_graphify() {
  # graphifyy needs the mcp package in its tool env or graphify-mcp crashes
  if have graphify && have graphify-mcp; then
    venv_py="$(uv tool dir 2>/dev/null)/graphifyy/bin/python"
    if [ ! -x "$venv_py" ] || "$venv_py" -c 'import mcp' >/dev/null 2>&1; then
      ok "graphify (+mcp)"; return
    fi
    [ "$MODE" = status ] && { warn "graphify: present but 'mcp' module missing"; return; }
    add "adding mcp to graphify tool env..."
    uv tool install graphifyy --with mcp --reinstall
    ok "graphify (+mcp)"; return
  fi
  [ "$MODE" = status ] && { warn "graphify: MISSING"; return; }
  add "installing graphifyy (+mcp)..."
  uv tool install graphifyy --with mcp
  have graphify && ok "graphify installed" || warn "graphify install failed"
}

ensure_opencode() {
  have opencode && { ok "opencode"; return; }
  [ "$MODE" = status ] && { warn "opencode: MISSING"; return; }
  add "installing opencode..."
  curl -fsSL https://opencode.ai/install | bash
  export PATH="$HOME/.opencode/bin:$PATH"
  have opencode && ok "opencode installed" || warn "opencode install failed"
}

ensure_obsidian() {
  [ "$GUI_APPS" = 0 ] && return 0
  if [ "$OS" = Darwin ] && [ -d /Applications/Obsidian.app ]; then ok "obsidian"; return; fi
  if [ "$OS" = Linux ] && { have obsidian || flatpak info md.obsidian.Obsidian >/dev/null 2>&1; }; then ok "obsidian"; return; fi
  [ "$MODE" = status ] && { warn "obsidian: MISSING (GUI app)"; return; }
  add "installing obsidian..."
  if [ "$OS" = Darwin ] && have brew; then
    brew install --cask obsidian
  elif [ "$OS" = Linux ]; then
    if have flatpak; then flatpak install -y flathub md.obsidian.Obsidian
    elif have snap; then sudo snap install obsidian --classic
    else warn "install obsidian manually: https://obsidian.md/download"; return; fi
  else
    warn "no brew — install obsidian manually: https://obsidian.md/download"; return
  fi
  ok "obsidian installed"
}

ensure_emdash() {
  [ "$GUI_APPS" = 0 ] && return 0
  if [ "$OS" = Darwin ] && ls -d /Applications/[Ee]mdash.app >/dev/null 2>&1; then ok "emdash"; return; fi
  if [ "$OS" = Linux ] && have emdash; then ok "emdash"; return; fi
  [ "$MODE" = status ] && { warn "emdash: MISSING (GUI app, optional)"; return; }
  add "installing emdash from GitHub releases..."
  api="https://api.github.com/repos/generalaction/emdash/releases/latest"
  if [ "$OS" = Darwin ]; then
    if [ "$ARCH" = arm64 ]; then pat='arm64\.dmg$'; else pat='x64\.dmg$'; fi
    url="$(curl -fsSL "$api" | grep -o '"browser_download_url": *"[^"]*"' | cut -d'"' -f4 | grep -iE "$pat" | head -1 || true)"
    if [ -n "$url" ]; then
      tmp="$(mktemp -d)"; curl -fsSL "$url" -o "$tmp/emdash.dmg"
      hdiutil attach -nobrowse -quiet "$tmp/emdash.dmg"
      app="$(ls -d /Volumes/*/*.app 2>/dev/null | head -1)"
      [ -n "$app" ] && cp -R "$app" /Applications/
      hdiutil detach -quiet "${app%/*.app}" 2>/dev/null || true
      rm -rf "$tmp"; ok "emdash installed"
    else
      warn "could not resolve emdash dmg — get it at https://github.com/generalaction/emdash/releases"
    fi
  else
    url="$(curl -fsSL "$api" | grep -o '"browser_download_url": *"[^"]*"' | cut -d'"' -f4 | grep -iE 'x86_64\.appimage$' | head -1 || true)"
    if [ -n "$url" ]; then
      mkdir -p "$HOME/.local/bin"
      curl -fsSL "$url" -o "$HOME/.local/bin/emdash" && chmod +x "$HOME/.local/bin/emdash"
      ok "emdash installed (~/.local/bin/emdash)"
    else
      warn "could not resolve emdash AppImage — https://github.com/generalaction/emdash/releases"
    fi
  fi
}

ensure_dashboard() {
  if [ "$MODE" = status ]; then
    if [ -f "$STATE/dashboard.pid" ] && kill -0 "$(cat "$STATE/dashboard.pid")" 2>/dev/null; then
      ok "dashboard (:8080)"
    else
      warn "dashboard: not running (:8080)"
    fi
    return
  fi
  if [ -f "$STATE/dashboard.pid" ] && kill -0 "$(cat "$STATE/dashboard.pid")" 2>/dev/null; then
    ok "dashboard already running (:8080)"
    return
  fi
  add "starting dashboard (:8080)..."
  mkdir -p "$STATE"
  nohup python3 "$ROOT/tools/dashboard/app.py" > "$STATE/dashboard.log" 2>&1 &
  echo $! > "$STATE/dashboard.pid"
  sleep 1
  if kill -0 "$(cat "$STATE/dashboard.pid")" 2>/dev/null; then
    ok "dashboard up (http://localhost:8080)"
    DASHBOARD_STARTED=1
  else
    warn "dashboard failed to start — see $STATE/dashboard.log"
  fi
}

open_browser() {
  [ "$MODE" = status ] && return 0
  [ "$DASHBOARD_STARTED" != 1 ] && return 0
  url="http://localhost:8080"
  if [ "$OS" = Darwin ]; then
    open -a "Google Chrome" "$url" 2>/dev/null || open "$url"
    return 0
  fi
  if [ "$OS" = Linux ]; then
    if have google-chrome; then
      google-chrome "$url" >/dev/null 2>&1 || xdg-open "$url" >/dev/null 2>&1
    elif have chromium-browser; then
      chromium-browser "$url" >/dev/null 2>&1 || xdg-open "$url" >/dev/null 2>&1
    else
      xdg-open "$url" >/dev/null 2>&1
    fi
    return 0
  fi
}

# ── services ───────────────────────────────────────────────────────────────

start_ollama() {
  if curl -s -m 2 -o /dev/null "http://localhost:$OLLAMA_PORT"; then ok "ollama serve already running"; return; fi
  [ "$MODE" = status ] && { warn "ollama serve: not running"; return; }
  add "starting ollama serve..."
  nohup ollama serve > "$STATE/ollama.log" 2>&1 &
  echo $! > "$STATE/ollama.pid"
  wait_http "http://localhost:$OLLAMA_PORT" 20 && ok "ollama serve up (:$OLLAMA_PORT)" || warn "ollama serve did not come up — see state/ollama.log"
}

pull_models() {
  [ "$PULL_MODELS" = 1 ] || return 0
  have ollama || return 0
  curl -s -m 2 -o /dev/null "http://localhost:$OLLAMA_PORT" || return 0
  models="$(grep 'model: openai/' "$CONFIG" | grep -v '^[[:space:]]*#' | sed 's/.*openai\///; s/ *#.*//; s/ *$//' | sort -u)"
  for m in $models; do
    if ollama list | awk '{print $1}' | grep -qx "$m"; then
      ok "model present: $m"
    else
      [ "$MODE" = status ] && { warn "model missing: $m"; continue; }
      add "pulling model: $m (large download)..."
      ollama pull "$m" && ok "pulled $m" || warn "pull failed: $m"
    fi
  done
}

start_litellm() {
  if curl -s -m 2 -o /dev/null "http://localhost:$LITELLM_PORT/v1/models" -H "Authorization: Bearer sk-pipa-local"; then
    ok "litellm gateway already running (:$LITELLM_PORT)"; return
  fi
  [ "$MODE" = status ] && { warn "litellm gateway: not running"; return; }
  add "starting litellm gateway (:$LITELLM_PORT)..."
  nohup litellm --config "$CONFIG" --port "$LITELLM_PORT" > "$STATE/litellm.log" 2>&1 &
  echo $! > "$STATE/litellm.pid"
  wait_http "http://localhost:$LITELLM_PORT/v1/models" 30 && ok "litellm gateway up (:$LITELLM_PORT)" || warn "gateway did not come up — see state/litellm.log"
}

# ── global wiring (PATH + OpenCode base config) ───────────────────────────

persist_path() {
  line='export PATH="'$ROOT'/bin:$HOME/.opencode/bin:$HOME/.local/bin:$PATH"'
  for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
    # only touch rc files that exist, plus the current shell's rc
    case "$rc" in
      *.zshrc)  [ -f "$rc" ] || [ "$(basename "${SHELL:-}")" = zsh ] || continue ;;
      *.bashrc) [ -f "$rc" ] || [ "$(basename "${SHELL:-}")" = bash ] || continue ;;
    esac
    if [ -f "$rc" ] && grep -qF "$ROOT/bin" "$rc"; then
      ok "PATH already in $(basename "$rc")"
    else
      [ "$MODE" = status ] && { warn "PATH: $ROOT/bin not in $(basename "$rc")"; continue; }
      { echo ""; echo "# pipa_harness (pipa-up + opencode + uv tools)"; echo "$line"; } >> "$rc"
      add "PATH added to $(basename "$rc") (open a new terminal to pick it up)"
    fi
  done
}

setup_global_opencode() {
  gdir="$HOME/.config/opencode"
  gcfg="$gdir/opencode.jsonc"
  if [ -f "$gcfg" ] && grep -q "pipa" "$gcfg" 2>/dev/null; then
    ok "global opencode config (~/.config/opencode)"
  else
    [ "$MODE" = status ] && { warn "global opencode config: MISSING"; }
    if [ "$MODE" != status ]; then
      mkdir -p "$gdir"
      sed "s|@PIPA_ROOT@|$ROOT|g" "$ROOT/templates/global-opencode.jsonc" > "$gcfg"
      add "wrote $gcfg (litellm provider + base rules)"
    fi
  fi
  if [ -e "$gdir/agent" ]; then
    ok "global opencode agents"
  else
    [ "$MODE" = status ] && { warn "global opencode agents: MISSING"; return; }
    ln -s "$ROOT/agents" "$gdir/agent"
    add "linked $gdir/agent -> $ROOT/agents"
  fi
}

# ── project scaffold (.harness_extension) ─────────────────────────────────

scaffold_project() {
  target="$(git rev-parse --show-toplevel 2>/dev/null)" || return 0
  [ "$target" = "$ROOT" ] && return 0          # inside pipa itself: no scaffold
  ext="$target/.harness_extension"

  if [ -d "$ext" ]; then
    ok ".harness_extension/ exists ($target)"
  else
    [ "$MODE" = status ] && { warn "project not scaffolded: $target (run pipa-up here)"; return; }
    add "scaffolding .harness_extension/ in $target"
    mkdir -p "$ext"
    (cd "$ROOT/templates/extension" && find . -type f ! -name opencode.jsonc | while read -r f; do
      mkdir -p "$ext/$(dirname "$f")"
      [ -e "$ext/$f" ] || cp "$f" "$ext/$f"
    done)
  fi

  if [ ! -e "$target/AGENTS.md" ]; then
    [ "$MODE" != status ] && { ln -s .harness_extension/AGENTS.md "$target/AGENTS.md"; add "AGENTS.md -> .harness_extension/AGENTS.md"; }
  fi

  mkdir -p "$target/.opencode"
  if [ ! -e "$target/.opencode/opencode.jsonc" ] && [ "$MODE" != status ]; then
    cp "$ROOT/templates/extension/opencode.jsonc" "$target/.opencode/opencode.jsonc"
    add ".opencode/opencode.jsonc"
  fi
  if [ ! -e "$target/.opencode/agent" ] && [ "$MODE" != status ]; then
    ln -s ../.harness_extension/agents "$target/.opencode/agent"
    add ".opencode/agent -> .harness_extension/agents"
  fi
}

# ── run ────────────────────────────────────────────────────────────────────

say "pipa-up ($MODE) — $OS/$ARCH"
say ""

ensure_uv
ensure_ollama
ensure_litellm
ensure_graphify
ensure_opencode
ensure_obsidian
ensure_emdash
ensure_dashboard
open_browser

say ""
start_ollama
pull_models
start_litellm

say ""
persist_path
setup_global_opencode
scaffold_project

say ""
if [ "$MODE" = status ]; then
  python3 "$ROOT/bin/harness_status.py" || true
else
  say "Verifying..."
  python3 "$ROOT/bin/harness_status.py" || true
  say ""
  say "Done."
  [ "$DASHBOARD_STARTED" = 1 ] && say "  Dashboard: http://localhost:8080 (opened in browser)"
  say "  Next: open a NEW terminal (PATH updated), then: cd your-project && opencode"
  say "  Logs: $STATE/litellm.log · $STATE/ollama.log    Stop: bin/pipa-up.sh --stop"
fi
