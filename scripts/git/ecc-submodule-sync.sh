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
#   ecc-submodule-sync.sh update    # save -> submodule update -> restore (the safe one-shot)
#   ecc-submodule-sync.sh restore   # re-apply the saved patch after an update
#   ecc-submodule-sync.sh status    # show gitlink vs canonical + pending local additions
#
# The patch lives at scripts/git/ecc-local-additions.patch (tracked, so it travels
# with the repo). It must stay free of secrets and workstation paths — repo_hygiene
# scans it like any tracked file.
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
SUB="$REPO/vendor/ecc-tools"
PATCH="$REPO/scripts/git/ecc-local-additions.patch"

die() { echo "ecc-submodule-sync: $*" >&2; exit 1; }
[ -d "$SUB/.git" ] || [ -f "$SUB/.git" ] || die "submodule not initialized at vendor/ecc-tools"

_save() {
  # Capture everything in the submodule worktree that differs from its current
  # HEAD (== the recorded gitlink after an update): untracked + modified locals.
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
  if git -C "$SUB" apply --3way --whitespace=nowarn "$PATCH"; then
    echo "restore: local additions re-applied"
  else
    die "restore: patch did not apply cleanly — resolve in $SUB, then re-run save"
  fi
}

case "${1:-help}" in
  save)    _save ;;
  restore) _restore ;;
  update)
    _save || true
    git -C "$REPO" submodule update --init --recursive vendor/ecc-tools
    _restore
    ;;
  status)
    echo "gitlink (recorded): $(git -C "$REPO" ls-tree HEAD vendor/ecc-tools | awk '{print $3}')"
    echo "submodule HEAD:     $(git -C "$SUB" rev-parse HEAD)"
    echo "canonical (origin): $(git -C "$SUB" rev-parse origin/main 2>/dev/null || echo '?')"
    echo "pending local additions:"
    git -C "$SUB" status --short 2>/dev/null | sed 's/^/  /' || echo "  (clean)"
    ;;
  *)
    grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'
    ;;
esac
