#!/usr/bin/env bash
# =============================================================================
# scripts/security/verify-egress-pf-rules.sh
# Layer-3 macOS pf (Packet Filter) egress enforcement floor verification
#
# Asserts the anchor file exists, rules match expected hash/content,
# and (in non-skip mode) anchor is loaded in pfctl.
# Returns 0 on success, non-zero on failure with clear warning.
# Reference: orama-system docs/v2/54-tri-stack-observability-and-l3-egress-v2.md § 2
# =============================================================================
set -euo pipefail

ANCHOR_FILE="${PF_ANCHOR_FILE:-/etc/pf.anchors/com.perpetua-tools.egress-deny}"
ANCHOR_NAME="com.perpetua-tools.egress-deny"
PFCTL_SKIP="${PFCTL_SKIP:-0}"

# Non-macOS hosts pass verification cleanly
if [[ "$(uname -s 2>/dev/null || echo Unknown)" != "Darwin" ]]; then
  echo "Non-macOS host ($(uname -s)) — pf verification skipped."
  exit 0
fi

# 1. Check anchor file existence
if [[ ! -f "$ANCHOR_FILE" ]]; then
  echo "WARN: pf egress anchor file missing at $ANCHOR_FILE" >&2
  exit 1
fi

# 2. Check rule content integrity / drift -- exact, ordered comparison, not
# substring presence. A rule like `pass out quick all` inserted BEFORE the
# required block rules would make every required-rule string still present
# in the file (passing a naive grep-per-rule check) while `quick`'s
# first-match semantics mean the block rules below it are never reached.
REQUIRED_RULES=(
  "block drop out quick to 169.254.0.0/16"
  "block drop out quick to 169.254.169.254"
  "block drop out quick to fd00:ec2::254"
  "block drop out quick to fe80::/10"
)

# Extract only actual rule lines: strip comments and blank lines, so
# comment-text differences (which don't affect enforcement) don't fail
# verification, but any extra/reordered/unexpected RULE line does.
# Use a while-read loop (not mapfile) so this script runs on macOS's
# default /bin/bash 3.2 as well as Homebrew bash 4+.
ACTUAL_RULE_LINES=()
while IFS= read -r line; do
  ACTUAL_RULE_LINES+=("$line")
done < <(grep -vE '^\s*(#.*)?$' "$ANCHOR_FILE" 2>/dev/null || true)

if [[ "${#ACTUAL_RULE_LINES[@]}" -ne "${#REQUIRED_RULES[@]}" ]]; then
  echo "WARN: pf egress anchor has ${#ACTUAL_RULE_LINES[@]} rule line(s), expected exactly ${#REQUIRED_RULES[@]} -- possible drift or an inserted/removed rule" >&2
  exit 2
fi

for i in "${!REQUIRED_RULES[@]}"; do
  if [[ "${ACTUAL_RULE_LINES[$i]}" != "${REQUIRED_RULES[$i]}" ]]; then
    echo "WARN: pf egress anchor rule order/content mismatch at position $((i + 1)): expected '${REQUIRED_RULES[$i]}', got '${ACTUAL_RULE_LINES[$i]}'" >&2
    exit 2
  fi
done

# 3. Check pfctl loaded rules and parent-anchor attachment, unless test-skipped
if [[ "$PFCTL_SKIP" -ne 1 ]]; then
  # 3a. Check if PF is actively enabled in kernel
  PF_INFO="$(pfctl -s info 2>/dev/null || true)"
  if ! echo "$PF_INFO" | grep -qi "Status: Enabled"; then
    echo "WARN: pf packet filtering is not enabled in kernel (run sudo pfctl -e)" >&2
    exit 3
  fi

  # 3b. Check loaded anchor rules match required rules
  LOADED_RAW="$(pfctl -a "$ANCHOR_NAME" -s rules 2>/dev/null || true)"
  LOADED_RULE_LINES=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && LOADED_RULE_LINES+=("$line")
  done < <(echo "$LOADED_RAW" | grep -vE '^\s*(#.*)?$' || true)

  if [[ "${#LOADED_RULE_LINES[@]}" -ne "${#REQUIRED_RULES[@]}" ]]; then
    echo "WARN: pf anchor $ANCHOR_NAME loaded rules (${#LOADED_RULE_LINES[@]}) do not match expected count (${#REQUIRED_RULES[@]})" >&2
    exit 3
  fi

  for i in "${!REQUIRED_RULES[@]}"; do
    if [[ "${LOADED_RULE_LINES[$i]}" != "${REQUIRED_RULES[$i]}" ]]; then
      echo "WARN: pf anchor $ANCHOR_NAME loaded rule mismatch at position $((i + 1)): expected '${REQUIRED_RULES[$i]}', got '${LOADED_RULE_LINES[$i]}'" >&2
      exit 3
    fi
  done

  # 3c. Check anchor attachment and rule ordering in root ruleset (pf.conf)
  ROOT_RULES="$(pfctl -sr 2>/dev/null || true)"
  if ! echo "$ROOT_RULES" | grep -qF "anchor \"$ANCHOR_NAME\""; then
    echo "WARN: pf anchor $ANCHOR_NAME is loaded but not attached in the root ruleset -- it will never be evaluated (run sudo bash scripts/security/install-egress-pf-rules.sh)" >&2
    exit 4
  fi

  # 3d. Check rule ordering: assert no broad 'pass out quick' rule precedes the anchor in root ruleset
  ORDERING_VIOLATION=0
  VIOLATING_RULE=""
  while IFS= read -r rule_line; do
    if echo "$rule_line" | grep -qF "anchor \"$ANCHOR_NAME\""; then
      break
    fi
    # Any outbound pass rule with the quick modifier before the anchor can
    # terminate evaluation before the anchor is reached. Match all common
    # spellings (bare quick, from/to any, interface-scoped) — not just the
    # narrow suffix set that misses `pass out quick from any to any`.
    if echo "$rule_line" | grep -qE '^\s*pass\s+out\b.*\bquick\b'; then
      ORDERING_VIOLATION=1
      VIOLATING_RULE="$rule_line"
      break
    fi
  done < <(echo "$ROOT_RULES" | grep -vE '^\s*(#.*)?$' || true)

  if [[ "$ORDERING_VIOLATION" -eq 1 ]]; then
    echo "WARN: pf root ruleset contains broad pass rule before anchor '$ANCHOR_NAME' which neutralizes it: '$VIOLATING_RULE'" >&2
    exit 5
  fi
fi

if [[ "${1:-}" == "--json" ]]; then
  echo "{\"layer\":\"pf-egress\",\"status\":\"ok\",\"anchor\":\"$ANCHOR_NAME\",\"rules_count\":${#REQUIRED_RULES[@]}}"
else
  echo "OK: Layer-3 macOS pf egress rules verified at $ANCHOR_FILE"
fi
exit 0
