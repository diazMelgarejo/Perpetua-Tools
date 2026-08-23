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
PF_CONF_FILE="${PF_CONF_FILE:-/etc/pf.conf}"
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

# Register the parent anchor in the active PF configuration. Loading rules
# with `pfctl -a "$ANCHOR_NAME" -f` alone does not make pf evaluate them --
# pf only reaches an anchor when a parent "anchor" rule in the root ruleset
# (pf.conf) points to it. Manage a delimited block so repeated runs are
# idempotent and unrelated pf.conf content is never touched.
ANCHOR_BLOCK_START="# BEGIN com.perpetua-tools.egress-deny (managed by install-egress-pf-rules.sh)"
ANCHOR_BLOCK_END="# END com.perpetua-tools.egress-deny"
ANCHOR_BLOCK=$(cat << BLOCK_EOF
${ANCHOR_BLOCK_START}
anchor "${ANCHOR_NAME}"
load anchor "${ANCHOR_NAME}" from "${ANCHOR_FILE}"
${ANCHOR_BLOCK_END}
BLOCK_EOF
)

if [[ -f "$PF_CONF_FILE" ]] && grep -qF "$ANCHOR_BLOCK_START" "$PF_CONF_FILE" 2>/dev/null; then
  echo "pf.conf anchor declaration already present at $PF_CONF_FILE"
else
  # Insert before the first pre-existing "quick" rule so a broad catch-all
  # (e.g. a general "pass out quick all") never runs before this anchor is
  # reached -- quick terminates evaluation on the first match, so ordering
  # here is load-bearing, not cosmetic.
  TMP_CONF="$(mktemp)"
  trap 'rm -f "$TMP_CONF"' EXIT
  if [[ -f "$PF_CONF_FILE" ]]; then
    if grep -qE '^\s*(pass|block).*quick' "$PF_CONF_FILE" 2>/dev/null; then
      FIRST_QUICK_LINE="$(grep -nE '^\s*(pass|block).*quick' "$PF_CONF_FILE" | head -1 | cut -d: -f1)"
      head -n "$((FIRST_QUICK_LINE - 1))" "$PF_CONF_FILE" > "$TMP_CONF"
      printf '%s\n' "$ANCHOR_BLOCK" >> "$TMP_CONF"
      tail -n "+${FIRST_QUICK_LINE}" "$PF_CONF_FILE" >> "$TMP_CONF"
    else
      cat "$PF_CONF_FILE" > "$TMP_CONF"
      printf '%s\n' "$ANCHOR_BLOCK" >> "$TMP_CONF"
    fi
  else
    printf '%s\n' "$ANCHOR_BLOCK" > "$TMP_CONF"
  fi

  if [[ -w "$(dirname "$PF_CONF_FILE")" ]] || [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    cp "$TMP_CONF" "$PF_CONF_FILE"
  else
    sudo cp "$TMP_CONF" "$PF_CONF_FILE"
  fi
  rm -f "$TMP_CONF"
  trap - EXIT
  echo "Registered anchor declaration in $PF_CONF_FILE"

  if [[ "$PFCTL_SKIP" -ne 1 ]]; then
    if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
      pfctl -f "$PF_CONF_FILE"
    else
      sudo pfctl -f "$PF_CONF_FILE"
    fi
    echo "Reloaded $PF_CONF_FILE"
  fi
fi

# Load anchor into pfctl if not skipped. The anchor load itself is NOT
# masked with `|| true` -- a genuine load failure means the enforcement
# floor is not active, which the operator must see. Enabling pf is a
# separate step: `pfctl -e` on an already-enabled pf reports a benign,
# expected non-zero exit ("pf already enabled") on repeated runs, which is
# tolerated explicitly here rather than masking real load failures too.
if [[ "$PFCTL_SKIP" -ne 1 ]]; then
  enable_pf() {
    local output
    if output="$("$@" -e 2>&1)"; then
      return 0
    fi
    if grep -qi "already enabled" <<<"$output"; then
      return 0
    fi
    echo "ERROR: failed to enable pf: $output" >&2
    return 1
  }

  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    pfctl -a "$ANCHOR_NAME" -f "$ANCHOR_FILE"
    enable_pf pfctl
  else
    sudo pfctl -a "$ANCHOR_NAME" -f "$ANCHOR_FILE"
    enable_pf sudo pfctl
  fi
  echo "Loaded anchor $ANCHOR_NAME into pfctl"
fi

exit 0
