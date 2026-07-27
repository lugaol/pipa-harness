#!/bin/bash
# Pipa Harness — full Docker battery test.
#
# Creates a test project at /pipa_test_dashboard, wires the harness extension,
# starts all services, and exercises every major feature. Produces a pass/fail
# report and returns non-zero if any critical check fails.
#
# Usage inside the container:
#   /usr/local/bin/test-battery.sh
#
# Optional env overrides:
#   SKIP_MODEL_BATTERY=1   Skip slow LLM calls through the gateway
#   SKIP_E2E_OPENCODE=1  Skip opencode headless smoke test
#   START_DASHBOARD=1    Start and test the dashboard API (default: 1)

set -euo pipefail

PIPA_ROOT="${PIPA_ROOT:-/opt/pipa_harness}"
TEST_PROJECT="${TEST_PROJECT:-/pipa_test_dashboard}"
STATE_DIR="${STATE_DIR:-/tmp/pipa-battery-state}"
REPORT="${STATE_DIR}/report.md"
JSON_REPORT="${STATE_DIR}/report.json"
START_DASHBOARD="${START_DASHBOARD:-1}"

mkdir -p "$STATE_DIR"
rm -f "$REPORT" "$JSON_REPORT"

PASS=0
FAIL=0
SKIP=0
RESULTS=()

log() { echo "[battery] $*" | tee -a "$REPORT"; }
section() {
    echo "" | tee -a "$REPORT"
    echo "## $*" | tee -a "$REPORT"
}

record() {
    local status="$1" name="$2" detail="${3:-}"
    RESULTS+=("{\"name\":\"$name\",\"status\":\"$status\",\"detail\":\"$(echo "$detail" | sed 's/"/\\"/g' | tr '\n' ' ')\"}")
    case "$status" in
        PASS) PASS=$((PASS+1)) ;;
        FAIL) FAIL=$((FAIL+1)) ;;
        SKIP) SKIP=$((SKIP+1)) ;;
    esac
    printf "  [%s] %s %s\n" "$status" "$name" "$detail" | tee -a "$REPORT"
}

wait_http() {
    local url="$1" seconds="${2:-30}"
    local i=0
    while [ "$i" -lt "$seconds" ]; do
        if curl -sf -m 2 -o /dev/null "$url" 2>/dev/null; then
            return 0
        fi
        sleep 1
        i=$((i+1))
    done
    return 1
}

# ── 0. environment / downloads ───────────────────────────────────────────────

section "Environment & Downloads"

check_command() {
    local cmd="$1" pkg="${2:-$1}"
    if command -v "$cmd" >/dev/null 2>&1; then
        record PASS "download:$pkg" "$(command -v "$cmd")"
    else
        record FAIL "download:$pkg" "not on PATH"
    fi
}

check_command uv uv
check_command ollama ollama
check_command litellm litellm
check_command graphify graphify
check_command graphify-mcp graphify-mcp
check_command opencode opencode
check_command python3 python3

# Python packages used by dashboard/tests
for pkg in fastapi uvicorn yaml; do
    if python3 -c "import $pkg" 2>/dev/null; then
        record PASS "python-pkg:$pkg"
    else
        record FAIL "python-pkg:$pkg"
    fi
done

# ── 1. project scaffolding ───────────────────────────────────────────────────

section "Project Scaffolding"

rm -rf "$TEST_PROJECT"
mkdir -p "$TEST_PROJECT"
cd "$TEST_PROJECT"
git init -b main >/dev/null 2>&1

# Seed a tiny source file so graphify has something to extract.
mkdir -p src
cat > src/main.py <<'PY'
def greet(name: str) -> str:
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(greet("pipa"))
PY

if bash "$PIPA_ROOT/install.sh" generic >"$STATE_DIR/install.log" 2>&1; then
    record PASS "install.sh"
else
    record FAIL "install.sh" "see $STATE_DIR/install.log"
fi

for f in .harness_extension .opencode AGENTS.md pipa-up; do
    if [ -e "$TEST_PROJECT/$f" ]; then
        record PASS "scaffold:$f"
    else
        record FAIL "scaffold:$f"
    fi
