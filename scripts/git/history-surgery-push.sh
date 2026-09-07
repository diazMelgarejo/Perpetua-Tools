#!/usr/bin/env bash
# Hooks-off git push for post-rewrite / expunge windows.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x "$SCRIPT_DIR/history-surgery-git.sh" ]]; then
  exec bash "$SCRIPT_DIR/history-surgery-git.sh" push "$@"
fi
exec git -c core.hooksPath=/dev/null push "$@"
