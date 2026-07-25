#!/bin/bash
# pipa_harness — model battery test via LiteLLM gateway.
# Times each model alias on 3 representative tasks and scores pass/fail.
# Usage: ./model_battery.sh [model_alias1 model_alias2 ...]
# Defaults to: fast primary deep
set -u

URL="${LITELLM_URL:-http://localhost:4000}"
KEY="${LITELLM_KEY:-sk-pipa-local}"

P_BUILD='Classify this build error into exactly one category (A=Compile, B=Linker, C=Config, D=Asset) and name the file to open. Reply "CATEGORY: X | FILE: path | HINT: one line".
Error:
> Task :app:mergeDebugNativeLibs FAILED
  undefined reference to `AudioStreamBuilder::setCallback`'
P_LOG='Diagnose these log lines: false trigger, missed trigger, chattering, or OK? One short paragraph + one tuning direction.
ML: rawB=0.62 | pressure=0.410 blow=1 | rms=0.0310
ML: rawB=0.59 | pressure=0.425 blow=1 | rms=0.0295
ML: rawB=0.08 | pressure=0.010 blow=0 | rms=0.0021
ML: rawB=0.61 | pressure=0.380 blow=1 | rms=0.0280
ML: rawB=0.07 | pressure=0.012 blow=0 | rms=0.0019
ML: rawB=0.58 | pressure=0.371 blow=1 | rms=0.0271'
P_JSON='Extract nodes and edges from this text as strict JSON only: {"nodes":[{"id":str,"type":str}],"edges":[{"from":str,"to":str,"relation":str}]}
"The controller analyzes input and sets a flag. The synth reads the flag and opens the gate. The bridge connects the UI to the synth."'

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
  echo "$out" | grep -qiE "$expect" && verdict="pass"
  printf "%-12s %-14s %-6s %6ss | %s\n" "$model" "$label" "$verdict" "$dt" "$(echo "$out" | tr '\n' ' ' | cut -c1-90)"
}

MODELS=("$@"); [ ${#MODELS[@]} -eq 0 ] && MODELS=(fast primary deep)

echo "model        task           result   time | response preview"
echo "------------ -------------- ------ -------+------------------"
for m in "${MODELS[@]}"; do
  run_task "$m" "build-triage" "$P_BUILD" "CATEGORY:\\s*A|^A=C\\+\\+"
  run_task "$m" "log-analysis" "$P_LOG" 'chatter|flap|rapid|hysteresis|release|threshold'
  run_task "$m" "json-schema"   "$P_JSON" '"nodes"'
  echo "------------ -------------- ------ -------+------------------"
done
