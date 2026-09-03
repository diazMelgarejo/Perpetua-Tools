# Agent Handoff Validation v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate structured agent handoff packets before new standard queue admission and emit a non-liveness admission audit only after successful admission.

**Architecture:** A Pydantic packet model and pure validation function own the v1 handoff boundary. The existing coordination CLI delegates file loading and validation to that boundary; its queue path remains backward compatible unless `--handoff` is supplied.

**Tech Stack:** Python 3.11, Pydantic v2, argparse, aiosqlite/GossipBus, pytest.

**Spec:** `docs/superpowers/specs/2026-09-03-agent-handoff-validation-v1-design.md`

## Global Constraints

- JSON is the machine source of truth; Markdown is explanatory only.
- Invalid handoffs fail before any queue or admission-audit mutation.
- `log()` remains non-liveness activity; only `heartbeat pulse` semantics refresh presence.
- Existing queue callers remain compatible when `--handoff` is absent.
- No packet authorizes merge, deployment, secrets, or recursive agent spawning.

---

### Task 1: Define the v1 packet contract

**Files:**
- Create: `orchestrator/handoff_validation.py`
- Test: `tests/test_handoff_validation.py`

**Interfaces:**
- Produces: `HandoffPacketV1`, `HandoffValidationError`, and `load_handoff_packet(path: Path) -> HandoffPacketV1`.
- Consumes: JSON input and Pydantic v2 only.

- [ ] Write tests for a valid packet, invalid SHA, mismatched current/commit heads, empty test evidence, and merge/deployment authority rejection.
- [ ] Run `python -m pytest tests/test_handoff_validation.py -q` and record the expected initial import failure.
- [ ] Implement only the typed model, JSON file loader, and normalized field-specific error boundary needed to make those tests pass.
- [ ] Rerun `python -m pytest tests/test_handoff_validation.py -q`.
- [ ] Commit `feat(coordination): validate handoff packets`.

### Task 2: Gate the coordination CLI

**Files:**
- Modify: `orchestrator/coordination/cli.py`
- Test: `tests/test_agent_handoff_cli.py`

**Interfaces:**
- Consumes: `load_handoff_packet(path: Path)`.
- Produces: `handoff validate PACKET.json` and `queue add --handoff PACKET.json`.

- [ ] Write failing CLI tests for valid/invalid preflight and queue tests proving an invalid packet produces no queue or admission-audit event.
- [ ] Run `python -m pytest tests/test_agent_handoff_cli.py -q` and record parser/helper failure.
- [ ] Add the `handoff validate` parser leaf and the optional `--handoff` queue argument. Do not modify `scripts/agent_coordination.py`; it is a compatibility facade that re-exports the canonical CLI.
- [ ] Validate before `queue_add`; on success pass packet branch and starting SHA to the existing queue source-line fields, then emit a `handoff_admitted` audit event. Do not pulse the assigned worker: only that worker can prove its presence.
- [ ] Run `python -m pytest tests/test_agent_handoff_cli.py tests/test_agent_coordination_queue.py -q`.
- [ ] Commit `feat(coordination): gate queue admission on handoff evidence`.

### Task 3: Publish the template and executable example

**Files:**
- Create: `docs/coordination/agent-handoff-template.md`
- Create: `docs/coordination/examples/handoff-packet-v1.json`
- Modify: `docs/coordination/README.md`
- Test: `tests/test_handoff_validation.py`

**Interfaces:**
- Consumes: `HandoffPacketV1`.
- Produces: human template, valid machine-readable example, and documented commands.

- [ ] Add a failing test that loads the committed example.
- [ ] Run the specific test and record the expected absent-file failure.
- [ ] Add the template, JSON example, and README commands for `handoff validate` and `queue add --handoff`.
- [ ] State that every long-running worker must pulse independently; logs and admission events do not refresh liveness.
- [ ] Rerun all handoff tests and commit `docs(coordination): publish validated handoff template`.

### Task 4: Verify, package, and publish the separate PR

**Files:**
- Create outside the repository: `agent-handoff-validation-v1-output.zip`

- [ ] Run `python scripts/agent_coordination.py handoff validate docs/coordination/examples/handoff-packet-v1.json`.
- [ ] Verify a legacy `queue add` one-shot command also exits without an aiosqlite closed-loop traceback; the CLI must cancel and drain only current-loop optional embedding tasks before shutdown.
- [ ] Run `python -m pytest tests/test_handoff_validation.py tests/test_agent_handoff_cli.py tests/test_agent_coordination_queue.py -q` and `git diff --check`.
- [ ] Package the template, JSON example, design, plan, and a generated validation report in the ZIP.
- [ ] Push `feat/agent-handoff-validation-v1`, create a PR against `main`, and report the exact head, changed files, and test evidence.
