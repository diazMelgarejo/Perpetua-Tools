#!/usr/bin/env bash
# Shared pre-commit/pre-push gate dispatcher (PT memory lane).
#
# Pattern source: orama-system scripts/ci/run_agent_security_scans.sh +
# docs/v2/plans/2026-08-20-agent-security-ci-runtime-efficiency.md — "split
# the invocation, not the gate logic": one implementation per gate, invoked
# by name, so pre-commit, pre-push, and CI can never drift apart the way a
# doc-embedded snippet and a script's inline logic did in the 2026-07-22
# namespace-collision incident.
#
# Usage: run_gates.sh <gate-name> [args...]
#   lan-topology            private LAN IPs in tracked config
#   memory-records          staged .agent/memory/** record validation
#   episodic-append-only <base> <head>   pinned-boundary byte check
#   repo-hygiene <root>     canonical hygiene (same check CI runs)
#   script-mode             git mode 100755 for Cursor bootstrap shell scripts
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

case "${1:-}" in
  lan-topology)
    exec python3 "$ROOT/scripts/hooks/no_committed_lan_topology.py"
    ;;
  memory-records)
    exec python3 "$ROOT/scripts/hooks/check_memory_records.py"
    ;;
  episodic-append-only)
    shift
    exec python3 "$ROOT/scripts/review/check_episodic_append_only.py" --repo "$ROOT" "$@"
    ;;
  repo-hygiene)
    shift
    exec python3 "$ROOT/scripts/review/repo_hygiene.py" "${1:-$ROOT}"
    ;;
  script-mode)
    exec python3 "$ROOT/scripts/hooks/check_tracked_script_mode.py"
    ;;
  *)
    echo "run_gates: unknown gate '${1:-}'" >&2
    exit 2
    ;;
esac
