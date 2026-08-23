#!/bin/sh
# 20-runtimes.sh — agent runtimes: deepseek-harness + opencode.
set -eu
cd "$(dirname "$0")/../.."
exec bin/pipa install dsh opencode
