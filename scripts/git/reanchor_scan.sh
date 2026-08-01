#!/usr/bin/env bash
# reanchor_scan.sh — canonical branch-state detector for rewritten histories.
#
# WHY THIS EXISTS (read before "fixing" branches):
#   When `main` is rewritten (squash-rebundle, filter-repo, expunge, force-push),
#   every pre-rewrite commit keeps its content but gets a NEW sha. After that,
#   `git rev-list --count`, ahead/behind, and `merge-base` are GRAPH-BY-SHA
#   proxies — they are MEANINGLESS across the rewrite boundary. A branch can read
#   "479 behind" while its tip is byte-identical to a commit already in main.
#   The only correct test is the TREE-TWIN: does the branch's tree (%T) match a
#   commit's tree in main? Two commits with the same %T are byte-identical
#   regardless of sha/author/message.
#
#   This is the trap behind the orama PR#70 "600 behind" incident AND the PT
#   re-scan repeat (2026-06-05). Canonical method: git-history-surgery
#   references/reanchor-after-rewrite.md (tree-twin scan — not ahead/behind).
#   https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/git-history-surgery/references/reanchor-after-rewrite.md
#
# Usage: reanchor_scan.sh <repo_path> [main_ref] [scope]
#   main_ref : reference for the rewritten history   (default: origin/main)
#   scope    : remotes | heads | all                 (default: remotes)
#              remotes = origin/* ; heads = local refs/heads/* ; all = both
set -u
REPO="${1:?usage: reanchor_scan.sh <repo_path> [main_ref] [scope]}"
MAINREF="${2:-origin/main}"
SCOPE="${3:-remotes}"
cd "$REPO" || { echo "cannot cd $REPO"; exit 2; }
export GIT_TERMINAL_PROMPT=0
TREES="$(mktemp -t main_trees.XXXXXX)"
trap 'rm -f "$TREES"' EXIT
echo "=========================================================="
echo "REPO: $REPO   (reference = $MAINREF, scope = $SCOPE)"
_TIMEOUT_BIN=$(command -v gtimeout 2>/dev/null || command -v timeout 2>/dev/null || echo "")
if [ -n "$_TIMEOUT_BIN" ]; then
  if ! "$_TIMEOUT_BIN" 90 git fetch --prune origin >/dev/null 2>&1; then
    echo "  FAIL: git fetch --prune origin failed (offline or timeout) — scan aborted"
    exit 3
  fi
else
  if ! git fetch --prune origin >/dev/null 2>&1; then
    echo "  FAIL: git fetch --prune origin failed (offline) — scan aborted"
    exit 3
  fi
fi
MAIN=$(git rev-parse "$MAINREF") || { echo "  no $MAINREF"; exit 0; }
ROOT=$(git rev-list --max-parents=0 "$MAIN" | tail -1)
git log "$MAIN" --format='%H %T' > "$TREES"
echo "  main=${MAIN:0:9}  root=${ROOT:0:9}"
echo "----------------------------------------------------------"

refs=""
case "$SCOPE" in
  remotes|all) refs="$refs $(git for-each-ref --format='%(refname:short)' refs/remotes/origin/ | grep -v 'origin/HEAD' | grep -v 'origin/main$')" ;;
esac
case "$SCOPE" in
  heads|all)   refs="$refs $(git for-each-ref --format='%(refname:short)' refs/heads/ | grep -v '^main$')" ;;
esac

for ref in $refs; do
  b="${ref#origin/}"
  tip=$(git rev-parse "$ref")
  # full first-parent walk to the deepest tree-twin — NO cap (a deeper-than-N
  # twin is exactly the false NO-TWIN a truncated scan would report).
  C=""; DT=""; above=0
  while read -r c; do
    [ -z "$c" ] && continue
    t=$(git rev-parse "${c}^{tree}")
    m=$(awk -v t="$t" '$2==t{print $1; exit}' "$TREES")
    if [ -n "$m" ]; then C="$c"; DT="$m"; break; fi
    above=$((above+1))
  done < <(git rev-list --first-parent "$tip")
  if [ -z "$DT" ]; then
    echo "  $ref  NO-TWIN (no tree match in $MAINREF) -> investigate"
    echo "        (verify with: git cherry -v $MAINREF $tip)"
  elif [ "$C" = "$tip" ]; then
    echo "  $ref  MERGED/in-main (tip twin ${DT:0:9}; work already in main)"
  else
    echo "  $ref  NEEDS-REANCHOR: graft $above unique commit(s) onto twin ${DT:0:9}"
    echo "        (verify which are truly missing:  git cherry -v $MAINREF $tip $C )"
  fi
done
