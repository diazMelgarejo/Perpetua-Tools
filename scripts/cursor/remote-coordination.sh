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
  return 64
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

  python3 - "$gossip_env_present" "$topo_json" <<'PY'
import json
import sys

gossip_env_present = sys.argv[1].lower() == "true"
try:
    topology = json.loads(sys.argv[2] or "{}")
except json.JSONDecodeError:
    topology = {}

if not isinstance(topology, dict):
    topology = {}

# Hard-enforce the authority boundary even if an older probe is present.
topology["queue_write_authority"] = False

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
