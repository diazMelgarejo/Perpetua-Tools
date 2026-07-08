#!/usr/bin/env bash
# worktree-bootstrap.sh — idempotent worktree setup for orama-system family
#
# Usage: scripts/worktree-bootstrap.sh <repo-path> <branch> <slug> [gbrain-source-id]
#
# Example:
#   scripts/worktree-bootstrap.sh \
#     ~/Documents/Terminal\ xCode/claude/OpenClaw/orama-system \
#     feat/my-feature \
#     2026-05-24-my-feature \
#     gstack-code-2159b4b9-595bce   # orama's current source (was 'orama-src' pre-2026-06-17; see gstack/SKILL.md table)
#
# Idempotent: safe to re-run. If worktree already exists, skips creation.
# See docs/v2/22-worktree-parallel-agents.md for full doctrine.

set -euo pipefail

# ── Args ─────────────────────────────────────────────────────────────────────
REPO_PATH="${1:?Usage: worktree-bootstrap.sh <repo-path> <branch> <slug> [gbrain-source-id]}"
BRANCH="${2:?Missing branch}"
SLUG="${3:?Missing slug}"

# Security: SLUG flows into a sourceable env file (.worktree-env) and a
# directory path. Reject anything that could escape shell quoting or path
# context: only [A-Za-z0-9._-] allowed (kebab-case slugs).
if [[ ! "$SLUG" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "ERROR: slug must match [A-Za-z0-9._-]+ (got: $SLUG)" >&2
  exit 1
fi
case "$SLUG" in
  -*|.|..) echo "ERROR: slug may not start with '-' or be '.'/'..' (got: $SLUG)" >&2; exit 1 ;;
esac
GBRAIN_SOURCE="${4:-}"   # optional; falls back to canonical's .gbrain-source

WORKTREE_HUB="$HOME/code/oramasys/worktrees"
WORKTREE_PATH="$WORKTREE_HUB/$SLUG"

# Resolve repo path (expand ~)
REPO_PATH="${REPO_PATH/#\~/$HOME}"

echo "═══════════════════════════════════════════════════"
echo " worktree-bootstrap.sh"
echo "  repo   : $REPO_PATH"
echo "  branch : $BRANCH"
echo "  slug   : $SLUG"
echo "  target : $WORKTREE_PATH"
echo "═══════════════════════════════════════════════════"

# ── Step 0: Sanity check ─────────────────────────────────────────────────────
if [ ! -d "$REPO_PATH/.git" ] && [ ! -f "$REPO_PATH/.git" ]; then
  echo "ERROR: $REPO_PATH is not a git repository" >&2
  exit 1
fi

cd "$REPO_PATH"

# ── Step 1: Pre-flight ───────────────────────────────────────────────────────
echo ""
echo "── Step 1: Pre-flight checks"

# Remove stale lock files (macOS Finder / interrupted git ops — Datum D5)
LOCK_COUNT=$(find .git -name "*.lock" 2>/dev/null | wc -l | tr -d ' ')
if [ "$LOCK_COUNT" -gt 0 ]; then
  echo "  Found $LOCK_COUNT stale .lock file(s) — removing..."
  find .git -name "*.lock" -delete
  echo "  ✓ Lock files removed"
else
  echo "  ✓ No stale lock files"
fi

# Check for orphan refs with spaces (blocks git fetch — Datum D1)
SPACE_REFS=$(find .git/refs -name "* *" 2>/dev/null || true)
if [ -n "$SPACE_REFS" ]; then
  echo "  WARNING: Orphan refs with spaces detected:"
  echo "$SPACE_REFS" | sed 's/^/    /'
  echo "  Fix: git update-ref -d \"refs/heads/<ref with space>\""
  echo "  Continuing (worktree add may still succeed with --no-checkout)..."
else
  echo "  ✓ No orphan refs with spaces"
fi

# ── Step 2: Create hub directory ─────────────────────────────────────────────
echo ""
echo "── Step 2: Ensure worktree hub exists"
mkdir -p "$WORKTREE_HUB"
echo "  ✓ $WORKTREE_HUB"

# ── Step 3: Assign port offset ───────────────────────────────────────────────
echo ""
echo "── Step 3: Assign port offset"

# Count existing worktrees (excluding main worktree) to determine index.
# `grep -v` exits 1 when EVERY line matches (i.e. zero worktrees besides the
# canonical one) — under `set -o pipefail` that aborts the whole script on
# the very first run in a repo with no other worktrees yet.
#
# IMPORTANT: a trailing `|| echo 0` on the whole pipeline does NOT work here
# — wc -l/tr still run to completion on the (empty) input `grep -v` passed
# through and already emit a correct "0" before the pipeline's own exit
# status is evaluated, so `|| echo 0` fires *in addition to* that output
# rather than replacing it, corrupting EXISTING into "0\n0" (confirmed via
# a real end-to-end run from a zero-worktree repo). The exit code must be
# neutralized at grep -v's own point in the pipe instead.
EXISTING=$(git worktree list --porcelain | grep "^worktree " | { grep -v "^worktree $REPO_PATH$" || true; } | wc -l | tr -d ' ')

# Check if this worktree already exists (idempotent: reuse its existing index)
EXISTING_ENTRY=$(git worktree list --porcelain | grep -A2 "^worktree $WORKTREE_PATH$" | grep "^branch" | head -1 || true)
if [ -n "$EXISTING_ENTRY" ]; then
  # Already registered — compute index from existing list position
  WT_INDEX=$(git worktree list --porcelain | grep "^worktree " | grep -v "^worktree $REPO_PATH$" | \
    grep -n "$WORKTREE_PATH" | cut -d: -f1 || echo "$EXISTING")
  WT_INDEX="${WT_INDEX:-$EXISTING}"
else
  WT_INDEX=$((EXISTING + 1))
fi

ENV_OFFSET=$((WT_INDEX * 100))

echo "  Worktree index : $WT_INDEX"
echo "  ENV_OFFSET     : $ENV_OFFSET"
echo "  Port map:"
echo "    AlphaClaw  : $((3000 + ENV_OFFSET))"
echo "    PT         : $((8000 + ENV_OFFSET))"
echo "    orama-api  : $((8001 + ENV_OFFSET))"
echo "    portal     : $((8002 + ENV_OFFSET))"

# ── Step 4: Create or attach worktree ────────────────────────────────────────
echo ""
echo "── Step 4: Create/attach worktree"

if [ -d "$WORKTREE_PATH" ]; then
  echo "  Worktree directory already exists at $WORKTREE_PATH"
  # Verify it's tracked by git
  if git worktree list --porcelain | grep -q "^worktree $WORKTREE_PATH$"; then
    echo "  ✓ Already registered in git worktree list — skipping creation"
  else
    echo "  WARNING: Directory exists but not tracked. Re-registering..."
    git worktree add --force "$WORKTREE_PATH" "$BRANCH" 2>/dev/null || \
      git worktree repair "$WORKTREE_PATH" 2>/dev/null || true
  fi
else
  # Create branch if it doesn't exist, otherwise attach
  if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    echo "  Branch '$BRANCH' exists — attaching"
    git worktree add "$WORKTREE_PATH" "$BRANCH"
  else
    echo "  Creating new branch '$BRANCH'"
    git worktree add "$WORKTREE_PATH" -b "$BRANCH"
  fi
  echo "  ✓ Worktree created"
fi

# ── Step 5: Write .gbrain-source ─────────────────────────────────────────────
echo ""
echo "── Step 5: Write .gbrain-source (Datum D2)"

if [ -n "$GBRAIN_SOURCE" ]; then
  echo "$GBRAIN_SOURCE" > "$WORKTREE_PATH/.gbrain-source"
  echo "  ✓ Pinned to: $GBRAIN_SOURCE"
elif [ -f "$REPO_PATH/.gbrain-source" ]; then
  cp "$REPO_PATH/.gbrain-source" "$WORKTREE_PATH/.gbrain-source"
  CANONICAL_SOURCE=$(cat "$REPO_PATH/.gbrain-source" | tr -d '[:space:]')
  echo "  ✓ Copied from canonical: $CANONICAL_SOURCE"
else
  echo "  WARNING: No gbrain-source provided and none found in canonical."
  echo "  Run: echo \"<source-id>\" > $WORKTREE_PATH/.gbrain-source"
  echo "  Or:  /sync-gbrain --full  inside the worktree to index and pin"
fi

# ── Step 6: macOS dedup .gitignore entries ────────────────────────────────────
echo ""
echo "── Step 6: macOS dedup .gitignore (Datum D6)"

GITIGNORE="$WORKTREE_PATH/.gitignore"
DEDUP_MARKER="# macOS dedup (worktree-bootstrap)"

if [ -f "$GITIGNORE" ] && grep -q "$DEDUP_MARKER" "$GITIGNORE" 2>/dev/null; then
  echo "  ✓ Already present — skipping"
else
  {
    echo ""
    echo "$DEDUP_MARKER"
    echo "*\ 2/"
    echo "*\ 2.*"
    echo "*\ 3/"
    echo "*\ 3.*"
  } >> "$GITIGNORE"
  echo "  ✓ Added dedup patterns to .gitignore"
fi

# ── Step 7: Write .worktree-env ───────────────────────────────────────────────
echo ""
echo "── Step 7: Write .worktree-env"

cat > "$WORKTREE_PATH/.worktree-env" <<ENV
# Auto-generated by worktree-bootstrap.sh — do not edit manually
# Source this file before starting services in this worktree:
#   source .worktree-env
# Note: SLUG already validated above (alphanumeric + ._- only); quoted
# defensively in case validation is ever loosened in the future.
WORKTREE_SLUG="$SLUG"
WORKTREE_INDEX="$WT_INDEX"
ENV_OFFSET="$ENV_OFFSET"
ALPHACLAW_PORT=$((3000 + ENV_OFFSET))
PT_PORT=$((8000 + ENV_OFFSET))
ORAMA_API_PORT=$((8001 + ENV_OFFSET))
ORAMA_PORTAL_PORT=$((8002 + ENV_OFFSET))
ENV

echo "  ✓ Written to $WORKTREE_PATH/.worktree-env"

# ── Step 8: Update .cursor/environment.json if present ───────────────────────
CURSOR_ENV="$WORKTREE_PATH/.cursor/environment.json"
if [ -f "$CURSOR_ENV" ] && command -v python3 >/dev/null 2>&1; then
  echo ""
  echo "── Step 8: Update .cursor/environment.json"
  python3 - <<PYEOF
import json, sys
path = "$CURSOR_ENV"
with open(path) as f:
    data = json.load(f)
env = data.get("env", {})
env["ALPHACLAW_PORT"] = "$((3000 + ENV_OFFSET))"
env["PORTAL_PORT"]    = "$((8002 + ENV_OFFSET))"
env["PT_PORT"]        = "$((8000 + ENV_OFFSET))"
data["env"] = env
with open(path, "w") as f:
    json.dump(data, f, indent=2)
print("  ✓ Updated port vars in .cursor/environment.json")
PYEOF
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo " ✅ Worktree ready: $WORKTREE_PATH"
echo "    Branch     : $BRANCH"
echo "    ENV_OFFSET : $ENV_OFFSET"
echo ""
echo "    Next steps:"
echo "    1. cd $WORKTREE_PATH"
echo "    2. source .worktree-env        (sets port vars)"
echo "    3. Do your work"
echo "    4. BEFORE committing docs/plans, run:"
echo "       python3 scripts/review/repo_hygiene.py ."
echo "       Must exit 0 — catches machine-specific paths, banned"
echo "       terms, hidden Unicode, and docs/v2 ordinal collisions."
echo ""
echo "    ⚠  Adding a docs/v2/NN-*.md file? Coordinate with parallel agents:"
echo "       ls docs/v2/ | grep '^[0-9]' | sort -V | tail -1   # highest existing"
echo "       grep 'Next free slot' docs/v2/README.md           # reserved next slot"
echo "       Update the README.md 'Next free slot' line FIRST, commit it, then"
echo "       write your doc — git conflict on that line = collision signal."
echo ""
echo "    5. Invoke finishing-a-development-branch when done"
echo "═══════════════════════════════════════════════════"
