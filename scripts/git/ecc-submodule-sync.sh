#!/usr/bin/env bash
# ecc-submodule-sync.sh — keep vendor/ecc-tools pinned to canonical (origin/main
# of ecc-tools) while preserving LOCAL-ONLY additions across submodule updates.
#
# Why: `git submodule update` hard-resets the submodule worktree to the recorded
# gitlink and silently discards local-only files. We keep the committed gitlink
# canonical (never a stale fork) and re-apply local extras from a saved patch.
#
# Workflow:
#   ecc-submodule-sync.sh save      # snapshot local-only additions -> patch (run BEFORE updating)
#   ecc-submodule-sync.sh restore   # re-apply the saved patch after an update
#   ecc-submodule-sync.sh update    # save -> checkout recorded gitlink -> restore
#   ecc-submodule-sync.sh upgrade   # save -> fetch -> checkout origin/main HEAD -> restore
#   ecc-submodule-sync.sh status    # show gitlink vs submodule HEAD vs origin/main
#
# Lessons encoded 2026-06-21:
#   - restore: --3way fails for added files (no base in the index).  Plain apply
#     is used instead; "already exists in working directory" is NOT an error —
#     untracked new files survive `git checkout` automatically, so the file is
#     already where it needs to be.
#   - upgrade: `git submodule update` syncs to the RECORDED gitlink, not
#     origin/main.  `upgrade` is the dedicated verb for bumping to latest.
#   - checkout: use -f to bypass "local changes would be overwritten" — tracked
#     modifications are already captured in the patch by _save, so discarding
#     them from the worktree before checkout is safe.
#
# The patch lives at scripts/git/ecc-local-additions.patch (tracked, so it
# travels with the repo). It must stay free of secrets and workstation paths —
# repo_hygiene scans it like any tracked file.
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
SUB="$REPO/vendor/ecc-tools"
PATCH="$REPO/scripts/git/ecc-local-additions.patch"

die() { echo "ecc-submodule-sync: $*" >&2; exit 1; }
[ -d "$SUB/.git" ] || [ -f "$SUB/.git" ] || die "submodule not initialized at vendor/ecc-tools"

_save() {
  # Capture everything that differs from the submodule's current HEAD:
  # untracked files are staged via intent-to-add so they appear in the diff.
  git -C "$SUB" add --intent-to-add -A 2>/dev/null || true
  git -C "$SUB" diff HEAD > "$PATCH"
  git -C "$SUB" reset -q 2>/dev/null || true   # undo intent-to-add staging
  local n; n=$(grep -c '^diff ' "$PATCH" 2>/dev/null || echo 0)
  if [ "$n" -eq 0 ]; then
    rm -f "$PATCH"
    echo "save: no local-only additions (patch removed)"
  else
    echo "save: $n file diff(s) -> ${PATCH#$REPO/}"
  fi
}

_restore() {
  [ -s "$PATCH" ] || { echo "restore: no patch to apply"; return 0; }

  # Plain apply (no --3way): --3way fails for added files because there is no
  # base version in the index to do a 3-way merge against.
  #
  # "already exists in working directory" is expected and benign: untracked new
  # files survive `git checkout` intact, so their presence means _save's patch
  # content is already on disk.  Treat it as success, not an error.
  local out rc
  out=$(git -C "$SUB" apply --whitespace=nowarn "$PATCH" 2>&1) && rc=0 || rc=$?

  if [ "$rc" -eq 0 ]; then
    echo "restore: local additions re-applied"
    return 0
  fi

  # Filter out the benign "already exists" noise.
  local real_errors
  real_errors=$(printf '%s\n' "$out" \
    | grep '^error:' \
    | grep -v "already exists in working directory" || true)

  if [ -z "$real_errors" ]; then
    local n; n=$(printf '%s\n' "$out" | grep -c "already exists" 2>/dev/null || echo 0)
    echo "restore: $n new-file path(s) already present (survived checkout) — skipped"
    return 0
  fi

  printf '%s\n' "$out" >&2
  die "restore: patch did not apply cleanly — resolve conflicts in $SUB, then re-run save"
}

_do_checkout() {
  # Check out SHA $1 in the submodule.
  # Use -f to discard tracked-file modifications: _save already captured them
  # in the patch, so losing the worktree copies is safe.
  local sha="$1"
  git -C "$SUB" checkout -f "$sha" 2>&1 | grep -v "^HEAD is now at" || true
  echo "  submodule HEAD -> $(git -C "$SUB" rev-parse --short HEAD)"
}

case "${1:-help}" in

  save)
    _save
    ;;

  restore)
    _restore
    ;;

  update)
    # Sync submodule worktree to the RECORDED gitlink (no network required).
    # Use this to undo manual SHA bumps or recover a clean state.
    _save || true
    target=$(git -C "$REPO" ls-tree HEAD vendor/ecc-tools | awk '{print $3}')
    echo "update: checking out gitlink $target"
    _do_checkout "$target"
    _restore
    echo "update: done"
    ;;

  upgrade)
    # Bump submodule to the LATEST commit on origin/main, preserving local additions.
    # Unlike 'update', this advances the gitlink — stage and commit afterward.
    echo "upgrade: fetching ecc-tools origin ..."
    git -C "$SUB" fetch origin 2>&1 | sed 's/^/  /' || true

    new_sha=$(git -C "$SUB" rev-parse origin/main)
    cur_sha=$(git -C "$SUB" rev-parse HEAD)

    if [ "$new_sha" = "$cur_sha" ]; then
      echo "upgrade: already at origin/main ($new_sha) — nothing to do"
      exit 0
    fi

    echo "upgrade: $cur_sha -> $new_sha"
    _save || true
    _do_checkout "$new_sha"
    _restore
    echo "upgrade: done"
    echo "  next: git add vendor/ecc-tools && git commit"
    ;;

  status)
    echo "gitlink (recorded): $(git -C "$REPO" ls-tree HEAD vendor/ecc-tools | awk '{print $3}')"
    echo "submodule HEAD:     $(git -C "$SUB" rev-parse HEAD)"
    # Fetch quietly so the canonical SHA reflects the true upstream state.
    git -C "$SUB" fetch origin --quiet 2>/dev/null || true
    echo "canonical (origin): $(git -C "$SUB" rev-parse origin/main 2>/dev/null || echo '?')"
    echo "pending local additions:"
    git -C "$SUB" status --short 2>/dev/null | sed 's/^/  /' || echo "  (clean)"
    ;;

  *)
    grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'
    ;;
esac
