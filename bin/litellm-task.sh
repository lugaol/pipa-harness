#!/bin/sh
# litellm-task.sh <role> <prompt...> — run a task through the LiteLLM gateway.
# Roles (override model alias via env):
#   fast    -> LITELLM_MODEL_FAST     (triage, titles, summaries)
#   primary -> LITELLM_MODEL_PRIMARY  (implementation)
#   deep    -> LITELLM_MODEL_DEEP     (research, complex reasoning)
#   explore -> LITELLM_MODEL_EXPLORE  (read-only codebase Q&A)
#
# Requires: litellm proxy running at $LITELLM_URL (default http://localhost:4000)
set -eu

ROLE="${1:-}"; PROMPT="${*:2}"
[ -n "$ROLE" ] && [ -n "$PROMPT" ] || { echo "usage: $0 <fast|primary|deep|explore|kilo-free> <prompt>" >&2; exit 2; }

URL="${LITELLM_URL:-http://localhost:4000}"
KEY="${LITELLM_KEY:-sk-pipa-local}"

case "$ROLE" in
  fast)    MODEL="${LITELLM_MODEL_FAST:-fast}" ;;
  primary) MODEL="${LITELLM_MODEL_PRIMARY:-primary}" ;;
  deep)    MODEL="${LITELLM_MODEL_DEEP:-deep}" ;;
  explore) MODEL="${LITELLM_MODEL_EXPLORE:-explore}" ;;
  kilo-free) MODEL="${LITELLM_MODEL_KILO_FREE:-kilo-free}" ;;
  *) echo "unknown role: $ROLE (use: fast|primary|deep|explore|kilo-free)" >&2; exit 2 ;;
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
