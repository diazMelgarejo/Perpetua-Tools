#!/usr/bin/env bash
# Truthful status-only helper for Cursor workers (I2).
#
# This is NOT an event relay. It never POSTs to peers and never claims that
# GOSSIP_PEERS / GOSSIP_SHARED_SECRET enable remote forwarding. Pulse/log are
# refused here; queue mutations remain coordinator-side only.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

usage() {
  cat <<'EOF'
Usage:
  scripts/cursor/remote-coordination.sh status

Status-only helper (I2). Prints JSON describing local topology and explicitly
reports that no remote event relay is implemented. Pulse/log/queue are not
supported by this helper — use PR/handoff (Mode B) or the local coordinator.
EOF
}

refuse_action() {
  local action="$1"
  printf '%s\n' \
    "remote-coordination.sh is status-only: '${action}' is not implemented (no remote event relay; no local CLI passthrough cosmetics)" \
    >&2
  # Exit, rather than return: a non-zero return in a case arm is not a
  # reliable `set -e` failure on every Bash implementation.
  exit 64
}

emit_status() {
  local gossip_env_present=false
  if [[ -n "${GOSSIP_PEERS:-}" || -n "${GOSSIP_SHARED_SECRET:-}" ]]; then
    gossip_env_present=true
  fi

  local topo_json='{}'
  if [[ -f scripts/cursor/topology_probe.py ]]; then
    # Advisory only — never treat Mode A as a write grant.
    topo_json="$(python3 scripts/cursor/topology_probe.py 2>/dev/null || echo '{}')"
  fi

  # Keep probe JSON off argv: it can contain local topology during the
  # subprocess lifetime even though the emitted payload is redacted.
  python3 - "$gossip_env_present" 3<<<"$topo_json" <<'PY'
import datetime
import json
import os
import sys
import uuid

gossip_env_present = sys.argv[1].lower() == "true"
try:
    topology = json.loads(os.fdopen(3).read() or "{}")
except (OSError, json.JSONDecodeError):
    topology = {}

if not isinstance(topology, dict):
    topology = {}

# Hard-enforce the authority boundary even if an older probe is present.
topology = {
    key: topology.get(key)
    for key in ("mode", "board_present", "topology_match")
    if key in topology
}
topology["queue_write_authority"] = False

# Agent label only. Private human identities are never emitted: the standing
# redaction rule applies, and an agent label (e.g. cline-session-20260907) is
# not a private identity.
AGENT_LABEL_ENV = ("PT_AGENT_ID", "OPENCLAW_AGENT_ID", "CLINE_AGENT_ID", "AGENT_ID")


def _agent_label() -> str:
    for key in AGENT_LABEL_ENV:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return "cursor-remote-worker"


now = datetime.datetime.now(datetime.timezone.utc)
label = _agent_label()

# Doc 69 Tier U header + the status kind panel. Identity verification is false
# because a local advisory observes nothing about a principal, and availability
# is "unknown" because no presence signal is sampled here.
header = {
    "envelope_id": f"status-{uuid.uuid4().hex[:16]}",
    "envelope_schema_version": "1",
    "envelope_kind": "status",
    "created_at": now.isoformat(),
    "privacy_tier": "internal_only",
    "author": {"agent_id": label, "model": None, "availability": "unknown"},
    "actor": {
        "agent_id": label,
        "instance_id": f"inst-{uuid.uuid4().hex[:12]}",
        "identity_verified": False,
    },
    "redaction": {"applied": True},
}
status_panel = {
    "authority": "read_only",
    "liveness_effect": "none",
    "observed_at": now.isoformat(),
}

payload = {
    "helper": "status-only",
    "remote_relay": False,
    "forwards_events": False,
    "queue_write_authority": False,
    "gossip_env_present": gossip_env_present,
    "gossip_env_note": (
        "GOSSIP_PEERS/GOSSIP_SHARED_SECRET do not enable forwarding in this helper"
        if gossip_env_present
        else "no gossip relay env set"
    ),
    "topology": topology,
    "header": header,
    "status": status_panel,
    "guidance": (
        "Mode B / cloud: report via PR or handoff; local coordinator owns queue "
        "transitions. Do not treat topology mode A as mutation authority."
    ),
}
json.dump(payload, sys.stdout)
sys.stdout.write("\n")
PY
}

command_name="${1:-}"
case "$command_name" in
  status)
    emit_status
    ;;
  pulse|log)
    refuse_action "$command_name"
    ;;
  -h|--help|help|"")
    usage
    ;;
  *)
    printf '%s\n' "unsupported remote coordination command: $command_name" >&2
    usage >&2
    exit 64
    ;;
esac
