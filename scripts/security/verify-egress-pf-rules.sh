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
mapfile -t ACTUAL_RULE_LINES < <(grep -vE '^\s*(#.*)?$' "$ANCHOR_FILE" 2>/dev/null || true)

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
  LOADED_RULES="$(pfctl -a "$ANCHOR_NAME" -s rules 2>/dev/null || true)"
  if [[ -z "$LOADED_RULES" ]]; then
    echo "WARN: pf anchor $ANCHOR_NAME is not loaded or pf is inactive (run sudo bash scripts/security/install-egress-pf-rules.sh)" >&2
    exit 3
  fi
  # Loaded-and-populated is necessary but not sufficient: pf only evaluates
  # an anchor's rules when a parent "anchor" directive in the root ruleset
  # (pf.conf) actually attaches it. Confirm that attachment exists.
  ROOT_RULES="$(pfctl -sr 2>/dev/null || true)"
  if ! echo "$ROOT_RULES" | grep -qF "anchor \"$ANCHOR_NAME\""; then
    echo "WARN: pf anchor $ANCHOR_NAME is loaded but not attached in the root ruleset -- it will never be evaluated (run sudo bash scripts/security/install-egress-pf-rules.sh)" >&2
    exit 4
  fi
fi

echo "OK: Layer-3 macOS pf egress rules verified at $ANCHOR_FILE"
exit 0
