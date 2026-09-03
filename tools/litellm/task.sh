#!/bin/sh
# litellm-task.sh <tier> <prompt...> — run a task through the LiteLLM gateway.
# Tiers (override model alias via env; tiers are user-assigned in the dashboard):
#   lowest -> LITELLM_MODEL_LOWEST  (read-only codebase Q&A, triage)
#   low    -> LITELLM_MODEL_LOW     (triage, titles, summaries)
#   mid    -> LITELLM_MODEL_MID     (implementation)
#   high   -> LITELLM_MODEL_HIGH    (research, complex reasoning)
#   xhigh  -> LITELLM_MODEL_XHIGH   (hardest reasoning, long-horizon work)
#
# Requires: litellm proxy running at $LITELLM_URL (default http://localhost:4000)
set -eu

ROLE="${1:-}"
if [ -n "$ROLE" ]; then
    shift
    PROMPT="$*"
fi
[ -n "$ROLE" ] && [ -n "$PROMPT" ] || { echo "usage: $0 <lowest|low|mid|high|xhigh> <prompt>" >&2; exit 2; }

URL="${LITELLM_URL:-http://localhost:4000}"
KEY="${LITELLM_KEY:-sk-pipa-local}"

case "$ROLE" in
  lowest)   MODEL="${LITELLM_MODEL_LOWEST:-lowest}" ;;
  low)      MODEL="${LITELLM_MODEL_LOW:-low}" ;;
  mid)      MODEL="${LITELLM_MODEL_MID:-mid}" ;;
  high)     MODEL="${LITELLM_MODEL_HIGH:-high}" ;;
  xhigh)    MODEL="${LITELLM_MODEL_XHIGH:-xhigh}" ;;
  *) echo "unknown tier: $ROLE (use: lowest|low|mid|high|xhigh)" >&2; exit 2 ;;
esac

curl -sf "${URL}/v1/chat/completions" \
  -H "Authorization: Bearer ${KEY}" \
  -H "Content-Type: application/json" \
  -d "$(python3 -c 'import json, sys
print(json.dumps({
    "model": sys.argv[1],
    "messages": [{"role": "user", "content": sys.argv[2]}],
    "stream": False,
}))' "$MODEL" "$PROMPT")" \
| python3 -c 'import json, sys
d = json.load(sys.stdin)
print(d["choices"][0]["message"]["content"])'
