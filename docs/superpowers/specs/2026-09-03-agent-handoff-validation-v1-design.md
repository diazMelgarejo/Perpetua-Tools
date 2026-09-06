# Agent Handoff Validation v1 — Design

## Goal

Make every new standard agent-dispatch packet machine-checkable before it is
placed on PT's GossipBus-backed queue, while retaining the existing v1 queue
commands for callers that have not yet migrated.

## Scope

This is a v1 compatibility layer. It adds a canonical JSON handoff packet, a
pure validator, a CLI preflight, and an opt-in queue-admission gate. It does
not change existing queue-row wire data, make handoffs a distributed lock, or
migrate coordination to v2.

## Non-goals

- Parsing free-form Markdown as authority.
- Treating a board log as a heartbeat.
- Auto-merging, deploying, creating workers, or elevating human authority.
- Requiring every legacy `queue add` caller to migrate in this change.

## Architecture

`orchestrator/handoff_validation.py` owns the `HandoffPacketV1` Pydantic
contract and a pure file-loader/validator. A packet carries the source line,
worker intent, evidence expectations, verification commands, and explicit
authority limits. Validation returns typed field/code/message diagnostics at
the CLI boundary rather than raw parser exceptions. It is strict and closed:
coercion and undeclared fields are rejected.

`scripts/agent_coordination.py handoff validate PACKET.json` is the operator
preflight. `queue add ... --handoff PACKET.json` uses that exact validator
before it calls `queue_add`; an invalid packet therefore emits no queue event
and cannot become dispatchable through the new standard path. A valid packet's
branch and starting SHA become the existing queue source-line fields, and its
named recipient becomes a queue reservation that no other worker can claim.

The gate emits a `handoff_admitted` audit event only after validation and
enqueue succeed. It must not pulse the assigned agent: admitting work proves
coordinator activity, not that the receiver is alive. Subsequent long-running
workers remain responsible for periodic explicit pulses; validation neither
refreshes a stale worker nor changes liveness timeouts. `log()` remains status
text and never becomes a liveness signal.

## Packet contract

Required fields are `schema_version` (= 1), session/job/task/agent identifiers,
role, intent, branch/worktree, starting/current/commit SHA values, changed
files, root cause, test command/result pairs, known risks, and explicit human,
merge, and deployment authority fields. SHA values use 7--40 hexadecimal
characters. `current_head` must equal `commit_sha`. v1 rejects packets that
claim merge or deployment authority.

## Failure behavior

Malformed JSON, missing fields, invalid SHA values, inconsistent heads, empty
evidence, and forbidden authority claims fail closed. The CLI prints concise
diagnostics and exits non-zero. Queue admission fails before touching
GossipBus, so no orphan task-event or implicit heartbeat is written.

One-shot coordination CLI commands cancel and drain only their own optional
background embedding tasks before `asyncio.run()` closes. This preserves the
durable event while preventing aiosqlite worker threads from writing back into
a closed event loop. Long-lived runtimes retain their own embedding tasks.

## Documentation and migration

Markdown teaches humans the protocol but declares JSON the source of truth.
The JSON example is both a copyable starting point and executable contract
fixture. v2 may make validated packets mandatory across all dispatch surfaces,
but must preserve this schema or ship an explicit versioned adapter.

## Tests

- Valid packets validate and preserve their source line.
- Missing evidence, head mismatch, and forbidden merge authority fail with
  actionable diagnostics.
- CLI preflight returns zero/non-zero correctly.
- `queue add --handoff` writes a queue event and non-liveness admission audit
  event only for a valid packet.
- Invalid packets write neither event; `log()` does not refresh liveness.
- Existing `queue add` remains unchanged without `--handoff`.
