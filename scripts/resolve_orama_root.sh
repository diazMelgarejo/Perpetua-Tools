#!/usr/bin/env bash
# Resolve the sibling orama-system checkout from Perpetua-Tools.
# Git repo-relative crawl only -- no hardcoded workstation layout paths.
#
# Thin wrapper over scripts/git/resolve_sibling_git_repo.sh's generic
# marker-based crawler. This is the reverse of orama-system's
# resolve_perp_harness.sh: Perpetua-Tools -> orama-system.
set -euo pipefail

_ROR_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_ROR_REPO_ROOT="$(cd "$_ROR_SELF_DIR" && git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -n "$_ROR_REPO_ROOT" && -f "$_ROR_REPO_ROOT/scripts/git/resolve_sibling_git_repo.sh" ]]; then
  # shellcheck source=git/resolve_sibling_git_repo.sh
  source "$_ROR_REPO_ROOT/scripts/git/resolve_sibling_git_repo.sh"
else
  echo "ERROR: resolve_sibling_git_repo.sh not found under repo root ${_ROR_REPO_ROOT:-<unresolved>}" >&2
  return 1 2>/dev/null || exit 1
fi

_ORAMA_MARKER="bin/orama-system/SKILL.md"
_RESOLVED_ORAMA_ROOT_CACHE=""

# resolve_orama_root resolves and prints the orama-system repository root.
# Memoizes into _RESOLVED_ORAMA_ROOT_CACHE so repeated calls in the same shell
# do not re-crawl.
resolve_orama_root() {
  if [[ -n "${_RESOLVED_ORAMA_ROOT_CACHE:-}" ]]; then
    echo "$_RESOLVED_ORAMA_ROOT_CACHE"
    return 0
  fi

  local override_rc=0 path parent mother orama_root
  path="$(sibling_repo_check_env_override "$_ORAMA_MARKER" \
    ORAMA_SYSTEM_PATH ORAMA_SYSTEM_ROOT ORAMA_ROOT)" || override_rc=$?
  if ((override_rc == 0)); then
    _RESOLVED_ORAMA_ROOT_CACHE="$(cd "$path" && pwd)"
    echo "$_RESOLVED_ORAMA_ROOT_CACHE"
    return 0
  elif ((override_rc == 2)); then
    # An explicit override was configured but none resolved to a valid,
    # non-symlinked orama-system git root. Fail closed rather than silently
    # crawling to a different checkout.
    return 1
  fi

  sibling_repo_reset_candidates
  parent="$(cd "$_ROR_REPO_ROOT/.." && pwd)"
  mother="$(cd "$_ROR_REPO_ROOT/../.." && pwd)"
  sibling_repo_crawl_collect "$parent" "$_ORAMA_MARKER" 2
  if [[ "$mother" != "$parent" ]]; then
    sibling_repo_crawl_collect "$mother" "$_ORAMA_MARKER" 2
  fi
  orama_root="$(sibling_repo_finalize "orama-system" || true)"
  if [[ -n "$orama_root" ]]; then
    _RESOLVED_ORAMA_ROOT_CACHE="$orama_root"
    echo "$_RESOLVED_ORAMA_ROOT_CACHE"
    return 0
  fi
  return 1
}
