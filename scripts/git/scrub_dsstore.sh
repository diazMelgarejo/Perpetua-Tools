#!/usr/bin/env bash
# scrub_dsstore.sh — remove macOS .DS_Store metadata Finder drops inside .git/
#
# .gitignore cannot cover .git/ internals, so these junk files accumulate and
# trip repo_hygiene.py's "macOS metadata file inside git refs" gate, blocking
# commits/pushes. Runs early in the hook chain so hygiene never sees them.
# Safe: .DS_Store is never a valid git ref/object/log; deletion is non-destructive
# to repository data. Called from .githooks/pre-commit and .githooks/pre-push.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
GIT_DIR="$(git rev-parse --git-dir 2>/dev/null)" || exit 0

case "$GIT_DIR" in
  /*) abs_git="$GIT_DIR" ;;
  *)  abs_git="$ROOT/$GIT_DIR" ;;
esac

[ -d "$abs_git" ] || exit 0

# Delete .DS_Store inside .git/ only — never touches the working tree.
find "$abs_git" -name .DS_Store -type f -delete >/dev/null 2>&1 || true

exit 0
