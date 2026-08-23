#!/bin/sh
# install.sh — legacy shim.
#
# The harness now lives at ~/.pipa-harness (see bootstrap.sh). This script
# forwards to the installed CLI so old docs/scripts keep working:
#   install.sh [init args...]
set -eu

if [ ! -x "$HOME/.pipa-harness/bin/pipa" ]; then
	echo "ERROR: pipa_harness not found at $HOME/.pipa-harness" >&2
	echo "" >&2
	echo "Install it first:" >&2
	echo "  bash bootstrap.sh                                  # from this repo" >&2
	echo "  curl -fsSL .../bootstrap.sh | sh                   # remote" >&2
	exit 1
fi

exec "$HOME/.pipa-harness/bin/pipa" init "$@"
