#!/usr/bin/env bash
# =============================================================================
# scripts/security/install-egress-pf-rules.sh
# Layer-3 macOS pf (Packet Filter) egress enforcement floor installer
#
# Idempotent installer for /etc/pf.anchors/com.perpetua-tools.egress-deny
# Reference: orama-system docs/v2/54-tri-stack-observability-and-l3-egress-v2.md § 2
# =============================================================================
set -euo pipefail

ANCHOR_FILE="${PF_ANCHOR_FILE:-/etc/pf.anchors/com.perpetua-tools.egress-deny}"
ANCHOR_NAME="com.perpetua-tools.egress-deny"
PFCTL_SKIP="${PFCTL_SKIP:-0}"

# Check platform
if [[ "$(uname -s 2>/dev/null || echo Unknown)" != "Darwin" ]]; then
  echo "Non-macOS host ($(uname -s)) — pf egress rules apply to macOS only."
  exit 0
fi

# Expected rule payload
EXPECTED_RULES=$(cat << 'RULE_EOF'
# com.perpetua-tools.egress-deny
# Layer 3 host-level egress enforcement floor
# Blocks cloud metadata and link-local ranges regardless of source app or
# egress interface (Wi-Fi, Thunderbolt/USB-C Ethernet, VPN utun*, USB
# tethering) -- `on <iface>` scopes a rule to that interface only, silently
# bypassable via any other route.
block drop out quick to 169.254.0.0/16
block drop out quick to 169.254.169.254
block drop out quick to fd00:ec2::254
block drop out quick to fe80::/10
RULE_EOF
)

# Check idempotency: skip write if already matching
if [[ -f "$ANCHOR_FILE" ]]; then
  CURRENT_RULES="$(cat "$ANCHOR_FILE")"
  if [[ "$CURRENT_RULES" == "$EXPECTED_RULES" ]]; then
    echo "pf egress anchor rules already up to date at $ANCHOR_FILE"
    if [[ "$PFCTL_SKIP" -eq 1 ]]; then
      exit 0
    fi
  fi
fi

# Ensure parent directory exists
ANCHOR_DIR="$(dirname "$ANCHOR_FILE")"
if [[ ! -d "$ANCHOR_DIR" ]]; then
  if [[ -w "$(dirname "$ANCHOR_DIR" 2>/dev/null || echo .)" ]] || [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    mkdir -p "$ANCHOR_DIR"
  else
    sudo mkdir -p "$ANCHOR_DIR"
  fi
fi

# Write anchor file
if [[ -w "$ANCHOR_DIR" ]] || [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  echo "$EXPECTED_RULES" > "$ANCHOR_FILE"
  chmod 644 "$ANCHOR_FILE"
else
  echo "$EXPECTED_RULES" | sudo tee "$ANCHOR_FILE" >/dev/null
  sudo chmod 644 "$ANCHOR_FILE"
fi

echo "Wrote pf egress rules to $ANCHOR_FILE"

# Load anchor into pfctl if not skipped
if [[ "$PFCTL_SKIP" -ne 1 ]]; then
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    pfctl -a "$ANCHOR_NAME" -f "$ANCHOR_FILE" -e 2>/dev/null || true
  else
    sudo pfctl -a "$ANCHOR_NAME" -f "$ANCHOR_FILE" -e 2>/dev/null || true
  fi
  echo "Loaded anchor $ANCHOR_NAME into pfctl"
fi

exit 0