done

if "$PIPA_ROOT/bin/pipa-extension-check.sh" "$TEST_PROJECT" >"$STATE_DIR/extension-check.log" 2>&1; then
    record PASS "extension-health-check"
else
    record FAIL "extension-health-check" "see $STATE_DIR/extension-check.log"
fi

# ── 2. start services ────────────────────────────────────────────────────────

section "Services"

OLLAMA_PID=""
LITELLM_PID=""
DASHBOARD_PID=""
OLLAMA_WE_STARTED=0
LITELLM_WE_STARTED=0
DASHBOARD_WE_STARTED=0

cleanup_services() {
    [ "$DASHBOARD_WE_STARTED" = "1" ] && [ -n "${DASHBOARD_PID:-}" ] && kill "$DASHBOARD_PID" 2>/dev/null || true
    [ "$LITELLM_WE_STARTED" = "1" ] && [ -n "${LITELLM_PID:-}" ] && kill "$LITELLM_PID" 2>/dev/null || true
    [ "$OLLAMA_WE_STARTED" = "1" ] && [ -n "${OLLAMA_PID:-}" ] && kill "$OLLAMA_PID" 2>/dev/null || true
    wait 2>/dev/null || true
}
trap cleanup_services EXIT

# Ollama
if command -v ollama >/dev/null 2>&1; then
    if wait_http "http://localhost:11434" 2; then
        record PASS "service:ollama" "already running"
    else
        ollama serve >"$STATE_DIR/ollama.log" 2>&1 &
        OLLAMA_PID=$!
        OLLAMA_WE_STARTED=1
        if wait_http "http://localhost:11434" 30; then
            record PASS "service:ollama" "started"
        else
            record FAIL "service:ollama" "did not start"
        fi
    fi

    pull_ollama_model() {
        local m="$1"
        if ollama list | awk '{print $1}' | grep -qx "$m"; then
            record PASS "model:$m" "present"
        else
            if ollama pull "$m" >"$STATE_DIR/ollama-pull-$m.log" 2>&1; then
                record PASS "model:$m" "pulled"
            else
                record FAIL "model:$m" "see $STATE_DIR/ollama-pull-$m.log"
            fi
        fi
    }
    pull_ollama_model "qwen2.5-coder:7b"
    pull_ollama_model "qwen2.5-coder:14b"
else
    record FAIL "service:ollama" "ollama not installed"
fi

# LiteLLM gateway (free config — works without cloud API keys)
if command -v litellm >/dev/null 2>&1; then
    if curl -sf -m 2 -o /dev/null "http://localhost:4000/v1/models" -H "Authorization: Bearer sk-pipa-local" 2>/dev/null; then
        record PASS "service:litellm" "already running"
    else
        nohup litellm --config "$PIPA_ROOT/config/litellm.free.yaml" --port 4000 >"$STATE_DIR/litellm.log" 2>&1 &
        LITELLM_PID=$!
        LITELLM_WE_STARTED=1
        i=0
        while [ "$i" -lt 30 ]; do
            if curl -sf -m 2 -o /dev/null "http://localhost:4000/v1/models" -H "Authorization: Bearer sk-pipa-local" 2>/dev/null; then
                record PASS "service:litellm" "started"
                break
            fi
            sleep 1
            i=$((i+1))
        done
        if [ "$i" -eq 30 ]; then
            record FAIL "service:litellm" "did not start"
        fi
    fi

    alias_count=$(curl -sf -m 5 "http://localhost:4000/v1/models" -H "Authorization: Bearer sk-pipa-local" | jq -r '.data | length')
    if [ "$alias_count" -gt 0 ]; then
        record PASS "litellm:aliases" "$alias_count models"
    else
        record FAIL "litellm:aliases" "no models registered"
    fi
else
    record FAIL "service:litellm" "litellm not installed"
fi

