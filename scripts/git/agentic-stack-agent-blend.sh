#!/usr/bin/env bash
# agentic-stack-agent-blend.sh — replay unique .agent/ innovations across an
# agentic-stack submodule pin bump, the same way AlphaClaw replays
# feature/MacOS-post-install across upstream syncs.
#
# AlphaClaw precedent (see .agent/memory/semantic/lessons.jsonl
# lesson_881de77084d5, lesson_9fffe4530a95, docs/wiki/08-macos-alphaclaw-compat.md):
#   - upstream always prevails on the integration line; local customizations
#     never get overwritten wholesale -- they're on the RECEIVING end of a
#     merge, not the source, and the merge is union (never delete, harmonize).
#   - patches are idempotent: a `detect` marker (already-applied) and an
#     `old` marker (target) decide whether to (re)apply, so upstream
#     overwriting the file (npm install / a submodule bump) self-heals.
#
# `.agent/` isn't its own branch (it's a tracked directory inside PT, not a
# submodule), so the git-native equivalent of "reverse-merge" here is a
# 3-way FILE merge per doc 41 §7's per-file-class rules:
#   base  = vendor/agentic-stack content at the SHA .agent/ was last blended
#           from (recorded in .agent/.agentic-stack-blend-state.json;
#           v0.9.0 / db4e6b0 the first time -- see .agent/install.json)
#   ours  = PT's current .agent/<path>       (our innovations)
#   theirs = vendor/agentic-stack content at the NEW pinned SHA (upstream)
# `git merge-file -p base ours theirs` unions cleanly whenever upstream and
# PT touched different lines; conflicts are reported, never silently
# resolved, and NEVER written directly into a tracked .agent/ file -- always
# staged under .agent/.blend-preview/ for human review first.
#
# Per doc 41 §5, Brain-integration paths are permanently blocked: never
# staged, never merged, regardless of diff cleanliness.
#
# Workflow:
#   agentic-stack-agent-blend.sh status   # base vs target SHA, file categories
#   agentic-stack-agent-blend.sh plan     # per-file strategy, no writes
#   agentic-stack-agent-blend.sh apply    # stage clean merges + new files
#                                          # under .agent/.blend-preview/
#   agentic-stack-agent-blend.sh promote  # human has reviewed the preview;
#                                          # copy it into real .agent/ paths
#                                          # and advance the blend-state base
set -euo pipefail

REPO="$(git rev-parse --show-toplevel)"
SUB="$REPO/vendor/agentic-stack"
AGENT_DIR="$REPO/.agent"
STATE_FILE="$AGENT_DIR/.agentic-stack-blend-state.json"
PREVIEW_DIR="$AGENT_DIR/.blend-preview"

die() { echo "agentic-stack-agent-blend: $*" >&2; exit 1; }
[ -d "$SUB/.git" ] || [ -f "$SUB/.git" ] || die "submodule not initialized at vendor/agentic-stack"

# Paths blocked per doc 41 §5 -- never staged, never merged, no exceptions.
BLOCKLIST_PREFIXES=(
  ".agent/tools/brain_bridge.py"
  ".agent/skills/brain/"
)

_is_blocked() {
  local rel="$1" prefix
  for prefix in "${BLOCKLIST_PREFIXES[@]}"; do
    case "$rel" in
      "$prefix"*) return 0 ;;
    esac
  done
  return 1
}

_init_state_if_missing() {
  [ -f "$STATE_FILE" ] && return 0
  local base_sha
  base_sha="$(git -C "$SUB" rev-list -n1 v0.9.0 2>/dev/null || echo "")"
  [ -n "$base_sha" ] || die "could not resolve v0.9.0 in vendor/agentic-stack"
  python3 - "$STATE_FILE" "$base_sha" <<'PYEOF'
import json, sys
state_file, base_sha = sys.argv[1], sys.argv[2]
json.dump({
    "schema_version": 1,
    "base_sha": base_sha,
    "base_version": "v0.9.0",
    "note": "base is PT .agent/'s original scaffold version (see .agent/install.json); never been blended since",
    "last_blend": {"at": None, "target_sha": None, "applied_clean": [], "conflicts": [], "staged_new": [], "skipped_blocked": []},
}, open(state_file, "w", encoding="utf-8"), indent=2)
print(f"initialized {state_file} at base {base_sha[:8]} (v0.9.0)")
PYEOF
}

_base_sha() { python3 -c "import json; print(json.load(open('$STATE_FILE', encoding='utf-8'))['base_sha'])"; }
_target_sha() { git -C "$SUB" rev-parse HEAD; }

