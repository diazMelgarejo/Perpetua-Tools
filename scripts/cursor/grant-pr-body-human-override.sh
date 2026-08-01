#!/usr/bin/env bash
# Operator-only: grant time-limited authorization for append-pr-body.sh (interactive TTY).
# Agents must not run this — hooks validate the issued grant file, not shell env alone.
set -euo pipefail

if [[ ! -t 0 && ! -t 1 ]]; then
  echo "error: grant-pr-body-human-override requires an interactive operator terminal" >&2
  exit 1
fi

ack_dir="${HOME}/.cursor"
ack_file="${ack_dir}/pr-body-human-override-ack"
issued_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

mkdir -p "$ack_dir"
umask 077
cat >"$ack_file" <<EOF
operator-grant-v1
issued-at=${issued_at}
EOF
chmod 600 "$ack_file"

echo "OK: PR body append grant issued (8h TTL)"
echo "  ${ack_file}"
echo "  Operator may run: bash scripts/cursor/append-pr-body.sh <owner/repo> <N> ..."
