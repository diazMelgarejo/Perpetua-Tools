#!/usr/bin/env bash
# Operator-only: mint HMAC-bound grant for append-pr-body.sh (interactive TTY).
# Agents must not run this — hooks and append script verify the grant artifact.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB="$SCRIPT_DIR/pr-body-grant-lib.py"

if [[ ! -t 0 || ! -t 1 ]]; then
  echo "error: grant requires a full interactive operator terminal (stdin+stdout TTY)" >&2
  exit 1
fi

if [[ -n "${CURSOR_AGENT:-}" ]] || [[ -n "${CI:-}" ]]; then
  echo "error: grant must be run from operator shell, not agent/CI" >&2
  exit 1
fi

if [[ $# -lt 2 && "${1:-}" != "-h" && "${1:-}" != "--help" ]]; then
  echo "error: usage: grant-pr-body-human-override.sh <owner/repo> <pr-number> --file|--message" >&2
  exit 1
fi

repo_slug="${1:-}"
pr_number="${2:-}"
shift 2 || true

append_file=""
append_message=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --file)
      append_file="${2:-}"
      shift 2
      ;;
    --message)
      append_message="${2:-}"
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
Usage:
  scripts/cursor/grant-pr-body-human-override.sh <owner/repo> <pr-number> --file <append.md>
  scripts/cursor/grant-pr-body-human-override.sh <owner/repo> <pr-number> --message "markdown"

Mint operator-grant-v2 (8h TTL, single-use, HMAC + content digest binding).
Run append-pr-body.sh with the SAME --file or --message immediately after granting.
EOF
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

[[ -n "$repo_slug" && -n "$pr_number" ]] || {
  echo "error: usage: grant-pr-body-human-override.sh <owner/repo> <pr-number> --file|--message" >&2
  exit 1
}

if [[ -n "$append_file" && -n "$append_message" ]]; then
  echo "error: provide --file or --message, not both" >&2
  exit 1
fi

if [[ -z "$append_file" && -z "$append_message" ]]; then
  echo "error: provide --file or --message matching the planned append" >&2
  exit 1
fi

cmd=(python3 "$LIB" mint --repo "$repo_slug" --pr "$pr_number")
if [[ -n "$append_file" ]]; then
  cmd+=(--file "$append_file")
else
  cmd+=(--message "$append_message")
fi

exec "${cmd[@]}"
