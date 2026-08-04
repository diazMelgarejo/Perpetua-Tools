#!/usr/bin/env bash
# Copy attribution-guard scripts from orama-system into a sibling repo checkout.
set -euo pipefail

target_input="${1:?target repo path required}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_root="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=guard-sync-manifest.sh
source "$SCRIPT_DIR/guard-sync-manifest.sh"

if ! target="$(git -C "$target_input" rev-parse --show-toplevel 2>/dev/null)"; then
  echo "skip: not a git repo: $target_input" >&2
  exit 0
fi

# Fail-closed: scan workspace siblings before any overwrite (GUARD_SYNC_E_DIVERGENCE).
if [[ "${GUARD_SYNC_SKIP_DIVERGENCE_CHECK:-0}" != "1" ]]; then
  if [[ ! -x "$SCRIPT_DIR/check-guard-sync-divergence.sh" ]]; then
    echo "error: check-guard-sync-divergence.sh missing or not executable" >&2
    exit 1
  fi
  WORKSPACE_ROOT="${WORKSPACE_ROOT:-$(cd "$source_root/.." && pwd)}" \
    bash "$SCRIPT_DIR/check-guard-sync-divergence.sh" --workspace || exit 1
fi

# Abort if canonical or target has uncommitted changes to any path we would overwrite.
# Prevents sync from silently dropping local harmonization work.
guard_sync_dirty_paths() {
  local root="$1"
  local label="$2"
  local rel dest
  local -a paths=()

  for rel in "${GUARD_SYNC_EXECUTABLES[@]}" "${GUARD_SYNC_DATA_FILES[@]}"; do
    paths+=("scripts/git/$rel")
  done
  for rel in append-pr-body.sh; do
    paths+=("scripts/cursor/$rel")
  done
  for rel in pr.md; do
    paths+=(".cursor/commands/$rel")
  done
  for rel in no-commit-attribution.mdc never-undo-attribution-expunge.mdc append-only-pr-body.mdc \
    banned-attribution-local.mdc zero-banned-attribution-everywhere.mdc; do
    paths+=(".cursor/rules/$rel")
  done

  local dirty=""
  for rel in "${paths[@]}"; do
    dest="$root/$rel"
    [[ -e "$dest" || -f "$source_root/$rel" || -f "$SCRIPT_DIR/${rel#scripts/git/}" ]] || continue
    if git -C "$root" status --porcelain -- "$rel" 2>/dev/null | grep -q .; then
      dirty+=$'\n'"  $rel"
    fi
  done
  if [[ -n "$dirty" ]]; then
    echo "error: $label has uncommitted changes to guard-sync paths — harmonize first, then sync:" >&2
    printf '%s\n' "$dirty" >&2
    echo "  Do NOT run sync-attribution-guard-scripts.sh until these are committed or intentionally discarded." >&2
    return 1
  fi
  return 0
}

# GUARD_SYNC_ON_DIRTY=skip — cloud install/start: warn and skip overwrite (exit
# GUARD_SYNC_EXIT_DIRTY_SKIP) instead of failing the whole VM boot when agent
# worktrees are mid-PR dirty.
_guard_sync_abort_if_dirty() {
  local root="$1"
  local label="$2"
  if guard_sync_dirty_paths "$root" "$label"; then
    return 0
  fi
  if [[ "${GUARD_SYNC_ON_DIRTY:-fail}" == "skip" ]]; then
    echo "warn: skipping sync for $label (GUARD_SYNC_ON_DIRTY=skip; dirty guard-sync paths preserved)" >&2
    exit "${GUARD_SYNC_EXIT_DIRTY_SKIP:-2}"
  fi
  exit 1
}

_guard_sync_abort_if_dirty "$source_root" "canonical repo ($source_root)"
if [[ "$(cd "$source_root" && pwd)" != "$(cd "$target" && pwd)" ]]; then
  _guard_sync_abort_if_dirty "$target" "target repo ($target)"
fi

