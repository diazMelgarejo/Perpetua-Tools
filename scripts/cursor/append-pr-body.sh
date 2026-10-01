#!/usr/bin/env bash
# Append-only PR body updates — NEVER replace the original Summary.
# Canonical: orama-system/scripts/cursor/append-pr-body.sh
#
# ManagePullRequest update_pr and gh pr edit REPLACE the entire body field.
# Agents must READ → backup → merge append-only → write full merged body.
set -euo pipefail

readonly CURSOR_BODY_END='<!-- CURSOR_AGENT_PR_BODY_END -->'
readonly CODERABBIT_MARKER='<!-- This is an auto-generated comment: release notes by coderabbit.ai -->'

usage() {
  cat <<'EOF'
Usage:
  scripts/cursor/append-pr-body.sh <owner/repo> <pr-number> --file <append.md>
  scripts/cursor/append-pr-body.sh <owner/repo> <pr-number> --message "markdown"
  scripts/cursor/append-pr-body.sh <owner/repo> <pr-number> --title "Follow-up title" --file <append.md>

Mandatory workflow:
  1. Fetch current body (gh pr view --json body)
  2. Save timestamped backup (.git/pr-body-backups/<repo>-pr<N>-<ts>.md)
  3. Insert new ## Follow-up block before CURSOR_AGENT_PR_BODY_END or CodeRabbit section
  4. Re-fetch and reject a stale body immediately before write
  5. gh pr edit --body-file (full merged body — integrative, not delta-only)
  6. Re-read and verify the remote body equals the merged body

Never pass body= with only the latest paragraph to ManagePullRequest update_pr.
EOF
}

guard_trace() {
  # Test-only seam: records which integrity guard was actually reached, so
  # tests can assert on runtime behaviour rather than scanning source text.
  # Never affects production control flow -- inert unless a test sets the var.
  if [[ -n "${PR_BODY_GUARD_TRACE_FILE:-}" ]]; then
    printf '%s\n' "$1" >>"$PR_BODY_GUARD_TRACE_FILE"
  fi
}

sha256_file() {
  python3 - "$1" <<'PY'
import hashlib
import sys
from pathlib import Path

print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
}

sha256_gh_view_body() {
  python3 - "$1" <<'PY'
import hashlib
import sys
from pathlib import Path

# `gh pr view --jq .body` writes one presentation LF after the JSON string.
# Remove exactly that transport byte, never the PR body's own trailing bytes.
content = Path(sys.argv[1]).read_bytes()
if not content.endswith(b"\n"):
    raise SystemExit("gh pr view output lacked its expected presentation newline")
print(hashlib.sha256(content[:-1]).hexdigest())
PY
}

build_merged_body() {
  python3 - "$1" "$2" "$3" "$4" "$CURSOR_BODY_END" "$CODERABBIT_MARKER" <<'PY'
import sys
from pathlib import Path

remote_path, append_path, out_path, title, cursor_end, coderabbit_marker = sys.argv[1:]
body = Path(remote_path).read_bytes()
if not body.endswith(b"\n"):
    raise SystemExit("gh pr view output lacked its expected presentation newline")
body = body[:-1]  # Strip the one `gh --jq` presentation LF only.
append_block = Path(append_path).read_bytes()
cursor_end_b = cursor_end.encode("utf-8")
coderabbit_marker_b = coderabbit_marker.encode("utf-8")
if cursor_end_b in append_block or coderabbit_marker_b in append_block:
    raise SystemExit("append content must not contain reserved PR body delimiters")
if body.count(cursor_end_b) > 1:
    raise SystemExit("PR body contains multiple CURSOR_AGENT_PR_BODY_END markers; manual repair required")
if body.count(coderabbit_marker_b) > 1:
    raise SystemExit("PR body contains multiple CodeRabbit markers; manual repair required")

follow_up = b"\n\n## " + title.encode("utf-8") + b"\n\n" + append_block
if cursor_end_b in body:
    merged = body.replace(cursor_end_b, follow_up + b"\n" + cursor_end_b, 1)
elif coderabbit_marker_b in body:
    merged = body.replace(coderabbit_marker_b, follow_up + b"\n\n" + coderabbit_marker_b, 1)
else:
    merged = body + follow_up
Path(out_path).write_bytes(merged)
PY
}

normalize_follow_up_title() {
  local raw="${1:-}"
  local rest="$raw"
  if [[ "$rest" == Follow-up:* ]]; then
    rest="${rest#Follow-up:}"
  elif [[ "$rest" == Follow-up\ * ]]; then
    rest="${rest#Follow-up }"
  elif [[ "$rest" == Follow-up* ]]; then
    rest="${rest#Follow-up}"
  fi
  rest="${rest#"${rest%%[![:space:]]*}"}"
  printf 'Follow-up: %s' "$rest"
}

