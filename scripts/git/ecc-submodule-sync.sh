#!/usr/bin/env bash
# ecc-submodule-sync.sh — keep vendor/ecc-tools pinned to canonical (origin/main
# of ecc-tools) while preserving LOCAL-ONLY additions across submodule updates.
#
# Why: `git submodule update` hard-resets the submodule worktree to the recorded
# gitlink and silently discards local-only files. We keep the committed gitlink
# canonical (never a stale fork) and re-apply local extras from a saved patch.
#
# This is a developer-maintenance utility. It is never a runtime, startup,
# hook, CI, or automatic-upgrade mechanism.
#
# Manual workflow:
#   ecc-submodule-sync.sh save --review
#       # inspect the printed candidate and digest; this does not write the patch
#   ecc-submodule-sync.sh save --approve <sha256>
#       # re-check the same candidate, then atomically replace the patch
#   ecc-submodule-sync.sh update    # checkout recorded gitlink -> restore
#   ecc-submodule-sync.sh upgrade   # fetch -> checkout origin/main HEAD -> restore
#   ecc-submodule-sync.sh restore   # re-apply the reviewed patch explicitly
#   ecc-submodule-sync.sh status    # show SHAs and classify local source drift
#   ecc-submodule-sync.sh ignore-runtime  # locally ignore generated hook telemetry
#
# Lessons encoded 2026-06-21:
#   - restore: --3way fails for added files (no base in the index).  Plain apply
#     is used instead; "already exists in working directory" is NOT an error —
#     untracked new files survive `git checkout` automatically, so the file is
#     already where it needs to be.
#   - upgrade: `git submodule update` syncs to the RECORDED gitlink, not
#     origin/main.  `upgrade` is the dedicated verb for bumping to latest.
#   - checkout: use -f only after verifying that every local difference exactly
#     matches the already-reviewed patch. It must never silently snapshot or
#     discard new worktree changes.
#
# The patch lives at scripts/git/ecc-local-additions.patch (tracked, so it
# travels with the repo). It must stay free of secrets and workstation paths —
# repo_hygiene scans it like any tracked file.
set -euo pipefail

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

REPO="$(git rev-parse --show-toplevel)"
SUB="$REPO/vendor/ecc-tools"
PATCH="$REPO/scripts/git/ecc-local-additions.patch"
MANIFEST="$REPO/scripts/git/ecc-local-overlay.tsv"
CANDIDATE=""
OVERLAY_COUNT=0
OVERLAY_PATHS=("")
OVERLAY_MODES=("")
OVERLAY_INTENTS=("")
TRANSIENT_PATHS=(".claude/hooks/.logs/hook-log.jsonl")

die() { echo "ecc-submodule-sync: $*" >&2; exit 1; }
[ -d "$SUB/.git" ] || [ -f "$SUB/.git" ] || die "submodule not initialized at vendor/ecc-tools"

_load_overlay_manifest() {
  [ -r "$MANIFEST" ] || die "overlay registry missing: ${MANIFEST#$REPO/}"

  local path mode intent known i
  while IFS=$'\t' read -r path mode intent; do
    case "$path" in
      ""|\#*) continue ;;
    esac
    case "$mode" in
      new-file|additive) ;;
      *) die "overlay registry mode must be new-file or additive: $path" ;;
    esac
    [ -n "$intent" ] || die "overlay registry entry needs an intent: $path"
    for ((i = 0; i < OVERLAY_COUNT; i++)); do
      known="${OVERLAY_PATHS[$i]}"
      [ "$path" != "$known" ] || die "duplicate overlay registry path: $path"
    done
    OVERLAY_PATHS[$OVERLAY_COUNT]="$path"
    OVERLAY_MODES[$OVERLAY_COUNT]="$mode"
    OVERLAY_INTENTS[$OVERLAY_COUNT]="$intent"
    OVERLAY_COUNT=$((OVERLAY_COUNT + 1))
  done < "$MANIFEST"

  [ "$OVERLAY_COUNT" -gt 0 ] || die "overlay registry has no reviewed paths"
}

_sha256() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    die "save: need shasum or sha256sum to approve a reviewed patch"
  fi
}

