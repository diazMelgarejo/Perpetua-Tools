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
  check_file_deletion_guard.sh
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

# Cursor Cloud helpers are also canonical payloads. Keep their lists here so
# install, divergence detection, and parity validation cannot silently cover
# different surfaces.
GUARD_SYNC_CURSOR_EXECUTABLES=(
  append-pr-body.sh
  grant-pr-body-human-override.sh
  pr-body-grant-lib.py
  hooks/pr-body-guard-core.py
  hooks/pr-body-backup-lib.sh
  hooks/before-shell-pr-body-guard.sh
  hooks/before-mcp-pr-body-guard.sh
)

GUARD_SYNC_CURSOR_COMMANDS=(
  pr.md
)

GUARD_SYNC_CURSOR_RULES=(
  no-commit-attribution.mdc
  never-undo-attribution-expunge.mdc
  append-only-pr-body.mdc
  banned-attribution-local.mdc
  zero-banned-attribution-everywhere.mdc
)

# Compatibility view for callers that address the legacy scripts/git-relative
# manifest. New code must use GUARD_PARITY_ROOT_REQUIRED below.
GUARD_PARITY_REQUIRED=(
  "${GUARD_SYNC_EXECUTABLES[@]}"
  "${GUARD_SYNC_DATA_FILES[@]}"
)

# Every unconditional sync destination, expressed relative to repo root.
# .githooks remains conditional on an explicit hooks-path opt-in and is
# therefore checked separately by the callers that understand that condition.
GUARD_PARITY_ROOT_REQUIRED=()
for _guard_sync_rel in "${GUARD_PARITY_REQUIRED[@]}"; do
  GUARD_PARITY_ROOT_REQUIRED+=("scripts/git/${_guard_sync_rel}")
done
for _guard_sync_rel in "${GUARD_SYNC_CURSOR_EXECUTABLES[@]}"; do
  GUARD_PARITY_ROOT_REQUIRED+=("scripts/cursor/${_guard_sync_rel}")
done
for _guard_sync_rel in "${GUARD_SYNC_CURSOR_COMMANDS[@]}"; do
  GUARD_PARITY_ROOT_REQUIRED+=(".cursor/commands/${_guard_sync_rel}")
done
for _guard_sync_rel in "${GUARD_SYNC_CURSOR_RULES[@]}"; do
  GUARD_PARITY_ROOT_REQUIRED+=(".cursor/rules/${_guard_sync_rel}")
done
unset _guard_sync_rel

# Dirty guard-sync paths with GUARD_SYNC_ON_DIRTY=skip — not success, not a hard failure.
GUARD_SYNC_EXIT_DIRTY_SKIP=2
