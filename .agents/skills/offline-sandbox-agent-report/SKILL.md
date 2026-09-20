---
name: offline-sandbox-agent-report
description: "Write the canonical Markdown agent report when the coordination queue or LAN is unreachable (offline, sandbox, or not on the same machine). Use for offline/sandbox agent reports, no-LAN handoffs, Cursor Cloud status, and any agent that cannot admit JSON via agent_coordination.py. Prefer docs/coordination/agent-handoff-template.md when the queue is reachable."
---

# offline-sandbox-agent-report

Canonical human report for agents with **no LAN** and agents **not on
the same machine** as the operator host.

Load and follow
[`docs/coordination/offline-sandbox-agent-report.md`](../../../docs/coordination/offline-sandbox-agent-report.md).
That Markdown template is the source of truth for section names and
field mapping.

The shared Grok Bot skill for this workflow is named
`offline-sandbox-agent-report`. Do not follow a sand-workflow URL.

## When to use

- The operator asks for an offline / sandbox agent report
- GossipBus, LAN peer, or `scripts/agent_coordination.py` is unreachable
- This session is a cloud/sandbox VM, not the operator workstation
- You cannot run `handoff validate` / `queue add` / `heartbeat pulse`

## When not to use

If the coordination queue is reachable, do **not** substitute this
Markdown for admission. Use
[`docs/coordination/agent-handoff-template.md`](../../../docs/coordination/agent-handoff-template.md)
and [`docs/coordination/examples/handoff-packet-v1.json`](../../../docs/coordination/examples/handoff-packet-v1.json).

## Instructions

1. Fill every required section in the canonical template (Identity,
   Locality, Outcome, Evidence, Authority, Reachability).
2. Set `merge_authorized: false` and `deployment_authorized: false`.
3. Put observed commands and results under Evidence. Do not claim a
   pass you did not run.
4. Keep `current_head` equal to `commit_sha` after the work is
   committed.
5. Leave `heartbeat_pulsed: false` unless this process actually sent
   `heartbeat pulse` for an agent it controls on a reachable bus.
6. Return the filled report as the handoff text. Do not enqueue the
   Markdown file as if it were validated JSON.

## Never

- Open a new PR, merge, or force-push because this skill was invoked
- Grant merge or deploy from the report
- Invent SHAs, test results, or LAN IDs
- Pulse heartbeat for an agent you do not control
- Replace the JSON handoff path in `docs/coordination/`
