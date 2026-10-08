#!/bin/sh
# 20-runtimes.sh — agent runtime wiring (opencode).
set -eu
cd "$(dirname "$0")/../.."
exec bin/pipa install opencode
