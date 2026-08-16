#!/usr/bin/env bash
# Report local-only branches, unpushed/unreanchored commits, and dirty
# worktrees across the current repo, sibling repos, and their linked
# worktrees. Read-only by design.
#
# Merged/orphaned classification uses scripts/git/reanchor_scan.sh's
# tree-twin scan, not ahead/behind counts or merge-base — both are
# meaningless once a repo's history has been rewritten (squash-rebundle,
# filter-repo, expunge, force-push). See reanchor_scan.sh's own header.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/git/resolve_sibling_git_repo.sh
source "${SCRIPT_DIR}/resolve_sibling_git_repo.sh"

# Set by print_branch_issues() when the tree-twin classification could not
# run for some repo (missing/unreadable scanner, scanner failure, or
# unresolved origin/main). main() uses this to fail closed: it must never
# print "No stranded work found." when a classification actually errored.
SCAN_HAD_ERRORS=0

die() {
  echo "ERROR: $*" >&2
  exit 1
}

abs_path_from() {
  local base="$1" path="$2"
  if [[ "$path" == /* ]]; then
    printf '%s\n' "$path"
  else
    (cd "${base}/${path}" 2>/dev/null && pwd) || return 1
  fi
}

repo_group_paths=()
repo_group_common_dirs=()

add_repo_group() {
  local repo="$1" common common_abs existing
  common="$(git -C "$repo" rev-parse --git-common-dir 2>/dev/null)" || return 0
  common_abs="$(abs_path_from "$repo" "$common")" || return 0

  if ((${#repo_group_common_dirs[@]} > 0)); then
    for existing in "${repo_group_common_dirs[@]}"; do
      [[ "$existing" == "$common_abs" ]] && return 0
    done
  fi

  repo_group_paths+=("$repo")
  repo_group_common_dirs+=("$common_abs")
}

is_target_repo() {
  local repo="$1" current_common="$2" common common_abs name
  common="$(git -C "$repo" rev-parse --git-common-dir 2>/dev/null)" || return 1
  common_abs="$(abs_path_from "$repo" "$common")" || return 1
  [[ "$common_abs" == "$current_common" ]] && return 0

  name="$(basename "$repo")"
  [[ "$name" == "Perpetua-Tools" || "$name" == "AlphaClaw" ]]
}

worktree_paths_for_repo() {
  local repo="$1" line path
  git -C "$repo" worktree list --porcelain 2>/dev/null | while IFS= read -r line; do
    case "$line" in
      worktree\ *)
        path="${line#worktree }"
        printf '%s\n' "$path"
        ;;
    esac
  done
}

worktree_label() {
  local wt="$1" branch
  if branch="$(git -C "$wt" symbolic-ref --quiet --short HEAD 2>/dev/null)"; then
    printf '%s\n' "$branch"
  else
    git -C "$wt" rev-parse --short HEAD 2>/dev/null || printf 'detached\n'
  fi
}

print_branch_issues() {
  local repo="$1" branch upstream reanchor_script reanchor_output reanchor_rc status_line branch_status detail
  reanchor_script="${SCRIPT_DIR}/reanchor_scan.sh"

  while IFS= read -r branch; do
    [[ -n "$branch" ]] || continue
    if ! upstream="$(git -C "$repo" rev-parse --abbrev-ref "${branch}@{u}" 2>/dev/null)"; then
      echo "  branch: ${branch}"
      echo "    issue: no-upstream"
    fi
  done < <(git -C "$repo" for-each-ref --format='%(refname:short)' refs/heads 2>/dev/null)

  # Merged/orphaned classification: tree-twin scan against origin/main, not
  # ahead/behind counts or merge-base — both are meaningless after a history
  # rewrite (see reanchor_scan.sh's own header for why).
  #
  # Fail CLOSED here, not open: a missing/unreadable scanner, a scanner
  # failure, or an unresolved origin/main must surface as a visible error
  # for this repo, never silent "nothing to report" -- the latter is
  # indistinguishable from "scan ran and found nothing", which would let
  # main() print the falsely reassuring "No stranded work found." for a
  # repo the scan never actually classified.
  if [[ ! -r "$reanchor_script" || ! -x "$reanchor_script" ]]; then
    echo "  ERROR: reanchor_scan.sh missing or not executable at ${reanchor_script} -- cannot classify merged/orphaned branches for ${repo}" >&2
    SCAN_HAD_ERRORS=1
    return 1
  fi

  # Capture output AND exit code directly (not via process substitution,
  # which discards $? in the calling shell) so a scanner failure -- fetch
  # timeout, bad repo path -- is never silently swallowed.
  reanchor_output="$(bash "$reanchor_script" "$repo" origin/main heads 2>&1)"
  reanchor_rc=$?
  if ((reanchor_rc != 0)); then
    echo "  ERROR: reanchor_scan.sh exited ${reanchor_rc} for ${repo} -- cannot classify merged/orphaned branches" >&2
    SCAN_HAD_ERRORS=1
    return 1
  fi
  # reanchor_scan.sh itself exits 0 even when origin/main doesn't resolve
  # (it prints "  no origin/main" and continues) -- that 0 is not proof the
  # scan actually ran, so check its output for that case explicitly.
  if [[ "$reanchor_output" == *"no origin/main"* ]]; then
    echo "  ERROR: reanchor_scan.sh could not resolve origin/main for ${repo} -- cannot classify merged/orphaned branches" >&2
    SCAN_HAD_ERRORS=1
    return 1
  fi

  while IFS= read -r status_line; do
    [[ "$status_line" =~ ^[[:space:]]+([^[:space:]]+)[[:space:]]+(NO-TWIN|NEEDS-REANCHOR)(.*)$ ]] || continue
    branch="${BASH_REMATCH[1]}"
    branch_status="${BASH_REMATCH[2]}"
    detail="${BASH_REMATCH[3]# }"
    echo "  branch: ${branch}"
    case "$branch_status" in
      NO-TWIN)
        echo "    issue: no-tree-twin-in-main"
        ;;
      NEEDS-REANCHOR)
        echo "    issue: needs-reanchor"
        ;;
    esac
    echo "    detail: ${branch_status}${detail}"
  done <<<"$reanchor_output"
}

print_worktree_issues() {
  local repo="$1" wt status branch
  while IFS= read -r wt; do
    [[ -n "$wt" ]] || continue
    status="$(git -C "$wt" status --short --untracked-files=normal 2>/dev/null)" || status=""
    if [[ -n "$status" ]]; then
      branch="$(worktree_label "$wt")"
      echo "  worktree: ${wt}"
      echo "    branch: ${branch}"
      echo "    issue: dirty-worktree"
      echo "    status:"
      sed 's/^/      /' <<<"$status"
    fi
  done < <(worktree_paths_for_repo "$repo")
}

print_repo_report() {
  # A $(...) command substitution forks a subshell, so calling
  # print_branch_issues() through one would lose its SCAN_HAD_ERRORS=1
  # mutation (subshell variable changes never propagate to the parent
  # shell). A brace group with plain output redirection does NOT fork a
  # subshell, so route both calls through a temp file instead to keep
  # SCAN_HAD_ERRORS visible in main().
  local repo="$1" report tmpfile
  tmpfile="$(mktemp)" || { echo "  ERROR: mktemp failed" >&2; SCAN_HAD_ERRORS=1; return 1; }
  {
    print_branch_issues "$repo"
    print_worktree_issues "$repo"
  } > "$tmpfile"
  report="$(cat "$tmpfile")"
  rm -f "$tmpfile"
  if [[ -n "$report" ]]; then
    echo "repo: ${repo}"
    printf '%s\n' "$report"
    return 0
  fi
  return 1
}

main() {
  local start_dir repo_root mother repo current_common current_common_abs any_found=0
  start_dir="${1:-$PWD}"
  repo_root="$(git -C "$start_dir" rev-parse --show-toplevel 2>/dev/null)" || die "not inside a git repository: ${start_dir}"
  mother="$(cd "${repo_root}/.." && pwd)" || die "cannot resolve workspace mother for ${repo_root}"
  current_common="$(git -C "$repo_root" rev-parse --git-common-dir 2>/dev/null)" || die "cannot resolve git common dir for ${repo_root}"
  current_common_abs="$(abs_path_from "$repo_root" "$current_common")" || die "cannot resolve absolute git common dir for ${repo_root}"

  sibling_repo_reset_candidates
  sibling_repo_crawl_collect "$mother" "" 2

  if ((${#_sibling_repo_candidates[@]} == 0)); then
    echo "No git repositories found under ${mother}"
    return 0
  fi

  for repo in "${_sibling_repo_candidates[@]}"; do
    if is_target_repo "$repo" "$current_common_abs"; then
      add_repo_group "$repo"
    fi
  done

  for repo in "${repo_group_paths[@]}"; do
    if print_repo_report "$repo"; then
      any_found=1
    fi
  done

  if ((SCAN_HAD_ERRORS != 0)); then
    echo "ERROR: one or more repos could not be classified -- see errors above. Not printing a clean result." >&2
    return 1
  fi

  if ((any_found == 0)); then
    echo "No stranded work found."
  fi
}

main "$@"
