#!/usr/bin/env bash
# Non-negotiable: repo-local hooks must be active before any commit.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
if [[ -n "${REPO_ROOT:-}" ]] && [[ -d "$REPO_ROOT" ]]; then
  REPO_ROOT="$(cd "$REPO_ROOT" && pwd)"
  # Only remap when REPO_ROOT is nested under this script's checkout
  # (literal ~/ OPENCLAW_HOME junk clones). Do NOT remap arbitrary
  # alternate roots — tests and intentional REPO_ROOT overrides must keep
  # their own hook failures (e.g. non-executable hooks).
  case "$REPO_ROOT" in
    "$SCRIPT_REPO_ROOT"/*)
      if [[ ! -x "$REPO_ROOT/.githooks/pre-commit" && -x "$SCRIPT_REPO_ROOT/.githooks/pre-commit" ]]; then
        REPO_ROOT="$SCRIPT_REPO_ROOT"
      fi
      ;;
  esac
else
  REPO_ROOT="$SCRIPT_REPO_ROOT"
fi

cd "$REPO_ROOT"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "ERROR: not a git repository: $REPO_ROOT" >&2
  exit 1
fi

hooks_path="$(git config --local --get core.hooksPath 2>/dev/null || true)"
if [[ "$hooks_path" != ".githooks" ]]; then
  echo "ERROR: core.hooksPath=${hooks_path:-<unset>} — expected .githooks" >&2
  echo "Run: bash scripts/git/install-local-hooks.sh" >&2
  exit 1
fi

for hook in pre-commit commit-msg pre-push; do
  path="$REPO_ROOT/.githooks/$hook"
  if [[ ! -f "$path" || ! -x "$path" ]]; then
    echo "ERROR: missing or non-executable $path" >&2
    echo "Run: bash scripts/git/install-local-hooks.sh" >&2
    exit 1
  fi
done

exit 0