_make_candidate() {
  CANDIDATE=$(mktemp "${PATCH}.candidate.XXXXXX")
  local tmp_index rc=0 transient
  tmp_index=$(mktemp "${PATCH}.index.XXXXXX")

  # Intent-to-add exposes untracked files in the diff. Use a temporary index so
  # review generation never mutates the developer's real submodule index.
  GIT_INDEX_FILE="$tmp_index" git -C "$SUB" read-tree HEAD || rc=$?
  if [ "$rc" -eq 0 ]; then
    GIT_INDEX_FILE="$tmp_index" git -C "$SUB" add --intent-to-add -A || rc=$?
  fi
  if [ "$rc" -eq 0 ]; then
    # A reviewed candidate is compared byte-for-byte with the tracked patch.
    # Full blob IDs keep that serialization stable across core.abbrev settings.
    local diff_args=(--binary --full-index HEAD -- .)
    for transient in "${TRANSIENT_PATHS[@]}"; do
      diff_args+=(":(exclude)$transient")
    done
    GIT_INDEX_FILE="$tmp_index" git -C "$SUB" diff "${diff_args[@]}" > "$CANDIDATE" || rc=$?
  fi
  rm -f "$tmp_index"
  [ "$rc" -eq 0 ] || return "$rc"
}

_cleanup_candidate() {
  if [ -n "${CANDIDATE:-}" ]; then
    rm -f "$CANDIDATE"
  fi
  return 0
}

trap _cleanup_candidate EXIT

_is_approved_path() {
  local path="$1"
  local i
  for ((i = 0; i < OVERLAY_COUNT; i++)); do
    [ "$path" = "${OVERLAY_PATHS[$i]}" ] && return 0
  done
  return 1
}

_is_transient_path() {
  local path="$1" transient
  for transient in "${TRANSIENT_PATHS[@]}"; do
    [ "$path" = "$transient" ] && return 0
  done
  return 1
}

_print_transient_drift() {
  local path records
  for path in "${TRANSIENT_PATHS[@]}"; do
    [ -f "$SUB/$path" ] || continue
    records=$(wc -l < "$SUB/$path" | tr -d ' ')
    printf '  transient-runtime-evidence: %s (%s record(s); excluded from overlay candidates)\n' "$path" "$records"
  done
}

_ignore_transient_paths() {
  local exclude path
  exclude=$(git -C "$SUB" rev-parse --git-path info/exclude)
  mkdir -p "$(dirname "$exclude")"
  touch "$exclude"

  for path in "${TRANSIENT_PATHS[@]}"; do
    if ! grep -Fqx "$path" "$exclude"; then
      printf '%s\n' "$path" >> "$exclude"
      printf 'ignore-runtime: added local ignore for %s\n' "$path"
    else
      printf 'ignore-runtime: local ignore already present for %s\n' "$path"
    fi
  done
}

_overlay_intent() {
  local path="$1" i
  for ((i = 0; i < OVERLAY_COUNT; i++)); do
    if [ "$path" = "${OVERLAY_PATHS[$i]}" ]; then
      printf '%s' "${OVERLAY_INTENTS[$i]}"
      return 0
    fi
  done
  return 1
}

_overlay_mode() {
  local path="$1" i
  for ((i = 0; i < OVERLAY_COUNT; i++)); do
    if [ "$path" = "${OVERLAY_PATHS[$i]}" ]; then
      printf '%s' "${OVERLAY_MODES[$i]}"
      return 0
    fi
  done
  return 1
}

_validate_candidate() {
  local candidate="$1"
  [ -s "$candidate" ] || return 0

  local path added removed intent mode n=0 expected_creates=0

  while IFS=$'\t' read -r added removed path; do
    [ -n "$path" ] || continue
    n=$((n + 1))
    _validate_markdown_fences "$path"
    _is_approved_path "$path" || die "save: drift at $path is not in the reviewed overlay registry; classify it before saving"
    intent=$(_overlay_intent "$path")
    [ -n "$intent" ] || die "save: overlay registry has no intent for $path"
    mode=$(_overlay_mode "$path")
    [ "$removed" = "0" ] || die "save: overlay path must be add-only: $path"
    [ "$added" != "0" ] || die "save: overlay path must add content: $path"
    [ "$mode" = "new-file" ] && expected_creates=$((expected_creates + 1))
    _validate_patch_mode "$candidate" "$path" "$mode"
  done < <(git apply --numstat "$candidate")

  local creates
  creates=$(grep -c '^new file mode ' "$candidate" 2>/dev/null || true)
  [ "$creates" -eq "$expected_creates" ] || die "save: overlay patch type does not match its reviewed mode"
  [ "$n" -le "$OVERLAY_COUNT" ] || die "save: candidate exceeds approved overlay path count"
  _validate_patch_markdown_fences "$candidate"
}

