#!/usr/bin/env bash
# agentic-stack-submodule-sync.sh — keep vendor/agentic-stack pinned to a known
# upstream release while PT's live `.agent/` brain stays in-repo (customized).
#
# Unlike vendor/ecc-tools, PT does NOT carry local-only patches inside the
# agentic-stack submodule. The submodule is the upstream reference skeleton +
# installer source (`install.sh`, `agentic-stack upgrade`). PT `.agent/` is the
# operational brain and may diverge — use `agentic-stack upgrade --dry-run` from
# vendor/agentic-stack before bumping the gitlink.
#
# Workflow:
#   agentic-stack-submodule-sync.sh status   # gitlink vs HEAD vs origin/master
#   agentic-stack-submodule-sync.sh update   # checkout recorded gitlink
#   agentic-stack-submodule-sync.sh upgrade    # fetch origin/master -> bump worktree
#
# Pin policy: record the gitlink in a commit after `upgrade`; tag releases are
# listed in https://github.com/codejunkie99/agentic-stack/blob/master/CHANGELOG.md
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
SUB="$REPO/vendor/agentic-stack"
UPSTREAM_BRANCH="${AGENTIC_STACK_UPSTREAM_BRANCH:-master}"

die() { echo "agentic-stack-submodule-sync: $*" >&2; exit 1; }
[ -d "$SUB/.git" ] || [ -f "$SUB/.git" ] || die "submodule not initialized at vendor/agentic-stack"

_do_checkout() {
  local sha="$1"
  git -C "$SUB" checkout -f "$sha" 2>&1 | grep -v "^HEAD is now at" || true
  echo "  submodule HEAD -> $(git -C "$SUB" rev-parse --short HEAD)"
}

case "${1:-help}" in

  update)
    target=$(git -C "$REPO" ls-tree HEAD vendor/agentic-stack | awk '{print $3}')
    echo "update: checking out gitlink $target"
    _do_checkout "$target"
    echo "update: done"
    ;;

  upgrade)
    echo "upgrade: fetching agentic-stack origin ..."
    git -C "$SUB" fetch origin 2>&1 | sed 's/^/  /' || true

    new_sha=$(git -C "$SUB" rev-parse "origin/$UPSTREAM_BRANCH")
    cur_sha=$(git -C "$SUB" rev-parse HEAD)

    if [ "$new_sha" = "$cur_sha" ]; then
      echo "upgrade: already at origin/$UPSTREAM_BRANCH ($new_sha) — nothing to do"
      exit 0
    fi

    echo "upgrade: $cur_sha -> $new_sha"
    _do_checkout "$new_sha"
    echo "upgrade: done"
    echo "  next: review vendor/agentic-stack CHANGELOG, run agentic-stack upgrade --dry-run in PT root"
    echo "  then: git add vendor/agentic-stack && git commit"
    ;;

  status)
    echo "gitlink (recorded): $(git -C "$REPO" ls-tree HEAD vendor/agentic-stack | awk '{print $3}')"
    echo "submodule HEAD:     $(git -C "$SUB" rev-parse HEAD)"
    git -C "$SUB" fetch origin --quiet 2>/dev/null || true
    echo "upstream (origin/$UPSTREAM_BRANCH): $(git -C "$SUB" rev-parse "origin/$UPSTREAM_BRANCH" 2>/dev/null || echo '?')"
    tag=$(git -C "$SUB" describe --tags --exact-match 2>/dev/null || echo "(no tag at HEAD)")
    echo "tag at HEAD:        $tag"
    ;;

  *)
    grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'
    ;;
esac