# Enumerate the dry-run delta from harness_manager, categorized by kind
# (+ new, ~ modified) and relative .agent/ path.
_dry_run_files() {
  export AGENTIC_STACK_ROOT="$SUB"
  export PYTHONPATH="$SUB${PYTHONPATH:+:$PYTHONPATH}"
  local raw
  if ! raw="$(python3 -m harness_manager.cli upgrade --dry-run "$REPO" 2>&1)"; then
    echo "agentic-stack-agent-blend: upgrade --dry-run failed:" >&2
    printf '%s\n' "$raw" >&2
    return 1
  fi
  printf '%s\n' "$raw" \
    | grep -E '^[[:space:]]*[+~][[:space:]]+\.agent/' \
    | sed -E 's/^[[:space:]]*([+~])[[:space:]]+(\.agent\/.*)$/\1 \2/'
}

cmd_status() {
  _init_state_if_missing
  local base target
  base="$(_base_sha)"
  target="$(_target_sha)"
  echo "blend base (last replayed from): $base ($(git -C "$SUB" describe --tags "$base" 2>/dev/null || echo '?'))"
  echo "vendor pin (target):             $target ($(git -C "$SUB" describe --tags "$target" 2>/dev/null || echo '?'))"
  if [ "$base" = "$target" ]; then
    echo "status: up to date -- nothing to blend"
    return 0
  fi
  echo ""
  echo "flagged .agent/ files:"
  _dry_run_files | while IFS=' ' read -r kind rel; do
    if _is_blocked "$rel"; then
      echo "  BLOCKED   $rel  (doc 41 §5 -- never staged)"
    elif [ "$kind" = "+" ]; then
      echo "  NEW       $rel  (review before adding)"
    else
      echo "  MODIFIED  $rel  (3-way merge candidate)"
    fi
  done
}

cmd_plan() {
  cmd_status
  echo ""
  echo "plan: 'apply' will attempt a clean 3-way merge for each MODIFIED file"
  echo "      (base=vendor@\$(base sha), ours=.agent/ now, theirs=vendor@\$(target sha))"
  echo "      and stage NEW files for review -- all under .agent/.blend-preview/,"
  echo "      never written directly into .agent/. Nothing is promoted until"
  echo "      you run 'promote' after reviewing the preview."
}

cmd_apply() {
  _init_state_if_missing
  local base target
  base="$(_base_sha)"
  target="$(_target_sha)"
  [ "$base" != "$target" ] || { echo "apply: already up to date"; return 0; }

  # Capture via command substitution (not process substitution) so a
  # non-zero exit from _dry_run_files (upgrade --dry-run failed) is checked
  # explicitly here -- `done < <(_dry_run_files)` would otherwise discard the
  # exit status and the failure would silently look like "nothing to blend".
  local dry_run_lines
  dry_run_lines="$(_dry_run_files)" || die "upgrade --dry-run failed -- see output above; nothing staged"

  rm -rf "$PREVIEW_DIR"
  mkdir -p "$PREVIEW_DIR"

  local clean=() conflicts=() staged_new=() skipped=()

  while IFS=' ' read -r kind rel; do
    [ -n "${rel:-}" ] || continue
    if _is_blocked "$rel"; then
      skipped+=("$rel")
      continue
    fi
    local sub_rel="${rel#.agent/}"
    local dest="$PREVIEW_DIR/${rel#.agent/}"
    mkdir -p "$(dirname "$dest")"

    if [ "$kind" = "+" ]; then
      # New upstream file -- stage for review, never auto-add.
      if git -C "$SUB" cat-file -e "$target:.agent/$sub_rel" 2>/dev/null; then
        git -C "$SUB" show "$target:.agent/$sub_rel" > "$dest"
        staged_new+=("$rel")
      fi
      continue
    fi

    # Modified file -- 3-way merge: base (old vendor) / ours (PT current) / theirs (new vendor).
    local ours="$AGENT_DIR/$sub_rel"
    [ -f "$ours" ] || { echo "  WARN: $rel flagged modified but missing in .agent/ -- treating as new"; \
      git -C "$SUB" show "$target:.agent/$sub_rel" > "$dest" 2>/dev/null && staged_new+=("$rel"); continue; }

    local base_tmp theirs_tmp
    base_tmp="$(mktemp)"; theirs_tmp="$(mktemp)"
    git -C "$SUB" show "$base:.agent/$sub_rel" > "$base_tmp" 2>/dev/null || : > "$base_tmp"
    git -C "$SUB" show "$target:.agent/$sub_rel" > "$theirs_tmp" 2>/dev/null || : > "$theirs_tmp"

    if git merge-file -p "$ours" "$base_tmp" "$theirs_tmp" > "$dest" 2>/dev/null; then
      clean+=("$rel")
    else
      conflicts+=("$rel")
      echo "  CONFLICT  $rel  (preview has <<<<<<< markers -- resolve by hand before promote)"
    fi
    rm -f "$base_tmp" "$theirs_tmp"
  done <<< "$dry_run_lines"

  echo "apply: staged under ${PREVIEW_DIR#$REPO/}/"
  echo "  clean merges:     ${#clean[@]}"
  echo "  conflicts:        ${#conflicts[@]}"
  echo "  new (for review): ${#staged_new[@]}"
  echo "  blocked/skipped:  ${#skipped[@]}"
  [ "${#skipped[@]}" -gt 0 ] && printf '    - %s\n' "${skipped[@]}"
  echo ""
  echo "next: review ${PREVIEW_DIR#$REPO/}/, then run 'promote' to copy accepted"
  echo "      files into .agent/ and advance the blend-state base to $target"
}

