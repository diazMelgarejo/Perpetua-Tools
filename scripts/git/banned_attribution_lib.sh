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

banned_patterns_ready() {
  local f
  f="$(banned_patterns_file "${1:-}")"
  [[ -f "$f" && -s "$f" ]]
}

list_banned_pattern_tokens() {
  local f token
  f="$(banned_patterns_file "${1:-}")"
  if [[ ! -f "$f" ]]; then
    return 1
  fi
  while IFS= read -r token || [[ -n "$token" ]]; do
    token="${token%%#*}"
    token="$(printf '%s' "$token" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [[ -n "$token" ]] || continue
    printf '%s\n' "$token"
  done <"$f"
}

first_banned_pattern_token() {
  local f token
  f="$(banned_patterns_file "${1:-}")"
  if [[ ! -f "$f" ]]; then
    return 1
  fi
  while IFS= read -r token || [[ -n "$token" ]]; do
    token="${token%%#*}"
    token="$(printf '%s' "$token" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [[ -n "$token" ]] || continue
    printf '%s' "$token"
    return 0
  done <"$f"
  return 1
}

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
        key="$(printf '%s' "$key" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        value="${raw#*=}"
        value="$(printf '%s' "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
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

authorized_private_identity_hashes_file() {
  local root="${1:-}"
  if [[ -z "$root" ]]; then
    root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
  fi
  printf '%s/.github/authorized-private-identities.sha256' "$root"
}

sha256_text() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum | awk '{print $1}'
    return
  fi
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 | awk '{print $1}'
    return
  fi
  return 127
}

identity_fingerprint() {
  local name_lc="$1" email_lc="$2"
  printf '%s <%s>' "$name_lc" "$email_lc" | sha256_text
}

private_identity_fingerprint_ok() {
  local name_lc="$1" email_lc="$2" root="${3:-}" file digest expected
  file="$(authorized_private_identity_hashes_file "$root")"
  [[ -f "$file" ]] || return 1
  digest="$(identity_fingerprint "$name_lc" "$email_lc")" || return 1
  while IFS= read -r expected || [[ -n "$expected" ]]; do
    expected="${expected%%#*}"
    expected="$(printf '%s' "$expected" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [[ -n "$expected" ]] || continue
    [[ "$digest" == "$expected" ]] && return 0
  done <"$file"
  return 1
}