resolve_git_backup_dir() {
  local git_common_dir
  if ! git_common_dir="$(git rev-parse --git-common-dir 2>/dev/null)"; then
    echo "error: must run inside a git repository" >&2
    return 1
  fi
  if [[ "$git_common_dir" != /* ]]; then
    git_common_dir="$(git rev-parse --show-toplevel)/$git_common_dir"
  fi
  printf '%s/pr-body-backups' "$(cd "$git_common_dir" && pwd)"
}

repo_slug="${1:-}"
pr_number="${2:-}"
shift 2 || true

title=""
append_file=""
append_message=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --title)
      title="${2:-}"
      shift 2
      ;;
    --file)
      append_file="${2:-}"
      shift 2
      ;;
    --message)
      append_message="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

[[ -n "$repo_slug" && -n "$pr_number" ]] || {
  usage
  exit 1
}

if [[ -n "$append_file" && -n "$append_message" ]]; then
  echo "error: provide --file or --message, not both" >&2
  exit 1
fi

if [[ -z "$append_file" && -z "$append_message" ]]; then
  echo "error: provide --file or --message" >&2
  exit 1
fi

if [[ -n "$append_file" && ! -f "$append_file" ]]; then
  echo "error: append file not found: $append_file" >&2
  exit 1
fi

GH_BIN="${GH_BIN:-gh}"
if ! command -v "$GH_BIN" >/dev/null 2>&1; then
  echo "error: gh CLI required" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GRANT_LIB="$SCRIPT_DIR/pr-body-grant-lib.py"

remote_tmp="$(mktemp)"
reread_tmp="$(mktemp)"
prewrite_tmp="$(mktemp)"
postwrite_tmp="$(mktemp)"
append_tmp="$(mktemp)"
out="$(mktemp)"
grant_finalized=0
grant_append_args=(--repo "$repo_slug" --pr "$pr_number" --file "$append_tmp")
release_on_fail() {
  if [[ "$grant_finalized" -eq 1 ]]; then
    return 0
  fi
  python3 "$GRANT_LIB" release "${grant_append_args[@]}" >/dev/null 2>&1 || true
}
trap 'release_on_fail; rm -f "$out" "$append_tmp" "$remote_tmp" "$reread_tmp" "$prewrite_tmp" "$postwrite_tmp"' EXIT

# Freeze the payload before any grant lifecycle operation. The grant binds
# bytes, not a mutable pathname; verify, reconcile, reserve, mark, consume,
# and failure release must therefore all receive this same snapshot.  Validate
# and bound a file source *before* copying it: an untrusted path must not be
# able to fill the temporary filesystem before the grant library rejects it.
if [[ -n "$append_file" ]]; then
  python3 - "$append_file" "$append_tmp" <<'PY'
import os
import stat
import sys
from pathlib import Path

MAX_APPEND_FILE_BYTES = 1024 * 1024
source = Path(sys.argv[1])
destination = Path(sys.argv[2])
flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
try:
    fd = os.open(source, flags)
except OSError as exc:
    raise SystemExit(f"error: cannot open append file safely: {source}: {exc}") from exc

try:
    source_stat = os.fstat(fd)
    if not stat.S_ISREG(source_stat.st_mode):
        raise SystemExit(f"error: append file is not a regular file: {source}")
    if source_stat.st_size > MAX_APPEND_FILE_BYTES:
        raise SystemExit(
            "error: append file exceeds size limit "
            f"({source_stat.st_size} > {MAX_APPEND_FILE_BYTES} bytes): {source}"
        )
    chunks: list[bytes] = []
    remaining = MAX_APPEND_FILE_BYTES + 1
    while remaining:
        chunk = os.read(fd, min(65536, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    data = b"".join(chunks)
    if len(data) > MAX_APPEND_FILE_BYTES:
        raise SystemExit(
            "error: append file exceeds size limit "
            f"(more than {MAX_APPEND_FILE_BYTES} bytes): {source}"
        )
finally:
    os.close(fd)

destination.write_bytes(data)
PY
else
  printf '%s' "$append_message" >"$append_tmp"
fi

verify_cmd=(python3 "$GRANT_LIB" verify "${grant_append_args[@]}")
if ! "${verify_cmd[@]}"; then
  echo "hint: operator runs grant-pr-body-human-override.sh with the same --file|--message" >&2
  exit 1
fi

if [[ -z "$title" ]]; then
  title="$(normalize_follow_up_title "Follow-up ($(date -u +%Y-%m-%d))")"
else
  title="$(normalize_follow_up_title "$title")"
fi

"$GH_BIN" pr view "$pr_number" --repo "$repo_slug" --json body --jq .body >"$remote_tmp"
current_body_digest="$(sha256_gh_view_body "$remote_tmp")"
reconcile_rc=0
reconcile_cmd=(
  python3 "$GRANT_LIB" reconcile "${grant_append_args[@]}"
  --title "$title" --remote-body-file "$remote_tmp"
)
reconcile_cmd_output="$("${reconcile_cmd[@]}" 2>&1)" || reconcile_rc=$?
if [[ "$reconcile_rc" -eq 0 ]]; then
  echo "$reconcile_cmd_output"
  grant_finalized=1
  echo "updated: https://github.com/${repo_slug}/pull/${pr_number}"
  exit 0
fi
if [[ "$reconcile_rc" -ne 2 ]]; then
  echo "$reconcile_cmd_output" >&2
  exit 1
fi

backup_dir="$(resolve_git_backup_dir)"
mkdir -p "$backup_dir"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
safe_slug="${repo_slug//\//-}"
backup_path="$(mktemp "${backup_dir}/${safe_slug}-pr${pr_number}-${ts}.XXXXXX")"

python3 - "$remote_tmp" "$backup_path" <<'PY'
import sys
from pathlib import Path

body = Path(sys.argv[1]).read_bytes()
if not body.endswith(b"\n"):
    raise SystemExit("gh pr view output lacked its expected presentation newline")
Path(sys.argv[2]).write_bytes(body[:-1])
PY
echo "backup: $backup_path"

if ! build_merged_body "$remote_tmp" "$append_tmp" "$out" "$title"; then
  echo "error: unable to build merged PR body" >&2
  exit 1
fi

base_body_digest="sha256:$(sha256_gh_view_body "$remote_tmp")"
merged_body_digest="sha256:$(sha256_file "$out")"
reserve_cmd=(
  python3 "$GRANT_LIB" reserve "${grant_append_args[@]}"
  --base-body-digest "$base_body_digest"
  --merged-body-digest "$merged_body_digest"
)
if ! "${reserve_cmd[@]}"; then
  echo "hint: operator runs grant-pr-body-human-override.sh with the same --file|--message" >&2
  exit 1
fi

# This is best-effort optimistic concurrency, not an atomic precondition:
# GitHub's PR-body endpoint has no compare-and-swap or expected-revision
# argument. A local lock cannot prevent external GitHub edits between this
# final reread and `gh pr edit`; use comment/notes reporting when that risk is
# unacceptable. The guard still prevents stale writes observed before it.
"$GH_BIN" pr view "$pr_number" --repo "$repo_slug" --json body --jq .body >"$reread_tmp"
if [[ "$(sha256_gh_view_body "$reread_tmp")" != "$current_body_digest" ]]; then
  guard_trace PR_BODY_E_STALE_ON_REREAD
  echo "error: [PR_BODY_E_STALE_ON_REREAD] PR body changed since initial read; aborting to avoid overwrite" >&2
  echo "hint: review concurrent edits and re-run append-pr-body.sh" >&2
  exit 1
fi

"$GH_BIN" pr view "$pr_number" --repo "$repo_slug" --json body --jq .body >"$prewrite_tmp"
prewrite_body_digest="$(sha256_gh_view_body "$prewrite_tmp")"
if [[ "$prewrite_body_digest" != "$current_body_digest" ]]; then
  guard_trace PR_BODY_E_STALE_PREWRITE
  echo "error: [PR_BODY_E_STALE_PREWRITE] PR body changed immediately before write; aborting to avoid stale overwrite" >&2
  echo "hint: review concurrent edits and re-run append-pr-body.sh with a fresh operator grant if needed" >&2
  exit 1
fi

if ! "$GH_BIN" pr edit "$pr_number" --repo "$repo_slug" --body-file "$out"; then
  echo "error: gh pr edit failed" >&2
  exit 1
fi

# Mark remote_applied immediately once the write is accepted by the API --
# BEFORE post-write verification, not after. release_nonce_reservation_atomic
# (invoked via the EXIT trap on any later failure) already refuses to release
# a reservation once remote_applied is true; that guard only protects a
# failure path if remote_applied was set before that path could be reached.
# Marking it after post-write verification left every failure between the
# write and that mark -- including a genuine post-write mismatch -- free to
# release the reservation and permit replay, despite a write having actually
# landed. Confirmed this ordering gap directly before fixing, not assumed.
mark_cmd=(python3 "$GRANT_LIB" mark-applied "${grant_append_args[@]}")
if ! "${mark_cmd[@]}"; then
  echo "error: [PR_BODY_E_MARK_APPLIED_FAILED] grant mark-applied failed immediately after PR body write — treat as security incident" >&2
  exit 1
fi

"$GH_BIN" pr view "$pr_number" --repo "$repo_slug" --json body --jq .body >"$postwrite_tmp"
if [[ "$(sha256_gh_view_body "$postwrite_tmp")" != "$(sha256_file "$out")" ]]; then
  guard_trace PR_BODY_E_POSTWRITE_MISMATCH
  echo "error: [PR_BODY_E_POSTWRITE_MISMATCH] remote PR body does not match the merged body after write; treat as concurrency/integrity incident" >&2
  exit 1
fi

consume_cmd=(python3 "$GRANT_LIB" consume "${grant_append_args[@]}")
if ! "${consume_cmd[@]}"; then
  echo "error: grant consume failed AFTER the PR body update. The remote write already landed." >&2
  echo "  cause: the nonce ledger could not be updated, so the grant may still be replayable." >&2
  echo "  fix: delete ~/.cursor/pr-body-human-override-ack now, then review .git/pr-body-backups." >&2
  exit 1
fi

grant_finalized=1
echo "updated: https://github.com/${repo_slug}/pull/${pr_number}"