cmd_promote() {
  [ -d "$PREVIEW_DIR" ] || die "no preview to promote -- run 'apply' first"
  local target
  target="$(_target_sha)"
  local n=0
  local promoted=() unresolved=()
  while IFS= read -r -d '' f; do
    local rel="${f#$PREVIEW_DIR/}"
    if grep -q '^<<<<<<<' "$f" 2>/dev/null; then
      echo "  SKIP (unresolved conflict markers): $rel"
      unresolved+=("$rel")
      continue
    fi
    mkdir -p "$AGENT_DIR/$(dirname "$rel")"
    cp "$f" "$AGENT_DIR/$rel"
    echo "  promoted: .agent/$rel"
    promoted+=("$rel")
    n=$((n + 1))
  # Excludes __pycache__ -- bytecode cache is never real .agent/ content;
  # a stray manual `py_compile`/import against a preview file leaves a
  # .pyc sibling that a blind file-walk would otherwise promote and record
  # in the blend catalog as if it were blended source.
  done < <(find "$PREVIEW_DIR" -type f -not -path '*/__pycache__/*' -print0)

  echo "promote: $n file(s) copied into .agent/"

  # Always record the attempt (audit trail), regardless of whether the base
  # advances -- mirrors the AlphaClaw session-checklist discipline of never
  # leaving a blend's outcome undocumented.
  local at promoted_json unresolved_json
  at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  promoted_json="$(printf '%s\n' "${promoted[@]-}" | python3 -c "import json,sys; print(json.dumps([l.rstrip() for l in sys.stdin if l.strip()]))")"
  unresolved_json="$(printf '%s\n' "${unresolved[@]-}" | python3 -c "import json,sys; print(json.dumps([l.rstrip() for l in sys.stdin if l.strip()]))")"
  python3 - "$STATE_FILE" "$target" "$at" "${#unresolved[@]}" "$promoted_json" "$unresolved_json" <<'PYEOF'
import json, sys
state_file, target, at, n_unresolved, promoted_json, unresolved_json = sys.argv[1:7]
state = json.load(open(state_file, encoding="utf-8"))
promoted = json.loads(promoted_json)
state["last_blend"] = {
    "at": at,
    "target_sha": target,
    "applied_clean": promoted,
    "conflicts": json.loads(unresolved_json),
}
# Only advance the recorded base when nothing is left unresolved AND at
# least one file was actually promoted -- an empty promote (nothing staged,
# e.g. everything was blocked/skipped) must not silently mark the base as
# blended, or the next cycle would diff from the wrong base and drop
# upstream's intervening changes.
if int(n_unresolved) == 0 and promoted:
    state["base_sha"] = target
json.dump(state, open(state_file, "w", encoding="utf-8"), indent=2)
PYEOF

  if [ "${#unresolved[@]}" -gt 0 ]; then
    echo ""
    echo "blend-state base NOT advanced: ${#unresolved[@]} file(s) still have unresolved"
    echo "conflicts, so they were not blended at $target. Advancing the base anyway"
    echo "would mark them blended when they aren't, and the next blend cycle would"
    echo "diff from the wrong base and silently drop upstream's intervening changes."
    echo "Resolve the markers in .agent/.blend-preview/, re-run 'promote', or run"
    echo "'apply' again after manually editing the conflicted .agent/ files, then"
    echo "promote once every flagged file is clean:"
    printf '  - %s\n' "${unresolved[@]}"
    return 0
  fi
  if [ "${#promoted[@]}" -eq 0 ]; then
    echo ""
    echo "blend-state base NOT advanced: nothing was actually promoted (preview"
    echo "was empty -- everything blocked/skipped, or 'apply' hasn't been re-run"
    echo "since the last promote). Nothing to record as blended at $target."
    return 0
  fi
  echo "blend-state base advanced to ${target:0:8} (last_blend recorded, $at)"
  echo "  next: review with git status/diff, then git add .agent/ && git commit"
}

case "${1:-help}" in
  status) cmd_status ;;
  plan) cmd_plan ;;
  apply) cmd_apply ;;
  promote) cmd_promote ;;
  *) grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//' ;;
esac
