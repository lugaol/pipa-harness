#!/bin/bash
set -euo pipefail

MODE="${1:-test}"
INSTALL_MODE="${INSTALL_MODE:-local}"

if [ "$INSTALL_MODE" = "local" ]; then
    PIPA_ROOT=/opt/pipa_harness
elif [ "$INSTALL_MODE" = "bootstrap" ]; then
    PIPA_ROOT=/root/.local/share/pipa-harness
else
    echo "Unknown INSTALL_MODE: $INSTALL_MODE" >&2
    exit 1
fi

export PATH="$PIPA_ROOT/bin:/root/.opencode/bin:/root/.local/bin:$PATH"

wait_http() {
    local url=$1 seconds=$2
    shift 2
    local i=0
    while [ $i -lt "$seconds" ]; do
        if curl -sf -m 2 -o /dev/null "$@" "$url"; then
            return 0
        fi
        sleep 1
        i=$((i+1))
    done
    return 1
}

start_services() {
    echo "Starting Ollama..."
    ollama serve > /tmp/ollama-runtime.log 2>&1 &
    OLLAMA_PID=$!
    wait_http "http://localhost:11434" 30 || { echo "Ollama failed to start"; cat /tmp/ollama-runtime.log; exit 1; }
    echo "Ollama ready"

    echo "Pulling qwen2.5-coder:7b model..."
    if ollama list | awk '{print $1}' | grep -qx "qwen2.5-coder:7b"; then
        echo "Model already present"
    else
        ollama pull qwen2.5-coder:7b || { echo "Model pull failed"; exit 1; }
        echo "Model pulled"
    fi

    echo "Starting LiteLLM gateway..."
    nohup litellm --config "$PIPA_ROOT/config/litellm.free.yaml" --port 4000 > /tmp/litellm-runtime.log 2>&1 &
    LITELLM_PID=$!
    wait_http "http://localhost:4000/v1/models" 30 -H "Authorization: Bearer sk-pipa-local" || { echo "LiteLLM failed to start"; cat /tmp/litellm-runtime.log; exit 1; }
    echo "LiteLLM ready"

    if [ "${START_DASHBOARD:-0}" = "1" ]; then
        echo "Starting dashboard..."
        nohup python3 "$PIPA_ROOT/tools/dashboard/app.py" > /tmp/dashboard-runtime.log 2>&1 &
        DASHBOARD_PID=$!
        wait_http "http://localhost:8080" 15 || { echo "Dashboard failed to start"; cat /tmp/dashboard-runtime.log; exit 1; }
        echo "Dashboard ready"
    fi
}

stop_services() {
    [ -n "${LITELLM_PID:-}" ] && kill "$LITELLM_PID" 2>/dev/null || true
    [ -n "${OLLAMA_PID:-}" ] && kill "$OLLAMA_PID" 2>/dev/null || true
    [ -n "${DASHBOARD_PID:-}" ] && kill "$DASHBOARD_PID" 2>/dev/null || true
    wait 2>/dev/null || true
}

run_test() {
    local exit_code=0
    
    if [ "$INSTALL_MODE" = "local" ]; then
        echo "Running pipa-up (local mode)..."
        cd /opt/pipa_harness && ./bin/pipa-up.sh --no-apps --no-pull || { echo "pipa-up FAILED"; exit 1; }
    fi

    start_services

    local test_project=/tmp/pipa-test-project
    rm -rf "$test_project"
    mkdir -p "$test_project"
    cd "$test_project"
    git init -b main

    echo "Installing harness extension into $test_project..."
    python3 "$PIPA_ROOT/install.sh" || { echo "install.sh FAILED"; stop_services; exit 1; }

    echo "Running extension health check..."
    if "$PIPA_ROOT/bin/pipa-extension-check.sh" "$test_project"; then
        echo "Extension health check: PASS"
    else
        echo "Extension health check: FAIL"
        exit_code=1
    fi

    echo "Generating graphify graph..."
    if command -v graphify >/dev/null 2>&1; then
        graphify extract . >/dev/null 2>&1 || echo "graphify extract failed (non-fatal)"
    else
        echo "graphify not installed, skipping graph generation"
    fi

    echo "Running harness status..."
    python3 "$PIPA_ROOT/bin/harness_status.py" --json > /tmp/status.json || true
    python3 -c "$(cat <<'PY'
import json, sys
with open("/tmp/status.json") as f:
    data = json.load(f)
checks = {c["name"]: c["status"] for c in data["checks"]}
critical_fail = []
if checks.get("litellm") != "pass":
    critical_fail.append("litellm")
if checks.get("graphify-cli") != "pass":
    critical_fail.append("graphify-cli")
if checks.get("git-repo") != "pass":
    critical_fail.append("git-repo")
optional_fail = [
    c["name"]
    for c in data["checks"]
    if c["status"] == "fail" and c["name"] not in ["litellm", "graphify-cli", "git-repo", "graphify-graph"]
]
if critical_fail:
    print(f"Harness status: FAIL (critical: {critical_fail})")
    sys.exit(1)
elif optional_fail:
    print(f"Harness status: PASS (optional missing: {optional_fail})")
else:
    print("Harness status: PASS")
    sys.exit(0)
PY
)" || exit_code=$?

    echo "Verifying LiteLLM models..."
    if curl -sf -m 5 "http://localhost:4000/v1/models" -H "Authorization: Bearer sk-pipa-local" >/tmp/models.json; then
        local count
        count=$(jq -r '.data | length' /tmp/models.json)
        if [ "$count" -gt 0 ]; then
            echo "LiteLLM models: PASS ($count models)"
        else
            echo "LiteLLM models: FAIL (no models returned)"
            exit_code=1
        fi
    else
        echo "LiteLLM models: FAIL (gateway not reachable)"
        exit_code=1
    fi

    stop_services
    return $exit_code
}

serve_mode() {
    if [ "$INSTALL_MODE" = "local" ]; then
        echo "Running pipa-up (local mode)..."
        cd /opt/pipa_harness && ./bin/pipa-up.sh --no-apps --no-pull || { echo "pipa-up FAILED"; exit 1; }
    fi
    
    start_services
    echo ""
    echo "PIPA services running:"
    echo "  LiteLLM:   http://localhost:4000"
    echo "  Ollama:    http://localhost:11434"
    if [ "${START_DASHBOARD:-0}" = "1" ]; then
        echo "  Dashboard: http://localhost:8080"
    fi
    echo ""
    echo "Press Ctrl+C to stop."
    wait
}

trap stop_services EXIT

case "$MODE" in
    test) run_test ;;
    battery) /usr/local/bin/test-battery.sh ;;
    serve) serve_mode ;;
    *) echo "Usage: $0 [test|serve|battery]"; exit 1 ;;
esac
