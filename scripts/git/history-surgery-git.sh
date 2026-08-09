#!/usr/bin/env bash
# Run git with hooks disabled during active history rewrite / expunge / post-rewrite push.
# Re-enable with: bash scripts/git/install-local-hooks.sh
set -euo pipefail
exec git -c core.hooksPath=/dev/null "$@"
