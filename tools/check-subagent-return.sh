#!/usr/bin/env bash
# check-subagent-return.sh — post-subagent return gate (computational layer).
#
# A cheap deterministic check to run BEFORE trusting a subagent's "done":
#   1. scope: every touched file must sit under an allowed prefix
#      (default: the current git root) — catches edits outside the owned surface;
#   2. secrets: the diff must not contain secret-looking material
#      (private keys, AWS-style ids, password/token assignments).
#
# Usage: tools/check-subagent-return.sh [--allow PREFIX ...] [--staged|--unstaged|HEAD]
# Exit 0 = clean, 1 = violation (machine-readable CHECK-FAIL lines on stdout).
# This never replaces the inferential review (@qa reads the diff and the
# build evidence); it just makes "trust, then verify" cheap.
# Ported from ia_harness tools/check-subagent-return.sh (allow-list generalized).
set -u
ALLOW=""
ALLOW_COUNT=0
MODE="HEAD"
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --allow) ALLOW="$ALLOW
$2"; ALLOW_COUNT=$((ALLOW_COUNT + 1)); shift 2;;
    --staged|--unstaged|HEAD) MODE="$1"; shift;;
    *) echo "usage: $0 [--allow PREFIX ...] [--staged|--unstaged|HEAD]" >&2; exit 2;;
  esac
done
case "$MODE" in
  --staged) DIFF_CMD=(git diff --cached --name-only -- . ':(exclude)*.pid'); FULL=(git diff --cached -- .);;
  --unstaged) DIFF_CMD=(git diff --name-only -- .); FULL=(git diff HEAD -- .);;
  *) DIFF_CMD=(git diff --name-only HEAD -- .); FULL=(git diff HEAD -- .);;
esac
fail=0
while IFS= read -r f; do
  [ -z "$f" ] && continue
  ok=0
  if [ "$ALLOW_COUNT" -gt 0 ]; then
    while IFS= read -r prefix; do
      [ -z "$prefix" ] && continue
      case "$f" in "$prefix"*) ok=1; break;; esac
    done <<< "$ALLOW"
  else
    # No explicit --allow: confine to the current git root.
    case "$f" in /*) ;; *) ok=1;; esac
    if git rev-parse --show-toplevel >/dev/null 2>&1; then
      top="$(git rev-parse --show-toplevel)"
      case "$(pwd)/$f" in "$top"/*) ok=1;; *) ok=0;; esac
    fi
  fi
  if [ "$ok" -eq 0 ]; then
    echo "CHECK-FAIL scope: $f outside allowed prefixes"
    fail=1
  fi
done < <("${DIFF_CMD[@]}" 2>/dev/null)
patterns=(
  '-----BEGIN [A-Z ]*PRIVATE KEY-----'
  'AKIA[0-9A-Z]{16}'
  'xox[bpas]-[0-9A-Za-z-]+'
  '(?i)(password|passwd|secret|api[_-]?key|auth[_-]?token)\s*[:=]\s*["'"'"']?[^"'"'"'[:space:]]+'
)
full="$("${FULL[@]}" 2>/dev/null)"
for pat in "${patterns[@]}"; do
  if printf '%s\n' "$full" | grep -qiE -e "$pat"; then
    echo "CHECK-FAIL secrets: diff matches secret pattern: $pat"
    fail=1
  fi
done
exit "$fail"
