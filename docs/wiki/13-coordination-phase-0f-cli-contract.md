# 13. Coordination Phase 0F CLI Contract

**TL;DR:** Phase 0F freezes the CLI contract for `agent_coordination.py` before extracting its modules. Do not confuse it with STM Phase 0.

---

## Terminology
Coordination Phase 0F is separate from STM Phase 0.
See [PHASE-0-TERMINOLOGY-DISAMBIGUATION.md](../coordination/PHASE-0-TERMINOLOGY-DISAMBIGUATION.md) for full context.

## Action
We extracted heartbeat handlers into `liveness.py` and left the parser/facade in `cli.py` to freeze the executable contract of 29 commands.
