# Agent Coordination Learnings (AntiGravity-Gemini)

## Date

2026-08-14

## Context

During the execution of Task 5 (Verify Antigravity And Preserve gstack Namespace
Ownership), the agent needed to register its identity and claim the implementation task on
the coordination board.

## Learning

**Do not write directly to the SQLite state database.**
The board’s canonical storage is the PT GossipBus database located at
`.state/perpetua_core.db`. However, direct SQLite writes are not the supported posting
interface.

The canonical posting entrypoint is confirmed as
`Perpetua-Tools/scripts/agent_coordination.py`, which serves as a thin wrapper over
`orchestrator.coordination.cli`.

### Commands Used

To register an agent:

```bash
python3 Perpetua-Tools/scripts/agent_coordination.py register <Agent-ID> \
  "<Persona/Roles>" <Model> "<Notes>"
```

To claim a task:

```bash
python3 Perpetua-Tools/scripts/agent_coordination.py claim <Agent-ID> \
  "<Task Name>" "<Notes>"
```

To release a task:

```bash
python3 Perpetua-Tools/scripts/agent_coordination.py release <Agent-ID> \
  "<Task Name>"
```

## Takeaway

Future agents (including Antigravity, Gemini, or Codex) must use the
`agent_coordination.py` CLI to manage their liveness, claims, and releases on the board.
Bypassing the CLI to write directly to the database leads to unreliable board liveness and
coordination failures (as observed when CODEX was unable to see an unregistered
AGY/Gemini agent).
