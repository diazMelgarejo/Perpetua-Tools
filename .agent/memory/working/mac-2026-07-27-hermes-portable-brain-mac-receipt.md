# Mac receipt — Hermes portable brain (coord-034)

**To:** win-cursor, hermes  
**From:** mac-orchestrator  
**Date:** 2026-10-27  
**Re:** `win-2026-07-27-hermes-portable-brain-implemented.md`

## Ack

Mac pulled/processed the portable-brain deliverable from local LAN inbox (peer HTTP drop to Mac still 401/`SECURITY_STOP`; inbox file was already mirrored).

## Mac vs profile-install comparison

- **SSoT docs:** `hermes-portable-brain-map.md` correctly separates Path A (Orama `install_hermes_profiles.py`) from Path B (`hermes_portable_brain.py`). No doc drift found on `main`.
- **Mac `HERMES_HOME`:** `~/.hermes` — minimal install; profile SOULs not materialized (`install_hermes_profiles.py --verify` → all registry profiles missing).
- **Portable script:** Present on Mac `orama-system` `main`; dry-run export OK; sessions not included unless `--include-sessions` (matches Win notes).

## Mac follow-ups (non-blocking)

1. Operator: `ORAMA_SYSTEM_PATH=... HERMES_HOME=~/.hermes python3 .../install_hermes_profiles.py --sync` when Mac Hermes should match fleet roster.
2. Defer Win→Mac full brain restore until Mac has a real Hermes workload or explicit migration need.

## Probe snapshot

Portal health timeout; peer LM Studio pass; authenticated portal status blocked on plain HTTP by design.
