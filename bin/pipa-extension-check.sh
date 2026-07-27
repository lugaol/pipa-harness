#!/bin/bash
# pipa-extension-check.sh — verify a project extension is correctly scaffolded.
#
# Usage: pipa-extension-check.sh [project-root]
# Returns 0 if healthy, non-zero if issues found. Prints PASS/FAIL per check.
set -eu

TARGET="${1:-$(pwd)}"
AGENTS="$TARGET/.harness_extension/AGENTS.md"
OPENCODE="$TARGET/.opencode/opencode.jsonc"

cd "$TARGET"
errors=0
fail() { echo "  [FAIL] $*"; errors=$((errors + 1)); }
pass() { echo "  [PASS] $*"; }

# 1. .harness_extension/ exists
if [ -d "$TARGET/.harness_extension" ]; then
  pass ".harness_extension/ directory exists"
else
  fail ".harness_extension/ directory is missing"
fi

# 2. AGENTS.md present (root symlink or file)
if [ -e "$TARGET/AGENTS.md" ]; then
  pass "root AGENTS.md exists"
else
  fail "root AGENTS.md is missing"
fi

# 3. AGENTS.md placeholders filled
if [ -f "$AGENTS" ]; then
  placeholders="0"
  for marker in "{{PROJECT_NAME}}" "{{PROJECT_DESCRIPTION}}" "{{BUILD_COMMAND}}" "{{TEST_COMMAND}}" "<Project name>" "<build command>" "<test command>"; do
    if grep -qF "$marker" "$AGENTS"; then
      placeholders="1"
      break
    fi
  done
  if [ "$placeholders" = "0" ]; then
    pass "AGENTS.md placeholders are filled"
  else
    fail "AGENTS.md still contains template placeholders"
  fi
else
  fail ".harness_extension/AGENTS.md is missing"
fi

# 4. .opencode/opencode.jsonc exists and is valid JSONC-ish
if [ -f "$OPENCODE" ]; then
  pass ".opencode/opencode.jsonc exists"
  # Basic structural check: must start with { and end with } (ignore whitespace)
  content="$(cat "$OPENCODE")"
  trimmed="$(echo "$content" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  first_char="$(printf '%s' "$trimmed" | head -c 1)"
  last_char="$(printf '%s' "$trimmed" | tail -c 1)"
  if [ "$first_char" = "{" ] && [ "$last_char" = "}" ]; then
    pass ".opencode/opencode.jsonc looks structurally valid"
  else
    fail ".opencode/opencode.jsonc does not look like a valid JSON object"
  fi
else
  fail ".opencode/opencode.jsonc is missing"
fi

# 5. .opencode/agent symlink points to .harness_extension/agents
if [ -L "$TARGET/.opencode/agent" ]; then
  pass ".opencode/agent symlink exists"
else
  fail ".opencode/agent symlink is missing"
fi

# 6. pipa-up wrapper exists
if [ -x "$TARGET/pipa-up" ]; then
  pass "pipa-up wrapper exists and is executable"
else
  fail "pipa-up wrapper is missing or not executable"
fi

# 7. .gitignore excludes harness artifacts
if grep -q "graphify-out/" "$TARGET/.gitignore" 2>/dev/null; then
  pass ".gitignore excludes harness artifacts"
else
  fail ".gitignore does not exclude harness artifacts"
fi

if [ "$errors" -eq 0 ]; then
  echo ""
  echo "Extension health check: PASS"
  exit 0
else
  echo ""
  echo "Extension health check: FAIL ($errors issue(s))"
  exit 1
fi