# Dashboard
if [ "$START_DASHBOARD" = "1" ]; then
    if [ -f "$PIPA_ROOT/tools/dashboard/app.py" ]; then
        if wait_http "http://localhost:8080" 2; then
            record PASS "service:dashboard" "already running"
        else
            nohup python3 "$PIPA_ROOT/tools/dashboard/app.py" >"$STATE_DIR/dashboard.log" 2>&1 &
            DASHBOARD_PID=$!
            DASHBOARD_WE_STARTED=1
            if wait_http "http://localhost:8080" 30; then
                record PASS "service:dashboard" "started"
            else
                record FAIL "service:dashboard" "did not start"
            fi
        fi
    else
        record FAIL "service:dashboard" "app.py missing"
    fi
fi

# ── 3. graphify ──────────────────────────────────────────────────────────────

section "Graphify"

if command -v graphify >/dev/null 2>&1; then
    # Use `update --force` for code-only extraction; it does not need an LLM key.
    if graphify update --force "$TEST_PROJECT" >"$STATE_DIR/graphify.log" 2>&1; then
        if [ -f "$TEST_PROJECT/graphify-out/graph.json" ]; then
            nodes=$(jq -r '.nodes | length' "$TEST_PROJECT/graphify-out/graph.json" 2>/dev/null || echo 0)
            record PASS "graphify:code-graph" "$nodes nodes"
        else
            record FAIL "graphify:code-graph" "no graph.json produced"
        fi
    else
        record FAIL "graphify:code-graph" "see $STATE_DIR/graphify.log"
    fi
else
    record SKIP "graphify:extract" "graphify not installed"
fi

# ── 4. agent evals ───────────────────────────────────────────────────────────

section "Agent Evals"

if [ -f "$PIPA_ROOT/tools/agent_evals/run.py" ]; then
    if (cd "$PIPA_ROOT" && python3 tools/agent_evals/run.py >"$STATE_DIR/agent-evals.log" 2>&1); then
        record PASS "agent-evals"
    else
        record FAIL "agent-evals" "see $STATE_DIR/agent-evals.log"
    fi
else
    record SKIP "agent-evals" "tools/agent_evals/run.py missing"
fi

# ── 5. dashboard API ─────────────────────────────────────────────────────────

section "Dashboard API"

api_get() {
    local path="$1" name="$2"
    if curl -sf -m 5 "http://localhost:8080$path" >"$STATE_DIR/api-$name.json" 2>/dev/null; then
        record PASS "api:$name"
    else
        record FAIL "api:$name" "$path unreachable"
    fi
}

if [ "$START_DASHBOARD" = "1" ] && wait_http "http://localhost:8080" 5; then
    api_get /api/status status
    api_get /api/models models
    api_get /api/agents agents
    api_get /api/extensions extensions
    api_get /api/tools tools
    api_get /api/env-keys env-keys
    api_get /api/evals evals

    # Validate that the extensions endpoint returns parseable JSON.
    if jq empty "$STATE_DIR/api-extensions.json" >/dev/null 2>&1; then
        record PASS "api:extensions-json-valid"
    else
        record FAIL "api:extensions-json-valid" "$STATE_DIR/api-extensions.json is not valid JSON"
    fi
else
    record SKIP "dashboard-api" "dashboard not running"
fi

# ── 6. memory store ───────────────────────────────────────────────────────────

section "Memory Store"

if [ -f "$PIPA_ROOT/tools/memory_store/index_vault.py" ]; then
    if (cd "$PIPA_ROOT" && python3 tools/memory_store/index_vault.py >"$STATE_DIR/memory-index.log" 2>&1); then
        record PASS "memory-store:index"
    else
        record FAIL "memory-store:index" "see $STATE_DIR/memory-index.log"
    fi

    if [ -f "$PIPA_ROOT/tools/memory_store/query.py" ]; then
        if python3 "$PIPA_ROOT/tools/memory_store/query.py" "harness" >"$STATE_DIR/memory-query.log" 2>&1; then
            record PASS "memory-store:query"
        else
            record FAIL "memory-store:query" "see $STATE_DIR/memory-query.log"
        fi
    fi
