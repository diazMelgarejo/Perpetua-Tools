#!/usr/bin/env bash
# Co-authored-by policy: allow well-known public AI/helper attribution; block
# unattributable random @gmail.com co-authors (see docs/wiki/08-git-hygiene-and-branching.md).
set -euo pipefail

msg_file="${1:?commit message file required}"
[[ -f "$msg_file" ]] || { echo "ERROR: missing commit message file: $msg_file" >&2; exit 1; }

# Explicit allowlist entries (case-insensitive — stored lowercase, matched after tolower).
# Add any personal/org domain here that is NOT covered by WELL_KNOWN_COAUTHOR_DOMAIN_SUFFIXES.
# All Anthropic model variants (Claude Sonnet, Opus 4.8, Haiku, etc.) are explicitly authorized
# via noreply@anthropic.com — never ban by model tier.
ALLOWED_EXACT_COAUTHOR_EMAILS=(
  cursoragent@cursor.com
  lawrence@bettermind.ph
  lawrence@cyre.me
  noreply@anthropic.com
)

# Only these @gmail.com / @googlemail.com addresses may appear in Co-authored-by.
ALLOWED_GMAIL_COAUTHORS=(
  diazmelgarejo@gmail.com
)

# Public agent / vendor domains (match email domain or subdomain).
# Mainstream AI models and autonomous coding agents are allowed co-authors — the
# only hard ban is the VERBOTEN pattern (private pattern lib). Extend as new
# mainstream agents appear; keep in sync with scripts/git/check_identity.sh.
WELL_KNOWN_COAUTHOR_DOMAIN_SUFFIXES=(
  openai.com
  anthropic.com
  cursor.com
  cursor.sh
  google.com
  google.dev
  github.com
  microsoft.com
  azure.com
  perplexity.ai
  x.ai
  coderabbit.ai
  mistral.ai
  deepseek.com
  cohere.com
  meta.com
  sourcegraph.com
  devin.ai
  codeium.com
  nousresearch.com
)

# Match in Co-authored-by display name / address when domain alone is ambiguous.
# "claude" covers all tiers: Claude Opus 4.8, Sonnet 4.6, Haiku 4.5, Fable 5, etc.
# "opus" and "fable" added as explicit belt-and-suspenders entries for
# Claude Opus 4.8 and Claude Fable 5 (user-authorized 2026-07-02).
WELL_KNOWN_COAUTHOR_NAME_MARKERS=(
  codex
  claude
  opus
  fable
  anthropic
  cursor
  cursoragent
  gemini
  google
  copilot
  openai
  github
  microsoft
  perplexity
  grok
  coderabbit
  coderabbitai
  mistral
  deepseek
  cohere
  llama
  devin
  cody
  codeium
  windsurf
  qwen
  hermes
  nousresearch
)

email_domain_ok() {
  local email_lc="$1"
  local domain="${email_lc#*@}"
  [[ -z "$domain" ]] && return 1
  local suffix
  for suffix in "${WELL_KNOWN_COAUTHOR_DOMAIN_SUFFIXES[@]}"; do
    if [[ "$domain" == "$suffix" || "$domain" == *."$suffix" ]]; then
      return 0
    fi
  done
  return 1
}

gmail_allowed() {
  local email_lc="$1"
  local allowed
  for allowed in "${ALLOWED_GMAIL_COAUTHORS[@]}"; do
    if [[ "$email_lc" == "$allowed" ]]; then
      return 0
    fi
  done
  return 1
}

coauthor_line_ok() {
  local line_lc="$1"
  local email_lc=""
  if [[ "$line_lc" =~ \<([^>]+)\> ]]; then
    email_lc="$(printf '%s' "${BASH_REMATCH[1]}" | tr '[:upper:]' '[:lower:]')"
  fi

  if [[ -n "$email_lc" ]]; then
    # Email was parsed — gate on email policy only; never fall through to
    # marker check. A display name containing "hermes" or "nousresearch"
    # must not override a rejected email address.
    local exact
    for exact in "${ALLOWED_EXACT_COAUTHOR_EMAILS[@]}"; do
      if [[ "$email_lc" == "$exact" ]]; then
        return 0
      fi
    done
    if [[ "$email_lc" == *@gmail.com || "$email_lc" == *@googlemail.com ]]; then
      gmail_allowed "$email_lc"
      return $?
    fi
    if email_domain_ok "$email_lc"; then
      return 0
    fi
    # Email present but not in any allowlist — reject; do NOT fall to markers.
    return 1
  fi

  # No email parsed (display-name-only line) — accept if a known tool marker
  # appears anywhere in the lowercased line.
  local marker
  for marker in "${WELL_KNOWN_COAUTHOR_NAME_MARKERS[@]}"; do
    if [[ "$line_lc" == *"$marker"* ]]; then
      return 0
    fi
  done

  return 1
}

while IFS= read -r line || [[ -n "$line" ]]; do
  case "$line" in
    [Cc]o-[Aa]uthor*)
      line_lc="$(printf '%s' "$line" | tr '[:upper:]' '[:lower:]')"
      if ! coauthor_line_ok "$line_lc"; then
        echo "ERROR: Co-authored-by not on approved co-author policy:" >&2
        echo "  $line" >&2
        echo "Allowed: explicit allowlist (cursoragent@cursor.com), well-known public AI/vendor domains (openai.com, anthropic.com, cursor.com, …), or allowlisted gmail (diazMelgarejo@gmail.com, Lawrence@cyre.me)." >&2
        exit 1
      fi
      ;;
  esac
done < "$msg_file"

exit 0
