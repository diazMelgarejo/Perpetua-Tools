# Mac orchestrator pulse — setup + Win blocker (2026-06-30)

**Status:** Mac side fully wired. Win dispatch blocked on infra (not auth).

## Done this session

- ✅ Mac OpenClaw persistent orchestrator confirmed: Ollama `qwen3.5:9b-nvfp4` (inference) + `bge-m3` (1024-dim embeddings, gbrain/CRG-compatible) — both warm on `localhost:11434`.
- ✅ `ORAMA_CONTROL_PLANE_TOKEN` resolved — steady-state token from `Auth-Lanes.md` already present in `orama-system/.env.local`; `auth_mode` now reports `joint` once exported.
- ✅ orama branch `subagent/win-coder/mac-co-orchestrator-playbook` (tip `2da1358`) — already pushed to origin, no retry needed.
- ✅ PT branch `subagent/mac-orchestrator/self-improve-memory` (tip `0dedf7e`) — confirmed fully merged into main via tree-twin scan (`reanchor_scan.sh`); the one "unreached" commit was content-identical to what's already on main (empty cherry-pick, skipped).
- ✅ `mac-orchestrator-pulse` cron job created via `openclaw cron add` (every 15m, agent `orchestrator`, isolated session, light context, 600s timeout). Survives gateway restart — persisted in `openclaw.json` `.cron.jobs`, not ephemeral state. Delivery is `announce -> last`, fail-closed silently when no chat is open (matches "alert only when a chat is open" requirement).
- ⚠️ Hand-editing `openclaw.json`'s cron schema via `jq` (per a skill doc's example) broke the live gateway — config validation failed, gateway exited, launchd showed `running` but the process had crashed. Restored from `openclaw.json.bak-pre-cron-2026-06-30`, re-bootstrapped the LaunchAgent, then used `openclaw cron add` CLI successfully. See `lesson_67ddcb4837f2` + `lesson_681ae028587d`.

## Blocker — Win orama portal (8002) down all session

- `peer-lmstudio` (port 1234, LM Studio `qwen3.5-27b-claude-4.6-opus-reasoning-distilled-v2`) — **PASS**, reachable all session.
- `portal-health` (port 8002, orama LAN-peer portal) — **FAIL**, connection times out / refuses (`HTTP 000`) for the entire session, including after auth was fixed. This is a Win-side service crash or hang, not a Mac-side or auth problem.
- A pending Win assignment (`coord-022-gossip`, 3×15m listen task) is sitting unsent in `orama-system/bin/orama-system/skills/hermes-harness/references/assignments/win-coord-listen-022.md` — never reached Win's inbox because the portal never accepted the POST.
- H6 real-task dispatch (`mac-hypothesis-h6-real-task.md`) and the Mac-vs-Win benchmark are both blocked on this same root cause.

## What happens next (no manual action needed on Mac)

The `mac-orchestrator-pulse` cron job will probe the Win peer every 15 minutes automatically. As soon as someone restarts the orama portal on Windows (`start.ps1 --lan-peer` per `docs/wiki/15-hermes-windows-harness.md`), the next pulse will detect `portal-health: PASS`, drain the queued `coord-022` and H6 assignments, and dispatch/benchmark without further prompting.

## If a human is on the Win box

Run on Windows: `.\start.ps1 --lan-peer` (or restart the orama portal process), then verify with `curl http://localhost:8002/health` locally on Win.
