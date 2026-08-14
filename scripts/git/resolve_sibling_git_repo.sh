#!/usr/bin/env bash
# resolve_sibling_git_repo.sh — generic, marker-based sibling git-repo discovery.
#
# Canonical in orama-system scripts/git/; synced byte-identical to
# Perpetua-Tools (and AlphaClaw, if it ever needs sibling discovery) via
# sync-repo-resolvers.sh. NEVER hand-edit a downstream copy — edit here,
# then re-run the sync script.
#
# Why this exists: multiple call sites need to find "the sibling repo" (orama
# looking for Perpetua-Tools, PT looking for orama-system, the guard-sync
# divergence check looking for every workspace repo) without hardcoding a
# fixed relative depth. A fixed-depth assumption breaks the moment a repo is
# nested one level deeper than expected — e.g. Perpetua-Tools lives at
# `<mother>/perplexity-api/Perpetua-Tools`, not `<mother>/Perpetua-Tools`, so
# a naive `$REPO_ROOT/../orama-system`-style default silently resolves to a
# path that doesn't exist. This crawler walks outward and validates each
# candidate against a marker file instead of trusting a guessed depth.
#
# Sourced by:
#   - bin/orama-system/skills/hermes-harness/scripts/resolve_perp_harness.sh
#     (orama -> Perpetua-Tools; marker: orchestrator/fastapi_app.py)
#   - Perpetua-Tools scripts/resolve_orama_root.sh (its synced counterpart;
#     Perpetua-Tools -> orama-system; marker: bin/orama-system/SKILL.md)
#   - check-guard-sync-divergence.sh --workspace (any-git-repo, empty marker)
set -uo pipefail

# sibling_repo_is_git_root <dir> <marker>
#   marker may be empty -- an empty marker only requires a non-symlinked
#   `.git`, used by callers that want "any git repo", not one specific one.
sibling_repo_is_git_root() {
  local d="${1%/}" marker="$2" resolved top
  [[ -n "$d" && -d "$d" ]] || return 1
  [[ -L "$d" ]] && return 1
  resolved="$(cd "$d" 2>/dev/null && pwd -P)" || return 1
  [[ -e "${resolved}/.git" ]] || return 1
  [[ -L "${resolved}/.git" ]] && return 1
  top="$(git -C "$resolved" rev-parse --show-toplevel 2>/dev/null)" || return 1
  top="$(cd "$top" 2>/dev/null && pwd -P)" || return 1
  [[ "$top" == "$resolved" ]] || return 1
  [[ -z "$marker" || -f "${resolved}/${marker}" ]]
}

_sibling_repo_candidates=()

sibling_repo_reset_candidates() {
  _sibling_repo_candidates=()
}

# sibling_repo_add_candidate <dir> <marker>
sibling_repo_add_candidate() {
  local d marker existing
  marker="$2"
  d="$(cd "${1%/}" 2>/dev/null && pwd)" || return 0
  sibling_repo_is_git_root "$d" "$marker" || return 0
  # Guard the [@] expansion: bash 3.2 (macOS system default) raises
  # "unbound variable" under `set -u` for "${arr[@]}" on an empty array,
  # even after an explicit `arr=()` -- ${#arr[@]} is safe unconditionally.
  if ((${#_sibling_repo_candidates[@]} > 0)); then
    for existing in "${_sibling_repo_candidates[@]}"; do
      [[ "$existing" == "$d" ]] && return 0
    done
  fi
  _sibling_repo_candidates+=("$d")
}

# sibling_repo_crawl_collect <base> <marker> [depth=2]
# Accumulates into _sibling_repo_candidates -- call sibling_repo_reset_candidates
# first if starting a fresh search (multiple crawls can accumulate on purpose,
# e.g. searching both a workspace mother dir and $HOME before finalizing).
sibling_repo_crawl_collect() {
  local base="${1%/}" marker="$2" depth="${3:-2}" d
  [[ -d "$base" ]] || return 0
  [[ -L "$base" ]] && return 0
  sibling_repo_add_candidate "$base" "$marker"
  if ((depth <= 0)); then
    return 0
  fi
  for d in "$base"/*/; do
    [[ -d "$d" ]] || continue
    [[ -L "$d" ]] && continue
    sibling_repo_add_candidate "$d" "$marker"
    sibling_repo_crawl_collect "$d" "$marker" $((depth - 1))
  done
}

# sibling_repo_finalize <label> -- prints the sole candidate, or errors on
# zero or multiple (ambiguous) matches.
sibling_repo_finalize() {
  local label="$1"
  if ((${#_sibling_repo_candidates[@]} == 0)); then
    return 1
  fi
  if ((${#_sibling_repo_candidates[@]} > 1)); then
    echo "ERROR: ambiguous ${label} roots (${#_sibling_repo_candidates[@]} marker-valid checkouts):" >&2
    printf '  %s\n' "${_sibling_repo_candidates[@]}" >&2
    return 1
  fi
  printf '%s\n' "${_sibling_repo_candidates[0]}"
}

# sibling_repo_check_env_override <marker> <var1> [var2...]
# Prints the resolved path and returns 0 if a valid override was found.
# Returns 1 if no listed var was set at all (caller should proceed to crawl).
# Returns 2 if a var WAS set but none resolved to a valid marker-matching git
# root -- callers must treat this as fail-closed (an explicit, broken
# override should error, not silently fall through to crawling and possibly
# resolving to the wrong repo).
sibling_repo_check_env_override() {
  local marker="$1"
  shift
  local var v any_set=""
  for var in "$@"; do
    v="${!var:-}"
    if [[ -n "$v" ]]; then
      any_set=1
      if sibling_repo_is_git_root "$v" "$marker"; then
        printf '%s\n' "$v"
        return 0
      fi
    fi
  done
  [[ -n "$any_set" ]] && return 2
  return 1
}

# resolve_sibling_repo_root <label> <marker> <search-root> [depth=2] [env_var...]
# One-shot convenience: env override check, then a single-source crawl+finalize.
# Callers needing multi-source accumulation (e.g. resolve_pt_root's
# mother-dir-then-$HOME search) should call the primitives above directly
# instead of this wrapper.
resolve_sibling_repo_root() {
  local label="$1" marker="$2" search_root="$3" depth="${4:-2}"
  shift 4 2>/dev/null || shift $#
  local override_rc=0 path
  if (($# > 0)); then
    path="$(sibling_repo_check_env_override "$marker" "$@")" || override_rc=$?
    if ((override_rc == 0)); then
      printf '%s\n' "$path"
      return 0
    elif ((override_rc == 2)); then
      return 1
    fi
  fi
  sibling_repo_reset_candidates
  sibling_repo_crawl_collect "$search_root" "$marker" "$depth"
  sibling_repo_finalize "$label"
}
