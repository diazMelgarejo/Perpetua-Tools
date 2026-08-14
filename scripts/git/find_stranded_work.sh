#!/usr/bin/env bash
# Report local-only branches, unpushed commits, and dirty worktrees across the
# current repo, sibling repos, and their linked worktrees. Read-only by design.
#
# Branch ahead counts below are a cheap local-upstream first pass for
# unpushed work only. They are not authoritative for post-rewrite
# merged/orphaned status; use scripts/git/reanchor_scan.sh for that.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/git/resolve_sibling_git_repo.sh
source "${SCRIPT_DIR}/resolve_sibling_git_repo.sh"

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
  local repo="$1" branch upstream ahead
  while IFS= read -r branch; do
    [[ -n "$branch" ]] || continue
    if ! upstream="$(git -C "$repo" rev-parse --abbrev-ref "${branch}@{u}" 2>/dev/null)"; then
      echo "  branch: ${branch}"
      echo "    issue: no-upstream"
      continue
    fi

    ahead="$(git -C "$repo" rev-list --count "${upstream}..${branch}" 2>/dev/null)" || ahead=0
    if [[ "$ahead" =~ ^[0-9]+$ ]] && ((ahead > 0)); then
      echo "  branch: ${branch}"
      echo "    issue: unpushed-${ahead}-commits"
      echo "    upstream: ${upstream}"
      echo "    note: raw upstream ahead count; use scripts/git/reanchor_scan.sh for post-rewrite merge/orphan classification"
      echo "    commits:"
      git -C "$repo" log --format='      %h %s' --reverse "${upstream}..${branch}" 2>/dev/null
    fi
  done < <(git -C "$repo" for-each-ref --format='%(refname:short)' refs/heads 2>/dev/null)
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
  local repo="$1" report
  report="$(
    print_branch_issues "$repo"
    print_worktree_issues "$repo"
  )"
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

  if ((any_found == 0)); then
    echo "No stranded work found."
  fi
}

main "$@"
