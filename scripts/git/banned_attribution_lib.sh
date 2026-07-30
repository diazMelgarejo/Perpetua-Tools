#!/usr/bin/env bash
# Shared helpers for gitignored banned-attribution patterns (no literals in callers).
set -euo pipefail

banned_patterns_file() {
  local root="${1:-}"
  if [[ -z "$root" ]]; then
    root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
  fi
  local private="${root}/.cursor/private/banned-attribution-patterns"
  if [[ -f "$private" && -s "$private" ]]; then
    printf '%s' "$private"
    return 0
  fi
  local openclaw="${OPENCLAW_ATTRIBUTION_PATTERNS:-${HOME:-}/.cursor/openclaw/banned-attribution-patterns}"
  if [[ -f "$openclaw" && -s "$openclaw" ]]; then
    printf '%s' "$openclaw"
    return 0
  fi
  printf '%s' "$private"
}

# banned_patterns_ready reports whether a valid banned-attribution patterns file exists and is non-empty.
# banned_patterns_ready accepts an optional root directory argument used to resolve the patterns file; it exits with status 0 if the resolved file exists and has size > 0, non-zero otherwise.
banned_patterns_ready() {
  local f
  f="$(banned_patterns_file "${1:-}")"
  [[ -f "$f" && -s "$f" ]]
}

_trim_edges() {
  printf '%s' "$1" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

# list_banned_pattern_tokens streams banned-attribution pattern tokens (one per line) from the repository or user patterns file.
# It resolves the patterns file (optional `root` argument), reads it line-by-line, removes inline comments (`#`) and all whitespace, skips empty tokens, and writes each remaining token to stdout on its own line.
# Usage: while read -r token; do ...; done < <(list_banned_pattern_tokens "$root")
# Parameters:
#   root (optional) — repository root directory to use when resolving the patterns file; if omitted, the script determines the root automatically.
# Exit:
#   Returns non-zero if the resolved patterns file does not exist or cannot be read.
list_banned_pattern_tokens() {
  local f token
  f="$(banned_patterns_file "${1:-}")"
  if [[ ! -f "$f" ]]; then
    return 1
  fi
  while IFS= read -r token || [[ -n "$token" ]]; do
    token="${token%%#*}"
    token="$(_trim_edges "$token")"
    [[ -n "$token" ]] || continue
    printf '%s\n' "$token"
  done <"$f"
}

# first_banned_pattern_token outputs the first non-empty, non-comment banned-attribution pattern token from the resolved patterns file (takes an optional root directory argument).
# It prints the token to stdout and returns success; if no file or no token is found it returns a non-zero status.
first_banned_pattern_token() {
  local f token
  f="$(banned_patterns_file "${1:-}")"
  if [[ ! -f "$f" ]]; then
    return 1
  fi
  while IFS= read -r token || [[ -n "$token" ]]; do
    token="${token%%#*}"
    token="$(_trim_edges "$token")"
    [[ -n "$token" ]] || continue
    printf '%s' "$token"
    return 0
  done <"$f"
  return 1
}

# line_matches_banned_pattern checks whether a lowercased line contains any banned-attribution pattern token; tokens are lowercased before matching and are read from the resolved patterns file.
line_matches_banned_pattern() {
  local line_lc="$1"
  local root="${2:-}"
  local token token_lc
  while IFS= read -r token; do
    token_lc="$(printf '%s' "$token" | tr '[:upper:]' '[:lower:]')"
    if [[ "$line_lc" == *"$token_lc"* ]]; then
      return 0
    fi
  done < <(list_banned_pattern_tokens "$root" 2>/dev/null || true)
  return 1
}

openclaw_workspace_root() {
  local root="${1:-}"
  if [[ -z "$root" ]]; then
    root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
  fi
  local cur="$root"
  while [[ "$cur" != "/" && -n "$cur" ]]; do
    if [[ -d "$cur/orama-system" ]]; then
      printf '%s' "$cur"
      return 0
    fi
    cur="$(dirname "$cur")"
  done
  printf '%s' "$root"
}

verboten_literals_file() {
  local root="${1:-}"
  if [[ -n "${OPENCLAW_VERBOTEN_LITERALS:-}" ]]; then
    printf '%s' "$OPENCLAW_VERBOTEN_LITERALS"
    return 0
  fi
  printf '%s/.verboten-literals.local' "$(openclaw_workspace_root "$root")"
}

list_private_literal_values() {
  local root="${1:-}" selector="${2:-}" f raw key value
  f="$(verboten_literals_file "$root")"
  [[ -f "$f" ]] || return 1
  while IFS= read -r raw || [[ -n "$raw" ]]; do
    raw="${raw%%#*}"
    raw="$(printf '%s' "$raw" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [[ -n "$raw" ]] || continue
    case "$raw" in
      *=*)
        key="${raw%%=*}"
        value="${raw#"$key="}"
        value="$(_trim_edges "$value")"
        [[ -n "$value" ]] || continue
        [[ -z "$selector" || "$key" == "$selector" ]] || continue
        printf '%s\n' "$value"
        ;;
    esac
  done <"$f"
}

