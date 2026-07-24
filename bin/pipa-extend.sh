#!/bin/bash
# pipa-extend.sh — merge a project extension bundle on top of the base harness.
#
# An extension bundle is a folder with any of:
#   AGENTS.md        → appended to the base AGENTS.md (project-specific section)
#   rules/*.md       → copied into rules/ (project-specific rules)
#   skills/*/SKILL.md → copied into skills/ (project-specific skills)
#   agents/*.md      → copied into agents/ (project-specific subagents)
#   config/*.yaml    → merged/appended to config/ (e.g. extra LiteLLM models)
#
# Usage:
#   pipa-extend.sh <extension-dir>     # merge into this harness (additive)
#   pipa-extend.sh --update <name|dir> # re-copy files from the bundle (overwrite)
#   pipa-extend.sh --remove <name>     # unmerge: delete merged files + AGENTS.md section
#   pipa-extend.sh --list              # list installed extensions
#
# Every merged file is recorded in .pipa-extensions/<name>.manifest so updates
# and removals are exact. Merges are additive by default: existing files with
# the same name are kept; if content differs the incoming file is installed as
# <extname>__<file> instead of silently skipping (skills are dir-namespaced).
set -eu

HARNESS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST_DIR="$HARNESS_ROOT/.pipa-extensions"

usage() {
  echo "Usage:"
  echo "  $0 <extension-dir>      merge an extension bundle into the harness"
  echo "  $0 --update <name|dir>  re-copy merged files from the bundle (overwrite)"
  echo "  $0 --remove <name>      remove a previously merged extension"
  echo "  $0 --list               list installed extensions"
  echo ""
  echo "Extension bundles live in squads/projects/<name>/ (may be symlinks to an"
  echo "in-repo harness/ dir). Each bundle may contain: AGENTS.md, rules/,"
  echo "skills/, agents/, config/"
}

# Record a merged file in the extension manifest (dedup).
record() { # record <name> <relative-path>
  mkdir -p "$MANIFEST_DIR"
  grep -qxF "$2" "$MANIFEST_DIR/$1.manifest" 2>/dev/null || echo "$2" >> "$MANIFEST_DIR/$1.manifest"
}

# Copy one file into the harness, collision-safe.
# copy_file <name> <src> <destdir> <prefix-on-conflict:yes|no>
copy_file() {
  local name="$1" src="$2" destdir="$3" prefix="$4"
  local bn dst
  bn="$(basename "$src")"
  dst="$destdir/$bn"
  mkdir -p "$destdir"
  if [ -e "$dst" ]; then
    if cmp -s "$src" "$dst"; then
      echo "  ~ $dst (identical, skipping)"
      record "$name" "${dst#"$HARNESS_ROOT"/}"
      return
    elif [ "$prefix" = "yes" ]; then
      dst="$destdir/${name}__${bn}"
      if [ -e "$dst" ] && cmp -s "$src" "$dst"; then
        echo "  ~ $dst (identical, skipping)"
        record "$name" "${dst#"$HARNESS_ROOT"/}"
        return
      fi
      echo "  ! name clash: installing as ${dst#"$HARNESS_ROOT"/}"
    else
      echo "  ~ $dst (exists with different content, skipping)"
      record "$name" "${dst#"$HARNESS_ROOT"/}"
      return
    fi
  else
    echo "  + ${dst#"$HARNESS_ROOT"/}"
  fi
  cp "$src" "$dst"
  record "$name" "${dst#"$HARNESS_ROOT"/}"
}

# Strip the AGENTS.md section for an extension.
strip_agents_section() { # strip_agents_section <name>
  local mark="<!-- BEGIN EXTENSION: $1 -->"
  local endmark="<!-- END EXTENSION: $1 -->"
  [ -f "$HARNESS_ROOT/AGENTS.md" ] || return 0
  grep -qF "$mark" "$HARNESS_ROOT/AGENTS.md" || return 0
  local tmp
  tmp="$(mktemp)"
  awk -v begin="$mark" -v end="$endmark" '
    $0 == begin { skip = 1; next }
    $0 == end   { skip = 0; next }
    !skip       { print }
  ' "$HARNESS_ROOT/AGENTS.md" > "$tmp"
  # collapse trailing blank lines left behind
  awk 'NF { blank = 0 } { if (NF) { for (i = 0; i < blank; i++) print ""; blank = 0; print } else blank++ }' "$tmp" > "$HARNESS_ROOT/AGENTS.md"
  rm -f "$tmp"
}

# Resolve an extension name-or-dir to (name, dir).
resolve_ext() { # resolve_ext <arg> → sets EXT_NAME, EXT_DIR (EXT_DIR may be empty)
  local arg="$1"
  if [ -d "$arg" ]; then
    EXT_DIR="$(cd "$arg" && pwd)"
    EXT_NAME="$(basename "$EXT_DIR")"
  elif [ -d "$HARNESS_ROOT/squads/projects/$arg" ]; then
    EXT_DIR="$(cd "$HARNESS_ROOT/squads/projects/$arg" && pwd)"
    EXT_NAME="$arg"
  else
    EXT_DIR=""
    EXT_NAME="$arg"
  fi
}