else
    record SKIP "memory-store" "tools/memory_store missing"
fi

# ── 7. litellm-task.sh ───────────────────────────────────────────────────────

section "LiteLLM Task Script"

if [ -x "$PIPA_ROOT/bin/litellm-task.sh" ]; then
    if "$PIPA_ROOT/bin/litellm-task.sh" explore "Reply with exactly one word: PONG" >"$STATE_DIR/litellm-task.log" 2>&1; then
        if grep -qi "pong" "$STATE_DIR/litellm-task.log"; then
            record PASS "litellm-task:explore"
        else
            record FAIL "litellm-task:explore" "response did not contain PONG"
        fi
    else
        record FAIL "litellm-task:explore" "see $STATE_DIR/litellm-task.log"
    fi
else
    record SKIP "litellm-task:explore" "bin/litellm-task.sh missing"
fi

# ── 8. model battery ──────────────────────────────────────────────────────────

section "Model Battery"

if [ -x "$PIPA_ROOT/bin/model_battery.sh" ] && [ "${SKIP_MODEL_BATTERY:-0}" != "1" ]; then
    if "$PIPA_ROOT/bin/model_battery.sh" fast primary deep explore >"$STATE_DIR/model-battery.log" 2>&1; then
        record PASS "model-battery"
    else
        record FAIL "model-battery" "see $STATE_DIR/model-battery.log"
    fi
else
    record SKIP "model-battery" "SKIP_MODEL_BATTERY=1 or script missing"
fi

# ── 9. opencode headless ─────────────────────────────────────────────────────

section "OpenCode Headless"

if [ "${SKIP_E2E_OPENCODE:-0}" != "1" ] && command -v opencode >/dev/null 2>&1; then
    if (cd "$TEST_PROJECT" && timeout 120 opencode run -m "litellm/explore" \
        "Reply with exactly one word: PONG" >"$STATE_DIR/opencode.log" 2>&1); then
        if grep -qi "pong" "$STATE_DIR/opencode.log"; then
            record PASS "opencode:headless"
        else
            record FAIL "opencode:headless" "response did not contain PONG"
        fi
    else
        record FAIL "opencode:headless" "see $STATE_DIR/opencode.log"
    fi
else
    record SKIP "opencode:headless" "SKIP_E2E_OPENCODE=1 or opencode not installed"
fi

# ── 10. pipa-up --status (does not mutate, reports readiness) ─────────────────

section "pipa-up Status"

if [ -x "$PIPA_ROOT/bin/pipa-up.sh" ]; then
    if "$PIPA_ROOT/bin/pipa-up.sh" --no-apps --no-pull --status >"$STATE_DIR/pipa-up-status.log" 2>&1; then
        record PASS "pipa-up:status"
    else
        record FAIL "pipa-up:status" "see $STATE_DIR/pipa-up-status.log"
    fi
else
    record SKIP "pipa-up:status" "bin/pipa-up.sh missing"
fi

# ── report ───────────────────────────────────────────────────────────────────

section "Summary"

TOTAL=$((PASS + FAIL + SKIP))
log "PASS: $PASS | FAIL: $FAIL | SKIP: $SKIP | TOTAL: $TOTAL"

{
    echo ""
    echo "Detailed logs: $STATE_DIR"
    echo "Test project:  $TEST_PROJECT"
} | tee -a "$REPORT"

# JSON report
{
    echo "{"
    echo "  \"pass\": $PASS,"
    echo "  \"fail\": $FAIL,"
    echo "  \"skip\": $SKIP,"
    echo "  \"results\": ["
    first=1
    for r in "${RESULTS[@]}"; do
        [ "$first" -eq 1 ] || echo ","
        echo -n "    $r"
        first=0
    done
    echo ""
    echo "  ]"
    echo "}"
} > "$JSON_REPORT"

if [ "$FAIL" -eq 0 ]; then
    log "BATTERY TEST: PASS"
    exit 0
else
    log "BATTERY TEST: FAIL ($FAIL failures)"
    exit 1
fi
