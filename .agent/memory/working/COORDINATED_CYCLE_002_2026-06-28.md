# Coordinated cycle 002 — landmark

**Date:** 2026-06-28  
**Status:** ACTIVE — Mac+Win subagents working in parallel

## What shipped this cycle

| Host | Assignment | Inbox |
|------|------------|-------|
| Mac | `mac-routing-policy-review.md` | local |
| Mac | `mac-routing-review.md` (result) | local |
| Win | `win-autoresearch-h4-gpu.md` | peer |
| Win | `mac-hypothesis-v2.md` | peer |

## Fan-out manifest

`orama-system/.../references/coordinated-cycle-002.json`

## Self-improve gate

`~/.openclaw/state/lan_peer/inbox/self-improve-merge-final-proposed.md`  
→ reply **`approve lessons`** to land PT + orama `docs/LESSONS.md`

## Win waiting on

- autoresearcher: H4 benchmark → drop `gpu-results-h4.md` to Mac peer

## Mac subagents

- **mac-researcher:** `mac-hypothesis-v2.md` dropped to Win
- **orchestrator:** `mac-routing-review.md` complete
- **co-orchestrator:** cycle 002 fan-out OK
