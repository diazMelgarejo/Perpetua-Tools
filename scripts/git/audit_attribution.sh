#!/usr/bin/env bash
# Scan commits for Co-authored-by policy, non-approved authors, and banned attribution.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
N="${1:-79}"
exec python3 "$SCRIPT_DIR/audit_engine.py" audit \
  --repo "$REPO_ROOT" \
  --history-count "$N"
