#!/usr/bin/env bash
# Thin wrapper: check_commit_message_claims.py needs python3, this keeps the
# .githooks/commit-msg chain (all bash scripts) uniform.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/check_commit_message_claims.py" "$@"
