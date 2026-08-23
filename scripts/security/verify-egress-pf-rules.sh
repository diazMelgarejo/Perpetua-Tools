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
ANCHOR_NAME="com.perpetua-tools"
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

# 2. Check rule content integrity / drift
REQUIRED_RULES=(
  "block drop out quick on en0 to 169.254.0.0/16"
  "block drop out quick on en0 to 169.254.169.254"
  "block drop out quick on en0 to fd00:ec2::254"
  "block drop out quick on en0 to fe80::/10"
)

ANCHOR_CONTENT="$(cat "$ANCHOR_FILE")"
for rule in "${REQUIRED_RULES[@]}"; do
  if ! echo "$ANCHOR_CONTENT" | grep -Fq -- "$rule"; then
    echo "WARN: pf egress anchor missing required rule: $rule" >&2
    exit 2
  fi
done

# 3. Check pfctl loaded rules unless test-skipped
if [[ "$PFCTL_SKIP" -ne 1 ]]; then
  LOADED_RULES="$(pfctl -a "$ANCHOR_NAME" -s rules 2>/dev/null || true)"
  if [[ -z "$LOADED_RULES" ]]; then
    echo "WARN: pf anchor $ANCHOR_NAME is not loaded or pf is inactive (run sudo bash scripts/security/install-egress-pf-rules.sh)" >&2
    exit 3
  fi
fi

echo "OK: Layer-3 macOS pf egress rules verified at $ANCHOR_FILE"
exit 0
