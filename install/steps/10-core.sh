#!/bin/sh
# 10-core.sh — core engine components: uv, LiteLLM gateway, code graph.
set -eu
cd "$(dirname "$0")/../.."
exec bin/pipa install uv py-deps litellm graphify
