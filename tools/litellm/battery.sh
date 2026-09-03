#!/bin/bash
# pipa_harness — model battery test via LiteLLM gateway.
# Times each model alias on 3 representative tasks and scores pass/fail.
# Usage: ./battery.sh [model_alias1 model_alias2 ...]
# Defaults to: lowest mid high
set -u

URL="${LITELLM_URL:-http://localhost:4000}"
KEY="${LITELLM_KEY:-sk-pipa-local}"

P_BUILD='Classify this build error into exactly one category (A=Compile, B=Linker, C=Config, D=Asset) and name the file to open. Reply "CATEGORY: X | FILE: path | HINT: one line".
Error:
> src/net/client.c:41: undefined reference to `client_connect_timeout'
> collect2: error: ld returned 1 exit status'
P_LOG='Diagnose these log lines: rate-limit hit, upstream timeout, or OK? One short paragraph + one tuning direction.
gw: req=201 status=429 retry_after=1.2s
gw: req=202 status=429 retry_after=2.4s
gw: req=203 status=200 latency=88ms'
P_JSON='Extract nodes and edges from this text as strict JSON only: {"nodes":[{"id":str,"type":str}],"edges":[{"from":str,"to":str,"relation":str}]}
"The controller analyzes input and sets a flag. The worker reads the flag and runs the job. The bridge connects the UI to the worker."'

FAILED=0

run_task () { # model, label, prompt, expect_regex
  local model="$1" label="$2" prompt="$3" expect="$4"
  local t0 out dt
  t0=$(python3 -c 'import time; print(time.time())')
  out=$(curl -s "${URL}/v1/chat/completions" \
    -H "Authorization: Bearer ${KEY}" \
    -H "Content-Type: application/json" \
    -d "$(python3 -c 'import json,sys
print(json.dumps({"model":sys.argv[1],"messages":[{"role":"user","content":sys.argv[2]}],"stream":False}))' "$model" "$prompt")" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"])' 2>/dev/null || echo "(error)")
  dt=$(python3 -c "import time,sys; print(f'{time.time()-float(sys.argv[1]):.1f}')" "$t0")
  local verdict="FAIL"
  if echo "$out" | grep -qiE "$expect"; then
      verdict="PASS"
  else
      FAILED=$((FAILED + 1))
  fi
  printf "%-12s %-14s %-6s %6ss | %s\n" "$model" "$label" "$verdict" "$dt" "$(echo "$out" | tr '\n' ' ' | cut -c1-90)"
}

MODELS=("$@"); [ ${#MODELS[@]} -eq 0 ] && MODELS=(lowest mid high)

echo "model        task           result   time | response preview"
echo "------------ -------------- ------ -------+------------------"
for m in "${MODELS[@]}"; do
  run_task "$m" "build-triage" "$P_BUILD" "CATEGORY:\\s*A|^A=C\\+\\+"
  run_task "$m" "log-analysis" "$P_LOG" 'rate.limit|429|backoff|throttle|upstream|timeout'
  run_task "$m" "json-schema"   "$P_JSON" '"nodes"'
  echo "------------ -------------- ------ -------+------------------"
done

if [ "$FAILED" -gt 0 ]; then
    echo ""
    echo "MODEL BATTERY: FAIL ($FAILED task(s) failed)"
    exit 1
fi
echo ""
echo "MODEL BATTERY: PASS"