atomic_install_file() {
  local src="$1"
  local dest="$2"
  local mode="$3"
  local dest_dir tmp

  dest_dir="$(dirname "$dest")"
  mkdir -p "$dest_dir"
  if [[ -L "$dest" || ( -e "$dest" && ! -f "$dest" ) ]]; then
    echo "error: $dest is not a safe regular-file destination (refusing to touch it)" >&2
    return 1
  fi
  if [[ -d "$dest" ]]; then
    echo "error: destination is a directory: $dest" >&2
    return 1
  fi
  tmp="$(mktemp "${dest_dir}/.$(basename "$dest").sync.XXXXXX")"
  if [[ -z "$tmp" || ! -f "$tmp" ]]; then
    echo "error: failed staging temp file for $dest" >&2
    return 1
  fi
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

atomic_write_file() {
  local dest="$1"
  local mode="$2"
  shift 2
  local dest_dir stage tmp

  dest_dir="$(dirname "$dest")"
  mkdir -p "$dest_dir"
  if [[ -L "$dest" || ( -e "$dest" && ! -f "$dest" ) ]]; then
    echo "error: $dest is not a safe regular-file destination (refusing to touch it)" >&2
    return 1
  fi
  tmp="$(mktemp)"
  if ! "$@" >"$tmp"; then
    rm -f "$tmp"
    echo "error: failed building $dest" >&2
    return 1
  fi
  stage="$(mktemp "${dest_dir}/.$(basename "$dest").sync.XXXXXX")"
  if ! install -m "$mode" "$tmp" "$stage"; then
    rm -f "$tmp" "$stage"
    echo "error: failed staging $dest" >&2
    return 1
  fi
  rm -f "$tmp"
  if ! mv -f "$stage" "$dest"; then
    rm -f "$stage"
    echo "error: failed writing $dest" >&2
    return 1
  fi
}

atomic_append_snippet() {
  local dest="$1"
  local mode="$2"
  local snippet="$3"
  local dest_dir stage tmp

  dest_dir="$(dirname "$dest")"
  mkdir -p "$dest_dir"
  if [[ ! -f "$snippet" ]]; then
    echo "error: snippet missing: $snippet" >&2
    return 1
  fi
  # dest must be either nonexistent or a regular file -- nothing else.
  # atomic_install_file() above already guards this exact case
  # (`[[ -d "$dest" ]]`); this function was simply missing the same
  # safety invariant its sibling in this file already established.
  # Broader here (-e && !-f, not just -d) to also catch device nodes,
  # FIFOs, and other non-regular-file types, not directories alone.
  #
  # Without this guard, `[[ -f "$dest" ]]` (checked below, decides
  # whether to preserve existing content) and the unconditional `mv -f
  # "$stage" "$dest"` at the end of this function (decides whether the
  # write succeeds) silently check two DIFFERENT things: -f is false
  # for a directory, so the function proceeds as if dest doesn't exist
  # yet -- but `mv` onto an *existing directory* doesn't fail or replace
  # it, it moves the source INTO that directory instead (POSIX mv
  # semantics, not a bug in mv). The net effect, traced end to end: the
  # function returns 0 (success), dest's real pre-existing content is
  # completely untouched, and a stray file with the staging temp-name
  # (e.g. .AGENTS.md.sync.XXXXXX) is silently dumped inside the
  # directory -- with nothing in the exit code or output to signal any
  # of this happened. Verified empirically, not assumed, before writing
  # this guard.
  if [[ -L "$dest" || ( -e "$dest" && ! -f "$dest" ) ]]; then
    echo "error: $dest exists but is not a regular file (refusing to touch it)" >&2
    return 1
  fi
  tmp="$(mktemp)"
  # Explicit per-command checks, not the brace group's own exit status --
  # `{ cat "$dest"; echo; cat "$snippet"; } >"$tmp"` only reports the exit
  # code of the LAST command in the group (cat "$snippet"), so a failing
  # `cat "$dest"` (e.g. dest unreadable, or a permissions issue) would go
  # undetected as long as the snippet cat still succeeds afterward --
  # silently producing a truncated $tmp missing dest's original content,
  # reported as success.
  if [[ -f "$dest" ]]; then
    if ! cat "$dest" >"$tmp"; then
      rm -f "$tmp"
      echo "error: failed reading $dest" >&2
      return 1
    fi
  else
    : >"$tmp"
  fi
  echo >>"$tmp"
  if ! cat "$snippet" >>"$tmp"; then
    rm -f "$tmp"
    echo "error: failed reading $snippet" >&2
    return 1
  fi
  stage="$(mktemp "${dest_dir}/.$(basename "$dest").sync.XXXXXX")"
  if ! install -m "$mode" "$tmp" "$stage"; then
    rm -f "$tmp" "$stage"
    echo "error: failed staging append for $dest" >&2
    return 1
  fi
  rm -f "$tmp"
  if ! mv -f "$stage" "$dest"; then
    rm -f "$stage"
    echo "error: failed appending to $dest" >&2
    return 1
  fi
}

for rel in "${GUARD_SYNC_EXECUTABLES[@]}"; do
  [[ -f "$SCRIPT_DIR/$rel" ]] || continue
  atomic_install_file "$SCRIPT_DIR/$rel" "$target/scripts/git/$rel" 0755
done

for rel in "${GUARD_SYNC_DATA_FILES[@]}"; do
  [[ -f "$SCRIPT_DIR/$rel" ]] || continue
  atomic_install_file "$SCRIPT_DIR/$rel" "$target/scripts/git/$rel" 0644
done

# Cursor Cloud agent helpers (orama canonical — synced to PT + AlphaClaw, not periscope).
for cursor_rel in \
  append-pr-body.sh \
  grant-pr-body-human-override.sh \
  pr-body-grant-lib.py; do
  [[ -f "$source_root/scripts/cursor/$cursor_rel" ]] || continue
  atomic_install_file \
    "$source_root/scripts/cursor/$cursor_rel" \
    "$target/scripts/cursor/$cursor_rel" \
    0755
done

for cursor_hook_rel in \
  hooks/pr-body-guard-core.py \
  hooks/pr-body-backup-lib.sh \
  hooks/before-shell-pr-body-guard.sh \
  hooks/before-mcp-pr-body-guard.sh; do
  [[ -f "$source_root/scripts/cursor/$cursor_hook_rel" ]] || continue
  atomic_install_file \
    "$source_root/scripts/cursor/$cursor_hook_rel" \
    "$target/scripts/cursor/$cursor_hook_rel" \
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
for rule in no-commit-attribution.mdc never-undo-attribution-expunge.mdc append-only-pr-body.mdc banned-attribution-local.mdc zero-banned-attribution-everywhere.mdc; do
  [[ -f "$source_root/.cursor/rules/$rule" ]] || continue
  atomic_install_file \
    "$source_root/.cursor/rules/$rule" \
    "$target/.cursor/rules/$rule" \
    0644
done

echo "synced guard scripts → $target"

snippet="$source_root/scripts/git/snippets/AGENTS-cursor-cloud-git.md"
if [[ -f "$snippet" ]]; then
  agents_md="$target/AGENTS.md"
  if [[ ! -f "$agents_md" ]]; then
    atomic_write_file "$agents_md" 0644 sh -c 'printf "%s\n\n" "# Agent instructions"; cat "$1"' _ "$snippet"
  elif ! grep -q 'apply-attribution-guard-all-repos' "$agents_md" 2>/dev/null; then
    atomic_append_snippet "$agents_md" 0644 "$snippet"
  fi
fi
