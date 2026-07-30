#!/usr/bin/env bash
# Copy attribution-guard scripts from orama-system into a sibling repo checkout.
set -euo pipefail

target_input="${1:?target repo path required}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_root="$(cd "$SCRIPT_DIR/../.." && pwd)"

if ! target="$(git -C "$target_input" rev-parse --show-toplevel 2>/dev/null)"; then
  echo "skip: not a git repo: $target_input" >&2
  exit 0
fi

atomic_install_file() {
  local src="$1"
  local dest="$2"
  local mode="$3"
  local dest_dir tmp

  dest_dir="$(dirname "$dest")"
  mkdir -p "$dest_dir"
  tmp="$(mktemp "${dest_dir}/.$(basename "$dest").sync.XXXXXX")"
  if ! install -m "$mode" "$src" "$tmp"; then
    rm -f "$tmp"
    echo "error: failed staging $src -> $dest" >&2
    return 1
  fi
  if ! mv -f "$tmp" "$dest"; then
    rm -f "$tmp"
    echo "error: failed installing $src -> $dest" >&2
    return 1
  fi
}

for rel in \
  cursor-hooks-id.sh \
  hooks/commit-msg.strip-coauthor \
  disable-cursor-commit-attribution.sh \
  commit-clean.sh \
  verify-staged-for-commit.sh \
  commit_clean_test.sh \
  apply-attribution-guard-all-repos.sh \
  sync-attribution-guard-scripts.sh \
  sync-banned-patterns-to-repo.sh \
  banned_attribution_lib.sh \
  audit_attribution.sh \
  check_commit_message.sh \
  check_identity.sh \
  daily-attribution-guard.sh \
  neutralize-cursor-coauthor-hook.sh \
  expunge-all-workspace-repos.sh \
  verify-git-guards.sh \
  verify-guard-parity.sh \
  scan-tracked-banned-tokens.sh; do
  [[ -f "$SCRIPT_DIR/$rel" ]] || continue
  atomic_install_file "$SCRIPT_DIR/$rel" "$target/scripts/git/$rel" 0755
done

# Cursor Cloud agent helpers (orama canonical — synced to PT + AlphaClaw, not periscope).
for cursor_rel in append-pr-body.sh; do
  [[ -f "$source_root/scripts/cursor/$cursor_rel" ]] || continue
  atomic_install_file \
    "$source_root/scripts/cursor/$cursor_rel" \
    "$target/scripts/cursor/$cursor_rel" \
    0755
done
if [[ -f "$source_root/.cursor/commands/pr.md" ]]; then
  atomic_install_file \
    "$source_root/.cursor/commands/pr.md" \
    "$target/.cursor/commands/pr.md" \
    0644
fi

# daily-attribution-guard.sh is now a normal synced file (canonical full impl in the
# copy list above) — self-contained, byte-identical in every repo, derives its own
# REPO_ROOT. No thin wrapper: a wrapper hardcodes a path and, on its own target, would
# exec itself (infinite recursion). Single source of truth, zero fragmentation.

# Repo-local agent rules (Cursor Cloud) — no forbidden tokens in these files.
for rule in no-commit-attribution.mdc never-undo-attribution-expunge.mdc banned-attribution-local.mdc zero-banned-attribution-everywhere.mdc; do
  [[ -f "$source_root/.cursor/rules/$rule" ]] || continue
  atomic_install_file \
    "$source_root/.cursor/rules/$rule" \
    "$target/.cursor/rules/$rule" \
    0644
done

echo "synced guard scripts → $target"

snippet="$source_root/scripts/git/snippets/AGENTS-cursor-cloud-git.md"
if [[ -f "$snippet" ]]; then
  if [[ ! -f "$target/AGENTS.md" ]]; then
    {
      echo "# Agent instructions"
      echo
      cat "$snippet"
    } >"$target/AGENTS.md"
  elif ! grep -q 'apply-attribution-guard-all-repos' "$target/AGENTS.md" 2>/dev/null; then
    {
      echo
      cat "$snippet"
    } >>"$target/AGENTS.md"
  fi
fi