private_owner_email_ok() {
  local email_lc="$1" root="${2:-}" token token_lc
  while IFS= read -r token; do
    token_lc="$(printf '%s' "$token" | tr '[:upper:]' '[:lower:]')"
    [[ "$email_lc" == "$token_lc" ]] && return 0
  done < <(list_private_literal_values "$root" owner_gmail 2>/dev/null || true)
  return 1
}

private_owner_name_ok() {
  local name_lc="$1" root="${2:-}" token token_lc
  while IFS= read -r token; do
    token_lc="$(printf '%s' "$token" | tr '[:upper:]' '[:lower:]')"
    [[ "$name_lc" == *"$token_lc"* ]] && return 0
  done < <(list_private_literal_values "$root" owner_name 2>/dev/null || true)
  return 1
}

line_matches_private_forbidden_literal() {
  local line_lc="$1" root="${2:-}" token token_lc
  while IFS= read -r token; do
    token_lc="$(printf '%s' "$token" | tr '[:upper:]' '[:lower:]')"
    [[ "$line_lc" == *"$token_lc"* ]] && return 0
  done < <(list_private_literal_values "$root" forbidden_attribution 2>/dev/null || true)
  return 1
}

# banned_attribution_hit returns 0 when author/committer/body metadata matches a banned pattern.
banned_attribution_hit() {
  local ae_lc="$1" an_lc="$2" ce_lc="$3" cn_lc="$4" body_lc="$5"
  local root="${6:-}"
  local patterns_ready=0
  if banned_patterns_ready "$root"; then
    patterns_ready=1
  fi
  if [[ "$patterns_ready" -eq 1 ]]; then
    line_matches_banned_pattern "$ae_lc" "$root" && return 0
    line_matches_banned_pattern "$an_lc" "$root" && return 0
    line_matches_banned_pattern "$ce_lc" "$root" && return 0
    line_matches_banned_pattern "$cn_lc" "$root" && return 0
  fi
  line_matches_private_forbidden_literal "$ae_lc" "$root" && return 0
  line_matches_private_forbidden_literal "$an_lc" "$root" && return 0
  line_matches_private_forbidden_literal "$ce_lc" "$root" && return 0
  line_matches_private_forbidden_literal "$cn_lc" "$root" && return 0
  local line line_lc
  while IFS= read -r line; do
    line_lc="$(printf '%s' "$line" | tr '[:upper:]' '[:lower:]')"
    case "$line_lc" in
      co-authored-by:*)
        if [[ "$patterns_ready" -eq 1 ]] && line_matches_banned_pattern "$line_lc" "$root"; then
          return 0
        fi
        if line_matches_private_forbidden_literal "$line_lc" "$root"; then
          return 0
        fi
        ;;
    esac
  done <<< "$body_lc"
  return 1
}