_is_markdown_path() {
  case "$1" in
    *.md|*.mdx) return 0 ;;
    *) return 1 ;;
  esac
}

_markdown_fence_state_file() {
  local file="$1"
  awk '
    {
      line = $0
      sub(/^[[:space:]]*/, "", line)
      marker = substr(line, 1, 1)
      if (marker != "`" && marker != "~") next

      length = 0
      while (substr(line, length + 1, 1) == marker) length++
      if (length < 3) next

      if (open_length == 0) {
        open_marker = marker
        open_length = length
        open_line = NR
      } else if (marker == open_marker && length >= open_length) {
        open_marker = ""
        open_length = 0
        open_line = 0
      }
    }
    END {
      if (open_length != 0) {
        printf "%d", open_line
        exit 1
      }
    }
  ' "$file"
}

_markdown_fence_state() {
  local path="$1"
  _markdown_fence_state_file "$SUB/$path"
}

_validate_markdown_fences() {
  local path="$1" open_line
  _is_markdown_path "$path" || return 0
  [ -f "$SUB/$path" ] || return 0

  if ! open_line=$(_markdown_fence_state "$path"); then
    die "save: unbalanced Markdown code fence in $path (opened at line $open_line)"
  fi
}

_validate_patch_markdown_fences() {
  local candidate="$1"
  local path sandbox open_line

  while IFS=$'\t' read -r _added _removed path; do
    [ -n "$path" ] || continue
    _is_markdown_path "$path" || continue
    _is_approved_path "$path" || continue

    sandbox=$(mktemp -d "${TMPDIR:-/tmp}/ecc-overlay-fence.XXXXXX")
    if git -C "$SUB" cat-file -e "HEAD:$path" 2>/dev/null; then
      mkdir -p "$sandbox/$(dirname "$path")"
      git -C "$SUB" show "HEAD:$path" > "$sandbox/$path"
    fi
    git -C "$sandbox" init -q
    if ! git -C "$sandbox" apply --include="$path" "$candidate"; then
      rm -rf "$sandbox"
      die "save: cannot validate Markdown overlay result for $path"
    fi
    if ! open_line=$(_markdown_fence_state_file "$sandbox/$path"); then
      rm -rf "$sandbox"
      die "save: reviewed overlay leaves an unbalanced Markdown code fence in $path (opened at line $open_line)"
    fi
    rm -rf "$sandbox"
  done < <(git apply --numstat "$candidate")
}

_classify_candidate() {
  local candidate="$1"
  [ -s "$candidate" ] || { echo "  no local source drift"; return 0; }

  local path added removed classification fence_state open_line
  while IFS=$'\t' read -r added removed path; do
    [ -n "$path" ] || continue

    if _is_approved_path "$path"; then
      classification="reviewed-overlay"
    else
      classification="unapproved-source-drift"
    fi

    fence_state=""
    if _is_markdown_path "$path" && [ -f "$SUB/$path" ]; then
      if ! open_line=$(_markdown_fence_state "$path"); then
        fence_state="; unbalanced-fence-opened-at-line-$open_line"
      fi
    fi
    printf '  %s: %s (+%s/-%s)%s\n' "$classification" "$path" "$added" "$removed" "$fence_state"
  done < <(git apply --numstat "$candidate")
}

