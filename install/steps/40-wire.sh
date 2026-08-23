#!/bin/sh
# 40-wire.sh — final wiring: tools + services, no GUI apps, no model pulls.
set -eu
cd "$(dirname "$0")/../.."
exec bin/pipa up --no-apps --no-pull