merge() { # merge <ext-dir> <mode:add|update>
  local ext name mode="$2"
  ext="$(cd "$1" && pwd)"
  name="$(basename "$ext")"
  echo "Extending pipa_harness with: $name ($ext) [mode: $mode]"
  echo ""

  # On update, drop the old merged copies first so renames don't linger.
  if [ "$mode" = "update" ] && [ -f "$MANIFEST_DIR/$name.manifest" ]; then
    while IFS= read -r rel; do
      [ -n "$rel" ] && rm -f "$HARNESS_ROOT/$rel"
    done < "$MANIFEST_DIR/$name.manifest"
    rm -f "$MANIFEST_DIR/$name.manifest"
    strip_agents_section "$name"
  fi

  # 1. AGENTS.md — append project section
  if [ -f "$ext/AGENTS.md" ]; then
    local mark="<!-- BEGIN EXTENSION: $name -->"
    if ! grep -qF "$mark" "$HARNESS_ROOT/AGENTS.md" 2>/dev/null; then
      echo "  + appending project section to AGENTS.md"
      {
        echo ""
        echo "$mark"
        cat "$ext/AGENTS.md"
        echo "<!-- END EXTENSION: $name -->"
      } >> "$HARNESS_ROOT/AGENTS.md"
    else
      echo "  ~ AGENTS.md already has extension '$name' (skipping)"
    fi
  fi

  # 2. rules/ and 4. agents/ — collision-safe flat copies
  for kind in rules agents; do
    if [ -d "$ext/$kind" ]; then
      for f in "$ext/$kind"/*.md; do
        [ -f "$f" ] || continue
        copy_file "$name" "$f" "$HARNESS_ROOT/$kind" yes
      done
    fi
  done

  # 3. skills/ — directories are self-namespacing
  if [ -d "$ext/skills" ]; then
    for d in "$ext/skills"/*/; do
      [ -d "$d" ] || continue
      local bn dst
      bn="$(basename "$d")"
      dst="$HARNESS_ROOT/skills/$bn"
      if [ -e "$dst" ]; then
        if diff -rq "$d" "$dst" >/dev/null 2>&1; then
          echo "  ~ skills/$bn/ (identical, skipping)"
        else
          echo "  ! skills/$bn/ exists with different content (skipping — remove it first to replace)"
        fi
      else
        cp -r "$d" "$dst"
        echo "  + skills/$bn/"
      fi
      record "$name" "skills/$bn"
    done
  fi

  # 5. config/
  if [ -d "$ext/config" ]; then
    for f in "$ext/config"/*; do
      [ -f "$f" ] || continue
      copy_file "$name" "$f" "$HARNESS_ROOT/config" yes
    done
  fi

  echo ""
  echo "Done. Extension '$name' merged into harness (manifest: .pipa-extensions/$name.manifest)."
  echo "Restart OpenCode to pick up new agents/skills."
}

remove_ext() { # remove_ext <name>
  local name="$1"
  if [ ! -f "$MANIFEST_DIR/$name.manifest" ]; then
    echo "ERROR: no manifest for extension '$name' (not installed?)" >&2
    exit 1
  fi
  echo "Removing extension: $name"
  while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    if [ -e "$HARNESS_ROOT/$rel" ]; then
      rm -rf "${HARNESS_ROOT:?}/$rel"
      echo "  - $rel"
    fi
  done < "$MANIFEST_DIR/$name.manifest"
  strip_agents_section "$name" && echo "  - AGENTS.md section"
  rm -f "$MANIFEST_DIR/$name.manifest"
  echo "Done. Extension '$name' removed."
}

case "${1:-}" in
  ""|-h|--help)
    usage
    exit 1
    ;;
  --list)
    if [ -d "$MANIFEST_DIR" ] && ls "$MANIFEST_DIR"/*.manifest >/dev/null 2>&1; then
      for m in "$MANIFEST_DIR"/*.manifest; do basename "$m" .manifest; done
    else
      echo "(no extensions installed)"
    fi
    ;;
  --remove)
    [ -n "${2:-}" ] || { usage; exit 1; }
    remove_ext "$2"
    ;;
  --update)
    [ -n "${2:-}" ] || { usage; exit 1; }
    resolve_ext "$2"
    [ -n "$EXT_DIR" ] || { echo "ERROR: extension dir not found for: $2" >&2; exit 1; }
    merge "$EXT_DIR" update
    ;;
  -*)
    echo "ERROR: unknown flag: $1" >&2
    usage
    exit 1
    ;;
  *)
    [ -d "$1" ] || { echo "ERROR: extension dir not found: $1" >&2; exit 1; }
    merge "$1" add
    ;;
esac