_validate_patch_mode() {
  local candidate="$1" path="$2" mode="$3"
  local header
  header=$(awk -v p="$path" '
    $0 == "diff --git a/" p " b/" p { in_patch = 1; next }
    /^diff --git / && in_patch { exit }
    in_patch { print }
  ' "$candidate")

  [ -n "$header" ] || die "save: missing patch header for $path"
  if printf '%s\n' "$header" | grep -Eq '^(old mode|new mode|deleted file mode|rename from|rename to|copy from|copy to) '; then
    die "save: overlay path must not rename, copy, delete, or change file mode: $path"
  fi
  if printf '%s\n' "$header" | grep -Eq '^(new|old|deleted) file mode 120000'; then
    die "save: overlay path must not be a symlink: $path"
  fi

  case "$mode" in
    new-file)
      printf '%s\n' "$header" | grep -q '^new file mode 100644$' \
        || die "save: new-file overlay must be a regular 100644 file: $path"
      ;;
    additive)
      if printf '%s\n' "$header" | grep -q '^new file mode '; then
        die "save: additive overlay must not create a new file: $path"
      fi
      ;;
  esac
}

_print_candidate_assessment() {
  local candidate="$1"
  [ -s "$candidate" ] || { echo "  no local overlay drift"; return 0; }

  local path added removed intent mode
  while IFS=$'\t' read -r added removed path; do
    [ -n "$path" ] || continue
    intent=$(_overlay_intent "$path")
    mode=$(_overlay_mode "$path")
    printf '  approved %s: %s (%s)\n' "$mode" "$path" "$intent"
  done < <(git apply --numstat "$candidate")
}

_review_candidate() {
  _make_candidate
  _classify_candidate "$CANDIDATE"
  _validate_candidate "$CANDIDATE"

  local digest n
  digest=$(_sha256 "$CANDIDATE")
  n=$(grep -c '^diff ' "$CANDIDATE" 2>/dev/null || true)
  echo "save: reviewed candidate contains $n approved file diff(s)"
  _print_candidate_assessment "$CANDIDATE"
  if [ "$n" -gt 0 ]; then
    git apply --stat "$CANDIDATE"
    git apply --summary "$CANDIDATE"
    sed -n '1,240p' "$CANDIDATE"
  fi
  echo "save: review the candidate above; it has not changed ${PATCH#$REPO/}"
  echo "save: approve the exact candidate with:"
  echo "  bash scripts/git/ecc-submodule-sync.sh save --approve $digest"
  _cleanup_candidate
  CANDIDATE=""
}

_approve_candidate() {
  local expected="${1:-}"
  [ -n "$expected" ] || die "save: provide the digest printed by 'save --review'"

  _make_candidate
  _validate_candidate "$CANDIDATE"

  local actual n
  actual=$(_sha256 "$CANDIDATE")
  [ "$expected" = "$actual" ] || die "save: candidate changed since review; re-run 'save --review'"
  n=$(grep -c '^diff ' "$CANDIDATE" 2>/dev/null || true)

  if [ "$n" -eq 0 ]; then
    rm -f "$PATCH"
    echo "save: approved empty overlay; patch removed"
    _cleanup_candidate
    CANDIDATE=""
    return 0
  fi

  mv "$CANDIDATE" "$PATCH"
  CANDIDATE=""
  echo "save: approved $n reviewed file diff(s) -> ${PATCH#$REPO/}"
}

_require_reviewed_overlay() {
  _make_candidate
  _classify_candidate "$CANDIDATE"
  _validate_candidate "$CANDIDATE"

  # A clean checkout can legitimately be missing the local-only files that a
  # reviewed patch restores. There is no unreviewed drift to reject in that
  # state; update/upgrade must be allowed to continue to _restore.
  if [ ! -s "$CANDIDATE" ]; then
    _cleanup_candidate
    CANDIDATE=""
    return 0
  fi

  if cmp -s "$CANDIDATE" "$PATCH"; then
    _cleanup_candidate
    CANDIDATE=""
    return 0
  fi

  die "unreviewed submodule changes detected; run 'save --review', inspect it, then run 'save --approve <sha256>' before update or upgrade"
}

