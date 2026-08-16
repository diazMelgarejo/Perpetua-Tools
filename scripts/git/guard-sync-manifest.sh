#!/usr/bin/env bash
# guard-sync-manifest.sh — single source of truth for canonical scripts/git/
# tooling distribution (attribution guards, plus shared cross-repo git
# utilities like resolve_sibling_git_repo.sh that have no reason to fork).
#
# orama-system scripts/git/ is CANONICAL. Perpetua-Tools (and AlphaClaw) carry
# byte-identical downstream mirrors via sync-attribution-guard-scripts.sh.
#
# Sourced by:
#   - sync-attribution-guard-scripts.sh (install loops)
#   - verify-guard-parity.sh (completeness + parity checks)
#
# Edit HERE only — never duplicate these lists in downstream repos.

# Executable guard tooling (mode 0755 when synced).
GUARD_SYNC_EXECUTABLES=(
  resolve_sibling_git_repo.sh
  check_commit_message_claims.sh
  check_commit_message_claims.py
  find_stranded_work.sh
  ensure_hooks_installed.sh
  check_tdd_commit.sh
  cursor-hooks-id.sh
  hooks/commit-msg.strip-coauthor
  disable-cursor-commit-attribution.sh
  commit-clean.sh
  verify-staged-for-commit.sh
  commit_clean_test.sh
  apply-attribution-guard-all-repos.sh
  sync-attribution-guard-scripts.sh
  guard-sync-manifest.sh
  sync-banned-patterns-to-repo.sh
  banned_attribution_lib.sh
  audit_attribution.sh
  check_commit_message.sh
  check_identity.sh
  check_no_pending_merge.sh
  daily-attribution-guard.sh
  neutralize-cursor-coauthor-hook.sh
  expunge-all-workspace-repos.sh
  verify-git-guards.sh
  verify-guard-parity.sh
  check-guard-sync-divergence.sh
  scan-tracked-banned-tokens.sh
  remind-pr-body-append-only.sh
  publish-clean-branch.sh
  history-surgery-git.sh
  verify-pr-body-not-clobbered.sh
  scrub_dsstore.sh
)

# Non-executable policy/data files (mode 0644 when synced).
GUARD_SYNC_DATA_FILES=(
  audit_engine.py
  identity-policy.json
  identity-policy.schema.json
)

# .githooks/ entrypoints (mode 0755 when synced). These call into the
# GUARD_SYNC_EXECUTABLES above, guarded by [[ -x ... ]] existence checks so
# the SAME content works whether or not a given optional script exists in a
# repo (e.g. check_tdd_commit.sh no-ops outside web/src/). Only synced to
# repos that already opted into core.hooksPath=.githooks -- see
# sync-attribution-guard-scripts.sh's handling.
GUARD_SYNC_GITHOOKS=(
  commit-msg
  pre-push
)

# Every synced path must be byte-identical in downstream repos when parity runs.
# (reanchor_scan.sh ships via full repo checkout — not in this manifest.)
GUARD_PARITY_REQUIRED=(
  "${GUARD_SYNC_EXECUTABLES[@]}"
  "${GUARD_SYNC_DATA_FILES[@]}"
)

# Dirty guard-sync paths with GUARD_SYNC_ON_DIRTY=skip — not success, not a hard failure.
GUARD_SYNC_EXIT_DIRTY_SKIP=2
