#!/usr/bin/env bash
# Co-authored-by policy: allow well-known public AI/helper attribution; block
# unattributable random @gmail.com co-authors (see docs/wiki/08-git-hygiene-and-branching.md).
set -euo pipefail

msg_file="${1:?commit message file required}"
[[ -f "$msg_file" ]] || { echo "ERROR: missing commit message file: $msg_file" >&2; exit 1; }
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# shellcheck source=banned_attribution_lib.sh
source "$SCRIPT_DIR/banned_attribution_lib.sh"

ALLOWED_EXACT_COAUTHOR_EMAILS=(
  cursoragent@cursor.com
  lawrence@bettermind.ph
  lawrence@cyre.me
  noreply@anthropic.com
  claude@anthropic.com
  kimi-agent@kimi.ai
  cloud-kimi-agent@kimi.ai
)

ALLOWED_GMAIL_COAUTHORS=(
  diazmelgarejo@gmail.com
)

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
  kimi.ai
)

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
  kimi
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
  private_owner_email_ok "$email_lc" "$REPO_ROOT" && return 0
  return 1
}

coauthor_line_ok() {
  local line_lc="$1"
  local email_lc=""
  if [[ "$line_lc" =~ \<([^>]+)\> ]]; then
    email_lc="$(printf '%s' "${BASH_REMATCH[1]}" | tr '[:upper:]' '[:lower:]')"
  fi

  if [[ -n "$email_lc" ]]; then
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
    return 1
  fi

  local marker
  for marker in "${WELL_KNOWN_COAUTHOR_NAME_MARKERS[@]}"; do
    if [[ "$line_lc" == *"$marker"* ]]; then
      return 0
    fi
  done
  private_owner_name_ok "$line_lc" "$REPO_ROOT" && return 0

  return 1
}

while IFS= read -r line || [[ -n "$line" ]]; do
  case "$line" in
    [Cc]o-[Aa]uthor*)
      line_lc="$(printf '%s' "$line" | tr '[:upper:]' '[:lower:]')"
      if line_matches_private_forbidden_literal "$line_lc" "$REPO_ROOT"; then
        echo "ERROR: Co-authored-by contains forbidden private attribution" >&2
        echo "  $line" >&2
        exit 1
      fi
      if ! coauthor_line_ok "$line_lc"; then
        echo "ERROR: Co-authored-by not on approved co-author policy:" >&2
        echo "  $line" >&2
        echo "Allowed: explicit allowlist, well-known public AI/vendor domains, or allowlisted gmail." >&2
        exit 1
      fi
      ;;
  esac
done < "$msg_file"

exit 0