_restore() {
  [ -s "$PATCH" ] || { echo "restore: no patch to apply"; return 0; }
  _validate_candidate "$PATCH"

  # Apply each reviewed path separately. A local-only file can legitimately
  # survive checkout, but its "already exists" error must never suppress an
  # additive overlay for a different upstream-owned file.
  local i path mode out rc applied=0 present=0
  for ((i = 0; i < OVERLAY_COUNT; i++)); do
    path="${OVERLAY_PATHS[$i]}"
    mode="${OVERLAY_MODES[$i]}"

    # A repeated update may find either a surviving local-only file or an
    # additive hunk already present. Reverse-check first so both approved,
    # already-applied forms remain idempotent.
    if git -C "$SUB" apply --reverse --check --include="$path" "$PATCH" >/dev/null 2>&1; then
      present=$((present + 1))
      continue
    fi

    out=$(git -C "$SUB" apply --whitespace=nowarn --include="$path" "$PATCH" 2>&1) && rc=0 || rc=$?

    if [ "$rc" -eq 0 ]; then
      applied=$((applied + 1))
      continue
    fi

    if [ "$mode" = "new-file" ] && printf '%s\n' "$out" | grep -q "already exists in working directory"; then
      present=$((present + 1))
      continue
    fi

    printf '%s\n' "$out" >&2
    die "restore: $path did not apply cleanly — resolve its reviewed overlay before continuing"
  done

  if [ "$applied" -gt 0 ]; then
    echo "restore: $applied reviewed overlay path(s) re-applied"
  fi
  if [ "$present" -gt 0 ]; then
    echo "restore: $present reviewed overlay path(s) already applied"
  fi
  return 0
}

_do_checkout() {
  # Check out SHA $1 in the submodule.
  # _require_reviewed_overlay proves that no unreviewed change will be lost.
  local sha="$1"
  git -C "$SUB" checkout -f "$sha" 2>&1 | grep -v "^HEAD is now at" || true
  echo "  submodule HEAD -> $(git -C "$SUB" rev-parse --short HEAD)"
}

_load_overlay_manifest

case "${1:-help}" in

  save)
    case "${2:-}" in
      --review)
        _review_candidate
        ;;
      --approve)
        _approve_candidate "${3:-}"
        ;;
      *)
        die "save is review-gated; run 'save --review', inspect it, then run 'save --approve <sha256>'"
        ;;
    esac
    ;;

  restore)
    _restore
    ;;

  update)
    # Sync submodule worktree to the RECORDED gitlink (no network required).
    # It never creates or changes the patch; save is a separate manual chore.
    _require_reviewed_overlay
    target=$(git -C "$REPO" ls-tree HEAD vendor/ecc-tools | awk '{print $3}')
    echo "update: checking out gitlink $target"
    _do_checkout "$target"
    _restore
    echo "update: done"
    ;;

  upgrade)
    # Bump submodule to the LATEST commit on origin/main, preserving local additions.
    # Unlike 'update', this advances the gitlink — stage and commit afterward.
    # It never creates or changes the patch; save is a separate manual chore.
    _require_reviewed_overlay
    echo "upgrade: fetching ecc-tools origin ..."
    git -C "$SUB" fetch origin 2>&1 | sed 's/^/  /' || true

    new_sha=$(git -C "$SUB" rev-parse origin/main)
    cur_sha=$(git -C "$SUB" rev-parse HEAD)

    if [ "$new_sha" = "$cur_sha" ]; then
      echo "upgrade: already at origin/main ($new_sha)"
    else
      echo "upgrade: $cur_sha -> $new_sha"
      _do_checkout "$new_sha"
    fi

    _restore
    echo "upgrade: done"
    echo "  next: git add vendor/ecc-tools && git commit"
    ;;

  status)
    echo "gitlink (recorded): $(git -C "$REPO" ls-tree HEAD vendor/ecc-tools | awk '{print $3}')"
    echo "submodule HEAD:     $(git -C "$SUB" rev-parse HEAD)"
    echo "canonical (cached): $(git -C "$SUB" rev-parse origin/main 2>/dev/null || echo '?')"
    echo "pending local additions:"
    git -C "$SUB" status --short 2>/dev/null | sed 's/^/  /' || echo "  (clean)"
    echo "candidate classification:"
    _make_candidate
    _classify_candidate "$CANDIDATE"
    _cleanup_candidate
    CANDIDATE=""
    echo "transient runtime evidence:"
    _print_transient_drift
    ;;

  ignore-runtime)
    _ignore_transient_paths
    ;;

  *)
    grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'
    ;;
esac
