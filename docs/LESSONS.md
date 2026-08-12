# Lessons — Perpetua-Tools

> **Cross-repo companion:** [`orama-system/docs/LESSONS.md`](../../orama-system/docs/LESSONS.md) — read both at session start for joint context.
> **Architecture authority:** [`orama-system/docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md`](../../orama-system/docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md)
> **Navigation hub:** [`CLAUDE-instru.md`](../../../CLAUDE-instru.md)

---

## 2026-07-10 — Checkpoint 1.0 team review + repo grounding + alexandria policy | Claude Code

**Session:** Phase 0 blocker fixes + multi-agent orchestration (Codex + Cline + Sonnet-5)
**Key mistake:** Edited specs from wrong location (gstack cache instead of canonical PT docs)
**Outcome:** User called out two-repo invariant violation; corrected course; committed fixes; established alexandria policy

### Critical lessons

35. **Two-repo invariant FIRST** — Before editing architectural specs, ALWAYS run git verification to confirm repo locations. This session edited specs from `~/.gstack/projects/` (gstack cache) instead of canonical `docs/phase-0-specifications/` (PT). User had to prompt correction. Apply two-repo check as FIRST step before multi-repo work.

36. **Orama monorepo structure** — `~/code/oramasys` is a container; the actual orama-system repo is at `~/code/oramasys/oramasys/`. Non-obvious. Document in checklist: `cd ../../oramasys/oramasys/` for orama-system canonical work, NOT `cd ../../oramasys/` alone.

37. **Codex CLI interactive limitation** — Codex needs TTY; piping stdin with `< /dev/null` fails silently. Codex 0.144.1 auth works, but review requires interactive terminal. Defer Codex reviews in non-interactive context (subagent sandbox). Reserve for foreground human sessions.

38. **Token sequencing** — Session burned ~40k tokens before critical-fixes phase. Early token-budget visibility enables ordering fixes by token-cost (T7 fix ~30m vs STM model ~4h). Request budget estimate before sequencing multi-phase work.

39. **Positive: two-repo grounding check** — User-prompted repo verification pattern worked excellently. Reusable pattern: when unsure of canonical location, verify both repos FIRST. Do this before any multi-repo edit.

40. **STM model conflict (spec reconciliation)** — D1 specifies POLLS_TO_CONFIRM=2; D2 specifies PROMOTE_THRESHOLD=2, DEMOTE_THRESHOLD=3. Spec-reconciliation task (design decision + dual-doc update + pseudocode), not implementation task. Resolve conflicts BEFORE Phase 1 scoping.

41. **REPO-CROSS-REFERENCE.md created** — Navigation confusion from gstack cache stale copies led to creation of canonical cross-reference document (docs/REPO-CROSS-REFERENCE.md) mapping all plans/specs/ADRs across PT and orama-system. Maintenance pattern: maintain cross-reference FIRST when adding new plans; use relative paths only (no `/<user>/`-style workstation-absolute paths in tracked files).

42. **Alexandria repository policy APPROVED** — Decision: create `oramasys/alexandria` as a documentation-only, zero-code repository for centralized specs, threat models, ADRs, and team review checklists. Benefits: single source of truth (not scattered across PT + gstack cache), no code = no build burden, stable URL anchors for cross-project references, clear L2/L3 delineation. ADR to be written to orama-system/docs/v2/41-alexandria-repository.md. Sync this policy to BOTH repos' LESSONS.md when implemented.

---

---

## 2026-06-29 — Bucket drain + subagent fan-out (operator approved ALL) | Cursor

**Approval:** operator `approve lessons` (round 10)  
**Machine lessons:** `lesson_db15dbdc9000`, `lesson_77688462f96e`, `lesson_b545fe9db94c`

32. **Subagent fan-out** — `win-coder-queue` + `win-autoresearcher-queue` in `.cursor/agents` (`lesson_db15dbdc9000`)
33. **401 after security PR** — restart `start.ps1 --lan-peer` before peer drops (`lesson_77688462f96e`)
34. **Stash before pull** — PT behind Mac learn rows; stash submodule/candidate drift (`lesson_b545fe9db94c`)

---

## 2026-06-28 — Cycle 005 coder + Ladder F (operator approved ALL) | Cursor

**Approval:** operator `approve lessons` (round 9) — **ALL** to PT `.agent`  
**Fan-out:** `2026-06-28-coord-005`  
**Machine lessons:** `lesson_7fc75916a601`, `lesson_81a9b9806526`, `lesson_7588896135cf`, `lesson_b6d64dcb2d7f`

28. **Bridge PR verify** — 38/38 tests on `subagent/win-coder/bridge-http-local`; drop `win-bridge-pr-ready.md` (`lesson_7fc75916a601`)
29. **Ladder F** — model-routing-check dispatch gate in `graceful-degradation.md` (`lesson_81a9b9806526`)
30. **Idle resume** — `V1_DEFERRED_BACKLOG` when queues idle >15 min (`lesson_7588896135cf`)
31. **Peer timeout degrade** — continue local queue; retry drop when probe green (`lesson_b6d64dcb2d7f`)

---

## 2026-06-28 — Self-improve cycle 005 (operator approved ALL) | Cursor

**Approval:** operator `approve lessons` (round 8) — **ALL** to PT `.agent`  
**Fan-out:** `2026-06-28-coord-005`  
**Sources:** `win-self-improve-cycle-005.md`, monitor log, queue reconcile, H5 finalize  
**Machine lessons:** `lesson_c391481ca104`, `lesson_8b5d45070494`, `lesson_82ab64772b2b`, `lesson_2a476c761ca1`

### Gold nuggets

24. **PS ASCII-only** — em-dash in `coord_monitor.ps1` broke ParserError; use ASCII in Win ops scripts (`lesson_c391481ca104`)
25. **PT memory merge** — union all rows when Mac+Win push `.agent/memory` same round (`lesson_8b5d45070494`)
26. **H5 finalize pattern** — pull Mac results, synthesis-only, drop final, no GPU re-run (`lesson_82ab64772b2b`)
27. **Monitor validated** — `coord_monitor.ps1` tick 5 caught coord-005 before manual poll (`lesson_2a476c761ca1`)

---

## 2026-06-28 — Cycle 005 H5 closed (operator approved) | Cursor

**Approval:** operator `approve lessons` (round 7)  
**Fan-out:** `2026-06-28-coord-005`  
**Machine lessons:** `lesson_e2f8a41c7d93`

23. **H5 closed** — Mac 3/3 @ 1/4/5 itp (490s) vs Win 3/3 @ 1/1/1 (280s); route autoresearch-coder to Win 27B (`lesson_e2f8a41c7d93`)

---

## 2026-06-28 — Queue prune + monitor playbook (operator approved) | Cursor

**Approval:** operator `approve lessons` (round 6)  
**Tool:** `win_job_queue.py` (`prune`, `complete-pending`)  
**Machine lessons:** `lesson_c6e4f1a89d20`, `lesson_9b3d7e2f41ac`

### Gold nuggets

21. **Queue hygiene** — `prune` on enqueue strips mac-* deliverables and ops noise; `complete-pending` reconciles finished coord jobs (`lesson_c6e4f1a89d20`)
22. **Active-cycle monitor** — poll probe + inbox + queue every 2–3 min; Mac H5 leg Mac-owned until dropped (`lesson_9b3d7e2f41ac`)

---

## 2026-06-28 — Cycle 004 sequential job queues (operator approved) | Cursor

**Approval:** operator `approve lessons` (round 5)  
**Fan-out:** `2026-06-28-coord-004`  
**Tool:** `bin/orama-system/skills/hermes-harness/scripts/win_job_queue.py`  
**Machine lessons:** `lesson_a3f8e2b91c04`, `lesson_7d2c1e8f5b90`

### Deliverables

| Role | Output |
|------|--------|
| autoresearcher | `gpu-results-h5-cross.md` → Mac |
| coder | `win-frugal-spawn-policy.md` → Mac |

### Gold nuggets

19. **Sequential Win queues** — `win_job_queue.py` routes `win-autoresearcher-*` / `win-coder-*` cards; one active job per role; LM Studio single-tenant (`lesson_a3f8e2b91c04`)
20. **Mac H4 closed** — Ollama 9B ~20.2s vs Win 27B ~33.1s warm clamp; H5 Win 3/3 iter-1; Mac H5 pending (`lesson_7d2c1e8f5b90`)

---

## 2026-06-28 — Self-improve merge FINAL + H3 routing (operator approved) | Cursor

**Approval:** operator `approve lessons` (round 4) — **union** with rounds 1–3 (doctrine C)  
**Sources:** `self-improve-merge-final-proposed.md`, `self-improve-merge-proposed.md`, `mac-self-improve-cycle-003.md`  
**Machine lessons:** `lesson_1f9c927792ba`, `lesson_203c342c1e85` (2 new rows; remainder already in jsonl)

### Union confirmation (already landed — not duplicated)

| Topic | Existing lesson / doc |
|-------|----------------------|
| File inbox co-orchestration | `lesson_87636d658879`, `lesson_20833366511b` |
| Mac Ollama warm / LM Studio passive | `lesson_49a5af119f6f` |
| autoresearch HTTP-local preflight | `lesson_aeb3cd01c203` (supersedes `lesson_7791e7860857`) |
| peer-stream / peer-file restart | `lesson_legacy_peerstream_20260628`, `lesson_130073d9e30a` |
| Post-commit sync | `lesson_legacy_sync_rebase_20260628` |
| Graceful degradation ladders | `lesson_c8dc70c59ac9` + `graceful-degradation.md` |

### New gold nuggets (round 4)

17. **H3 falsified — route by task class** — Win 27B ~10s on trivial prompts; affinity in `routing.yml` is quality/heavy → Win, latency-sensitive → Mac Ollama (`lesson_1f9c927792ba`)
18. **Portal monitor URLs** — Mac co-orchestrator: `/co-orchestration/macos`; Win: `/peer-inbox` (`lesson_203c342c1e85`)

---

## 2026-06-28 — Cycle 003 + graceful degradation ladders (operator approved) | Cursor

**Approval:** operator `approve lessons` (round 3)  
**Fan-out:** `2026-06-28-coord-003`  
**Canonical reference:** orama `bin/orama-system/skills/oramasys-method/references/graceful-degradation.md`  
**Machine lessons:** `lesson_c8dc70c59ac9` … `lesson_0ec02977f23a` (6 rows in `.agent/memory/semantic/lessons.jsonl`)

### Cycle 003 deliverables (Win)

| Subagent | Branch | Dropped to Mac |
|----------|--------|------------------|
| autoresearcher | `subagent/win-autoresearcher/h5-gpu-harness` | `gpu-results-h5.md` (3/3 PASS, iter 1) |
| coder | `subagent/win-coder/bridge-http-local` | `win-bridge-spike-notes.md` |
| doc-sync | `subagent/win-orchestrator/doc-sync-peer-inbox` | `win-doc-sync-peer-inbox.md` |

**Portal:** Win lane `/peer-inbox`; `/co-orchestration/windows` → 307 redirect (`1679b84`).

### Graceful degradation gold nuggets

11. **Unified ladders** — search (gbrain→CRG→web), inference (host-local→validated fallback→cloud budget cutoff), LAN (ws-peer→SSE, file inbox→partial fan-out), autoresearch (`http-local`→SSH) (`lesson_c8dc70c59ac9`)
12. **Win canonical inbox** — `platform/windows/peer_inbox_portal.py`; Hermes skin deleted; legacy URLs redirect (`lesson_0762f924239d`)
13. **Subagent branches** — `subagent/<role>/<topic>` for mutations only; inbox on `main`; operator PR review (`lesson_d0dfe41fb420`)
14. **HTTP-local preflight** — `AUTORESEARCH_PREFLIGHT_MODE=auto` skips SSH when `GPU_BOX` is local (`lesson_aeb3cd01c203`)
15. **H5 harness** — `run_h5_gpu_benchmark.py`; iterations-to-pass on Win 27B; Mac 9B leg still pending (`lesson_b7fb9002c24f`)
16. **Subagent usage limit** — when Task subagents hit quota, parent executes inline and still drops inbox deliverables (`lesson_0ec02977f23a`)

---

## 2026-06-28 — Portal dashboard `/` 500 after pull/restart (operator approved) | Cursor

**Approval:** operator `approve lessons` (round 2) — memory **union** per doctrine C  
**Fix:** orama `435d27a` — `_unwrap_redacted_list()` in `portal_server.py`  
**Symptom:** `http://localhost:8002/` → Internal Server Error; `/health` may still return 200 on stale portal process  
**Machine lessons:** `lesson_78f4700bd60c` (Win detail) + `lesson_64dedfe61cfa` (restart shorthand) + `lesson_20833366511b` (ws-peer GO)

### Win recovery

```powershell
cd $env:ORAMA_SYSTEM_PATH
git pull --ff-only origin main   # need >= 435d27a
.\platform\windows\start.ps1 --stop
.\platform\windows\start.ps1 --lan-peer --no-open
```

### Mac recovery

```bash
cd "$ORAMA_SYSTEM_PATH"
git pull --ff-only origin main
./start.sh --stop && ./start.sh --lan-peer --no-open
```

---

## 2026-06-28 — Operator approved: co-orchestration GO + self-improve lessons | Cursor

**Approval:** operator `approve lessons` (2026-06-28)  
**Sources:** `mac-lessons-draft.md`, `win-self-improve-runtime-results.md`, live probes  
**Machine lessons:** `lesson_87636d658879` … `lesson_64dedfe61cfa` (15 rows in `.agent/memory/semantic/lessons.jsonl`)

### Operational status (verified live)

| Layer | Status |
|-------|--------|
| L1 inference | PASS — Mac Ollama warm (`:11434`); Win LM Studio 27B (`:1234`) |
| L2 portal | PASS — `auth_mode: joint` |
| L3 file inbox | PASS — bidirectional `POST /api/peer-file` |
| ws-peer | PASS — bidirectional (`websockets>=12`, orama `58605e1`) |

### Approved gold nuggets (beyond co-orchestrator section below)

8. **Joint auth** — PT `.state/control_plane_token` + orama env lanes; either key unlocks `portal-status` on probes (`lesson_43c39af8176f`)
9. **ws-peer GO** — when ws-peer PASS both directions, L3 file inbox co-orchestration is fully operational; coordinate only via `lan_peer_assign` file drops, not remote agent RPC (`lesson_20833366511b`)
10. **parents[4]** — `lan_peer_assign.py` repo root is `Path(__file__).resolve().parents[4]`, not `parents[5]` (orama `9f89051`)

---

## 2026-06-28 — Coordinated cycle 002: parallel Mac+Win subagents | Cursor

**Landmark:** `.agent/memory/working/COORDINATED_CYCLE_002_2026-06-28.md`  
**Fan-out manifest:** [`coordinated-cycle-002.json`](../../orama-system/bin/orama-system/skills/hermes-harness/references/coordinated-cycle-002.json)

| Host | Assignment | Deliverable |
|------|------------|-------------|
| Mac | routing policy review | `mac-routing-review.md` |
| Win | H4 GPU coding-loop benchmark | `gpu-results-h4.md` → Mac inbox |
| Mac | hypothesis v2 | `mac-hypothesis-v2.md` → Win inbox |

**H4 headline (Win 27B):** ~33s wall on coding prompt (`clamp`); reasoning model returned thinking tokens only — Mac Ollama 9B parallel run still pending for comparison.

---

## 2026-06-28 — CI: 4-byte UTF-8 mojibake cp1252 second-byte gap | Cursor

**Fix:** `32722d5` — `_SECOND_F0` in `scripts/review/repo_hygiene.py`  
**Symptom:** CI `test_four_byte_utf8_mojibake_is_blocked` failed — emoji mojibake (`U+0178` from byte `0x9F`) not detected after RFC 3629 tightening in `820e078`  
**Pattern:** F0 lead-byte sequences must match cp1252-mapped second bytes (`0x91`–`0x9F`), not only latin-1 `U+0090`–`U+00BF`

---

## 2026-06-28 — Mac↔Win co-orchestrator: file inbox + PT `.agent` memory | Cursor

**PT working card:** `.agent/memory/working/CO_ORCHESTRATOR_LAN_PEER_2026-06-28.md`  
**orama playbook:** [`mac-co-orchestrator-playbook.md`](../../orama-system/bin/orama-system/skills/hermes-harness/references/mac-co-orchestrator-playbook.md)  
**GitHub:** https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/hermes-harness/references/mac-co-orchestrator-playbook.md

**Machine lessons:** `lesson_87636d658879` … `lesson_64dedfe61cfa` (15 co-orchestrator rows in `.agent/memory/semantic/lessons.jsonl`)

### Where Mac co-orchestrator + subagents look

| Role | Path |
|------|------|
| **Mac co-orchestrator** | `.agent/memory/working/MAC_CO_ORCHESTRATOR_WHERE_TO_LOOK_2026-06-28.md` |
| **Mac subagents** (mac-researcher, etc.) | `.agent/memory/working/MAC_SUBAGENTS_WHERE_TO_LOOK_2026-06-28.md` |
| Shared landmark | `.agent/memory/working/CO_ORCHESTRATOR_LAN_PEER_2026-06-28.md` |
| All agents | `.agent/memory/semantic/LESSONS.md` + `DOMAIN_KNOWLEDGE.md` |
| mac-researcher inbox | `~/.openclaw/state/lan_peer/inbox/` (local Mac assignments) |
| Win autoresearcher | `.agent/memory/working/WIN_AUTORESEARCHER_WHERE_TO_LOOK_2026-06-28.md` |
| Ops / tokens | `.agent/memory/working/LAN_PEER_L2_TOKEN_LANDMARK_2026-06-28.md` |

### Gold nuggets

1. **File inbox beats WS** for autoresearch fan-out — `POST /api/peer-file`, fan-out manifest by `assignee`
2. **Win inbound** — Mac drops are already local; do not use `--peer` to read them on Win
3. **Win outbound** — `drop --peer` → Mac reads with `read --peer --name`
4. **Mac unblock** — `git pull` orama `>= 9f89051`, `./start.sh --lan-peer` (peer-file 404 on stale portal)
5. **Partial fanout** — Mac proceeds when Win peer-file not yet live
6. **autoresearch_bridge** — SSH `GPU_BOX` path vs LAN HTTP + file handoff on Win
7. **Mac inference** — Ollama warm (`:11434`) primary; LM Studio passive (`:1234`) — route Mac subagents to `ollama-mac`

---

## 2026-06-28 — Windows `start.ps1` rehab: flags, read-only `$PID`, uvicorn paths | Cursor

**orama fix:** `2717eee` (`platform/windows/start.ps1`) · **PT memory:** `lesson_0d5d6b4a25eb`, `lesson_52add7792e48`, `.agent/memory/working/START_PS1_LAN_PEER_2026-06-28.md` · **Verified live:** `start.ps1 --no-open` → PT `:8000`, orama `:8001`, Portal `:8002` UP (exit 0)

### Failures (pre-fix)

| Symptom | Root cause |
|---------|------------|
| `--no-open` parameter not found | PowerShell `[switch]` params reject `--kebab-case`; need `$args` parsing like `start.sh` |
| `--status` / `--stop` abort | Assigned to read-only automatic `$PID` — use `$listenerPid` |
| Ports 8001/8002 never open | Wrong uvicorn modules (`api_server:app` vs `orama_system.api_server:app`) + `PYTHONPATH` |
| Start crashes before services | `EnvironmentVariables.Contains()` — must use `.ContainsKey()` |

### Operator sequence (Win)

```powershell
$env:PERPETUA_TOOLS_PATH = "<canonical PT clone>"
.\platform\windows\start.ps1 --stop
.\platform\windows\start.ps1 --no-open
.\platform\windows\start.ps1 --status
```

Set `PERPETUA_TOOLS_PATH` before start — wrong sibling path degrades hardware policy to cache-only.

---

## 2026-06-28 — LAN peer bidirectional talk attempts (Win session) | Cursor

**Full log (orama):** [`docs/guides/lan-peer-bidirectional-talk-2026-06-28.md`](../../orama-system/docs/guides/lan-peer-bidirectional-talk-2026-06-28.md)

### Network (live)

| Host | LAN IP | Notes |
|------|--------|-------|
| Win RTX | `<YOUR_LAN_IP>` | LM Studio + stack |
| Mac Studio | `<YOUR_LAN_IP>` | **Not** `.110` (stale default) |

### What worked

- Inference Mac↔Win over LM Studio HTTP (`:1234`) both directions
- `discover.py --force` subnet scan finds Mac at `.102`; `last_discovery.json` updated
- Win `probe_lan_peer.py` → Mac `portal-health` PASS after Mac `--lan-peer`

### What blocked full L2 round-trip

- `portal-status` 401 until **same** `ORAMA_CONTROL_PLANE_TOKEN` on both `.env.local`
- Win services must restart with `--lan-peer` (bind `0.0.0.0`, not `127.0.0.1` only)
- Cross-peer `POST /api/user-input` message queue — **v2 increment**, not wired

### Code fixes (same session)

- orama `discover.py`: Windows subnet scan; `start.ps1`: repo discover + `last_discovery.json`, no `.110` fallback
- PT: removed `<YOUR_LAN_IP>` defaults from `agent_launcher.py` / `alphaclaw_bootstrap.py`

---

## 2026-06-28 — LAN P2P transport research: WS-primary + SSE/POST-fallback plan | Claude Code

**orama docs:** [`docs/guides/lan-peer-bidirectional-talk-2026-06-28.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/guides/lan-peer-bidirectional-talk-2026-06-28.md) · **Commits:** orama `ca96862`, `f63ec72`

### What was learned

1. **FastAPI WebSocket (zero deps) is the simplest/most frugal LAN P2P transport** for a 2-host Python/FastAPI stack — already bundled in `fastapi[standard]`. Dual-socket pattern (each side is server + client) gives full-duplex at <1 ms LAN latency with ~40 LoC.
2. **SSE + POST is the correct HTTP-only fallback** — `GET /events/peer-stream` + `POST /api/peer-event`, two connections per direction, zero new packages. Degrades cleanly when WebSocket is firewalled or the peer doesn't support it.
3. **Channel manager pattern:** `lan_peer_channel.py` abstracts both transports behind `send()` / `on_inbound()`. State machine: `WS_CONNECTING → WS_CONNECTED | SSE_CONNECTING → SSE_CONNECTED | DISCONNECTED (30 s retry)`. Shared JSON envelope `{type, source, ts, data}` makes the transport invisible to callers.
4. **PT impact:** `probe_lan_peer.py` gains a `ws-peer` check in Phase 4 — probes `ws://{PEER_IP}:8002/ws/portal-peer` with a 5-second handshake test. No new deps.
5. **Transport upgrade ladder:** ZeroMQ PAIR (1 dep: `pyzmq`) for sub-ms or N>2 hosts; mDNS/zeroconf (1 dep) auto-discovers peer IP as `_orama._tcp.local.` — replaces `$MAC_IP`/`$WIN_IP` env vars. Both deferred until WS+SSE/POST channel is stable.

### Decisions

- Reuse-first: zero new packages in Phases 1–4. ZeroMQ/mDNS only if WS+SSE/POST proves insufficient.
- 5-phase sequence: endpoints → channel manager → lifespan hook → ws-peer probe → L3 agent dispatch.

---

## 2026-06-28 — LAN peer self-talk: Mac↔Win orama installs over HTTP | Cursor

**Canonical operator playbook (Mac + Win — identical):**
[`orama-system/.../lan-peer-self-talk.md#operator-playbook`](../../orama-system/bin/orama-system/skills/hermes-harness/references/lan-peer-self-talk.md#operator-playbook)

Both machines: `git pull --ff-only origin main` in orama-system, then follow playbook §A–§E.
Hermes slash: `/lan-peer-self-talk` · `.agent`: `lesson_12ddf8cf63b9`

### Rehab note (missing-LESSONS branch, merged)

Commit `2d6225a` on a **stale Perplexity-Tools clone** tried to `learn.py` a **workstation path** as the lesson claim (`%USERPROFILE%\...\hermes-integration-authority.md`). That violates path-hygiene (LINT-006). This branch replaces it with semantic lessons in `docs/LESSONS.md` + `.agent` (`lesson_12ddf8cf63b9` already on `main`) — **do not merge `2d6225a`**.

---

## 2026-06-28 — Hermes integration authority: PT is not a lesson-mining dependency | Cursor

**orama plan:** [`orama-system/docs/plans/2026-06-28-hermes-integration-authority.md`](../../orama-system/docs/plans/2026-06-28-hermes-integration-authority.md) · **orama commits:** `2e284a5`…`9d5f4e6` on `main` · **PT memory:** `.agent/memory/working/HERMES_INTEGRATION_AUTHORITY_2026-06-28.md`

### What was learned

1. **Hermes dispatch is orama-owned** — envelope, registry, and thin-wrapper installer live in `orama-system/bin/orama-system/skills/hermes-harness/`. PT supplies hardware-policy **runtime** YAML/API via one-way import; it does **not** own Hermes slash commands or lesson graduation.
2. **Four required thin wrappers** — `pt-orama-council`, `pt-orama-review`, `pt-orama-delegate`, `pt-hardware-policy`. Regenerate after pull: `python bin/orama-system/skills/hermes-harness/scripts/install_hermes_thin_skills.py --install --verify` (from orama root).
3. **Lesson-mining is optional** — `pt-orama-lesson-mining` installs only with `--include-optional`. No hard dependency on PT `learn.py`, `.agent` layout, or any specific graduation CLI. Do not wire PT bootstrap or `POST /autoresearch/sync` gates to this command.
4. **Sticky routing** — dispatch envelope → `hermes-universal-invocation-protocol.md`; partner audit → L2 `transport`; delegation → `agent_id` + `executor_id`; hardware on Windows Hermes → `pt-hardware-policy` command card + `start.ps1 --hardware-policy`.
5. **`PERPETUA_TOOLS_ROOT` unchanged for hardware** — still required for `discover.py` / `hardware_policy` import when running PT-side launchers; unrelated to optional lesson-mining.

### Decisions made

- DOMAIN_KNOWLEDGE gold nuggets and working memory updated; orama canonical bodies enriched — PT `.agent` references, does not duplicate procedure.
- Mac E2E for cross-harness `--hardware-policy` remains deferred (see orama `docs/plans/2026-06-28-mac-e2e-handoff.md`).

### Sync (both repos)

```bash
cd orama-system && git pull --ff-only origin main && python scripts/sync_version.py --check
python bin/orama-system/skills/hermes-harness/scripts/install_hermes_thin_skills.py --install --verify
cd ../Perpetua-Tools && git pull --ff-only origin main
```

---

## 2026-06-27 — Pre-v2 security hardening (Linux complete; Mac/Win E2E tomorrow) | Cursor

**Branch:** `cursor/security-hardening-pre-v2-c4ae` · **PRs:** [orama #113](https://github.com/diazMelgarejo/orama-system/pull/113) · [PT #154](https://github.com/diazMelgarejo/Perpetua-Tools/pull/154) · **Versions:** `1.1.1.0` both repos

**Context:** Last hardening pass before `v1.x-stable` freeze and `oramasys/v2-foundation` migration. Plan: [`orama-system/docs/plans/2026-06-27-security-hardening-pre-v2.md`](../../orama-system/docs/plans/2026-06-27-security-hardening-pre-v2.md).

### Perpetua-Tools (Linux ✅)

| Tier | Deliverable |
|------|-------------|
| T1-A | `_PT_STATE_SCHEMA` + `_validate_pt_state()` — RFC-1918 endpoint allowlist in `alphaclaw_bootstrap.py` |
| T1-B/C | URL canonicalization + `scripts/audit_policy_enforcement.py` pre-commit |
| T2-B | `scripts/check_model_ids.py` configuration-derived model provenance validation (`config/models.yml`, `.env.example`) |
| T3-B | 6 parametrized malformed `Co-authored-by` fuzz tests |

### orama-system (Linux ✅)

| Tier | Deliverable |
|------|-------------|
| T2-A/C | LINT-014 argv secret scan; line-level LINT-013 (`<!-- LINT-013-ok -->`) |
| T3-A | `tests/test_concurrent_lock.py` — 8 threads, ≤1 simultaneous lock holder |
| T3-C | Orphan pending → `registry/orphan-conflicts/` on clear + `sweep_orphan_pending()` on open |
| T4-A/B/C | `check_dep_pins.py`; LM Studio token WARN in `check-local-env.sh`; SBOM `docs/sbom/sbom-v1.1.1.0.json` |

### Blocked on Mac / Windows 11 (schedule tomorrow)

- Full `start.sh` E2E + `probe_required_endpoints` (Ollama `qwen3.5:9b-nvfp4`, `bge-m3`)
- `LM_STUDIO_WIN_ENDPOINTS` LAN probes from Mac
- `start.sh --hardware-policy` live harness
- Claude Desktop MCPB `--open`; keychain `security` CLI flows
- **T5:** tag `v1.1.1`, GitHub release, `oramasys/v2-foundation` branch — only after real-machine E2E green

### Verification (cloud VM)

- orama: pytest 33/33 (store, engine, concurrent lock); `repo_hygiene.py` OK
- PT: bootstrap 14/14; fuzz 6/6; `check_model_ids.py` exit 0
- `gbrain-selfheal.sh` skipped (gbrain not on PATH)

**Machine memory:** PT `.agent/memory` lessons `learn.py` batch + episodic `2026-06-27-security-hardening-linux-complete`.

### Follow-up (same day): PR summary append-only + gold nuggets

- **Incident:** PT [#154](https://github.com/diazMelgarejo/Perpetua-Tools/pull/154) body was replaced with CodeRabbit-only follow-up text — original pre-v2 scope erased. Restored via integrative synthesis; follow-ups appended below original.
- **Rule:** PR descriptions are **append-only** (same as `LESSONS.md`). New work → `## Follow-up:` section; never wholesale replace.
- **`.agent` memory:** `lesson_3b13ab0a45d4` (append-only PRs), `lesson_257a631cbfd3` (synthesize merge mode); DECISIONS §2026-06-27 PR append-only; episodic gold nuggets `PR154-summary-append-only-gold-nugget`, `PR158-synthesize-mode-gold-nugget`.
- **Canonical:** [orama `integrative-merge.md`](../../orama-system/blob/main/bin/orama-system/skills/oramasys-method/references/integrative-merge.md)

---

## 2026-06-26 — PR #135 CodeRabbit closure: memory path hygiene at write boundaries | Cursor

**Context:** PR #135 (`cursor/critical-bug-investigation-a924`) was merged before all four CodeRabbit threads were closed at root cause. CodeRabbit autofix on `80926a3` only hand-edited `REVIEW_QUEUE.md` (`<local-path>` placeholders) — a symptom patch.

**Root-cause fixes (this follow-up PR):**

1. **Central module** — `.agent/memory/path_hygiene.py` with `sanitize_tracked_path_leaks()` + `sanitize_json_strings()`.
2. **Write boundaries** — episodic `log_execution()`, `learn.py`, `graduate.py`, `write_review_queue_summary()` all sanitize before persist.
3. **Legacy scrub** — `.agent/tools/scrub_memory_paths.py` redacts existing episodic/lessons/candidate JSON; re-renders `LESSONS.md`.
4. **LINT-006 gap** — `repo_hygiene.py` now catches Windows `%USERPROFILE%`-style user paths (previously only Unix `/Users/`).
5. **REVIEW_QUEUE preamble** — `<!-- review-queue-dynamic -->` marker preserves curated static header across `graduate.py` re-renders.
6. **Coauthor guard** — already on main: email allowlist fail-closed before marker check + regression tests.

**Invariant:** Never edit derived memory markdown by hand to hide paths — sanitize at the writer or scrub the JSONL source, then re-render.

---

## 2026-06-25 — discover.py Windows platform fix + Hermes plan review | Claude

**PT-relevant findings:**

1. **discover.py platform role reversal was broken** — `discover_endpoints()` always labeled `localhost:1234` as "mac", then filtered `windows_only` models from it. On Windows this stripped out the primary inference models. Fixed in `orama-system/scripts/discover.py` with `RUNNING_ON_WINDOWS = sys.platform == "win32"`; when Windows: `localhost → win`, `$MAC_IP → mac`. After fix `win` models = `[qwen3.5-27b-claude-4.6-opus-reasoning-distilled-v2, gemma-4-26b-a4b-it, text-embedding-qwen3-embedding-8b-i1-gguf-q6-k]`.

2. **`PERPETUA_TOOLS_ROOT` must point to PT repo root for hardware_policy import** — `discover.py` does `sys.path.insert(0, str(pt_root))` and then `import utils.hardware_policy`. This only works if `pt_root` is the PT repo root (i.e., the directory that contains `src/utils/`). If `PERPETUA_TOOLS_ROOT` is unset, discovery falls back to the local filter silently — set it on Windows startup: `$env:PERPETUA_TOOLS_ROOT = "$REPO_ROOT" (resolve via `git rev-parse --show-toplevel` in the PT checkout)`.

3. **Plan corrections** — orama Hermes onboarding plan Phase 1 task 1 referenced `resolve_local_or_remote()` which does not exist in PT. Real primitives: `_loopback_host_from_endpoint`, `_is_local_endpoint`, `_get_local_ips` in `src/perpetua_tools/agent_launcher.py`. Plan corrected.

4. **Win LM Studio live** — `http://<YOUR_LAN_IP>:1234` (also `localhost:1234` from the Win host). Models confirmed from `/v1/models`: `qwen3.5-27b-claude-4.6-opus-reasoning-distilled-v2`, `gemma-4-26b-a4b-it`, `text-embedding-qwen3-embedding-8b-i1-gguf-q6-k`.

---

## 2026-06-22 — Full session: assumption failure, oramasys v2 src-layout, gbrain durability

> **For manual merge with the `.agent/` memory system.** This is the human-readable
> consolidation; the canonical machine records are PT `.agent/memory/semantic/LESSONS.md`
> (lessons `2e154f1b55ab`, `d892d844cf60`, `0afc8c5f2778`, `a7374ba4b00d`, `36f924c161e1`,
> `d0d49b68ab24`) and orama-system [`docs/LESSONS.md` §2026-06-22 (×2)](../../orama-system/docs/LESSONS.md).

### 1. DO-NOT — catastrophic assumption (`.agents` vs explicit `.agent`)

Told to write memory to `.agent/memory`, the AI silently "corrected" it to `.agents/memory`
and committed there, on a **stale branch**, never reading `.agent/AGENTS.md` — which defined
`.agent/` as the canonical structured brain (rendered `LESSONS.md` via `learn.py`, never
hand-edited). Wrong commit erased by re-anchoring to `origin/main`. Compounding failures:
overrode an explicit instruction with a guess; judged branch freshness by ahead/behind instead
of comparing the HEAD **tree** to origin; let an iCloud-move tangent replace the stated #1 task.

- **Enshrined as standards** (orama, ours): AFRP Intent-Verification **trigger 3** in
  [`bin/orama-system/afrp/SKILL.md`](../../orama-system/bin/orama-system/afrp/SKILL.md);
  **Target Verification (pre-insert)** in [`bin/orama-system/cidf/SKILL.md`](../../orama-system/bin/orama-system/cidf/SKILL.md).
- **Rule:** take explicit names verbatim; read the area's `AGENTS.md`/`_index` first; verify you
  are current (tree, not ahead/behind); ASK if it still seems wrong; keep the #1 task primary.

### 2. oramasys v2 — clean src-layout adopted (the original #1 task)

`perpetua-core` and `oramasys` moved to PyPA src-layout: `src/<pkg>/`, tests **inside**
`src/tests/`, thin `/bin` (perpetua-core `bin/test`; oramasys `bin/serve`), `README`, minimal
root. Verified **62 / 5** tests, merged + pushed (`perpetua-core 8c063f4`, `oramasys 0f5ba2b`).
`agate` left as-is (spec repo). Why v2 now: v1 tangled concerns + clutter; v2 = clean-slate
microkernel split (perpetua-core kernel ← oramasys graph/API, one-way boundary), locked clean
while small. Full account: [`docs/2026-06-22-oramasys-v2-intent-and-interpretation-gap.md`](2026-06-22-oramasys-v2-intent-and-interpretation-gap.md)
· decision: `.agent/memory/semantic/DECISIONS.md` §2026-06-22.

### 3. gbrain sync durability — stop re-fixing it

Two **recurring** root causes (don't re-diagnose): (a) `gbrain autopilot --repo .` is a launchd
agent (`com.gbrain.autopilot`, `KeepAlive=true` — kill won't stop it, only `launchctl unload -w`)
that jams on unacked parse failures and silently stales sources; (b) every repo move spawns a new
per-path source and orphans the old one — left "pending removal" they resurface as
`sync_freshness`/`multi_source_drift` every session. Durable fix:
[`orama-system/scripts/gbrain/gbrain-selfheal.sh`](../../orama-system/scripts/gbrain/gbrain-selfheal.sh)
(idempotent; wired into `start.sh` backgrounded; doctor 50→95). Archived 4 orphan sources
(reversible; defs in `~/repo-backups/gbrain-stale-quarantine-20260622/`). Canonical procedure:
[`gstack/SKILL.md` §GBrain Ops §2/§5/§6/§7](../../orama-system/bin/orama-system/gstack/SKILL.md).
Gotcha: bare `gbrain sync` from a non-git cwd only acks failures then refuses — per-source sync
must `cd` into the repo (or `--repo`) + `--source`.

### 4. Cross-harness memory

This session's knowledge was stored for retrieval everywhere: Claude Code file memory, a gbrain
page (`lessons/gbrain-sync-durability`, retrievable from Claude Desktop which has the gbrain MCP),
and a claude.ai Mem note. Pattern: gbrain is the shared cross-harness brain; the git-tracked
orama skills + LESSONS travel with the repos.

---

## 2026-06-22 — Merged stray root `LESSONS.md` into the canonical `docs/LESSONS.md`

**Housekeeping:** a stray `LESSONS.md` at the repo root (tracked, 16 lines, dated 2026-04-21/22)
duplicated the lessons-log purpose. Its three entries were moved into this file **in date order**
(placed below with the other April entries, after the 2026-04-20 entry), one example path de-doxed
to a placeholder per LINT-006; the stray root file was then removed so `docs/LESSONS.md` is the
single canonical human log. (Other `LESSONS.md` paths are intentional and distinct:
`.agent/memory/semantic/LESSONS.md` = rendered `.agent` brain; `.claude/lessons/LESSONS.md` =
ECC redirect.)

---

## 2026-05-22 — RAG Memory Pipeline v1 Backport

**Context:**
Backported 4 RAG modules from the v2 design plan (`orama-system feat/rag-gstack-optional-v1`)
into `diazMelgarejo/Perpetua-Tools` on branch `feat/rag-backport-v1`.

**What shipped:**

- `orchestrator/gossip_bus.py` — aiosqlite event log with FTS5 BM25 keyword search + `_pending_embeds` GC guard + `embed_status` column
- `orchestrator/memory_embed.py` — httpx Ollama bge-m3 embed helper + `probe_embed_dim()` (Gap 1 fix)
- `orchestrator/memory_store.py` — LanceDB `EmbeddingStore(dim=...)` + `get_lance_store()` singleton (Gap 1 fix)
- `orchestrator/memory_rrf.py` — Pure Reciprocal Rank Fusion k=60 (zero deps)
- 27 new tests across 3 test files; 345/345 passing, 0 regressions

**Three gap fixes from external review (Antigravity Gemini 3.5):**

1. Gap 1 (dim hardcode → schema mismatch): `probe_embed_dim()` + `EmbeddingStore(dim=...)` + env var override
2. Gap 2 (FTS5 silent failure on special chars): `_sanitize_fts_query()` strips operators before MATCH
3. Gap 3 (GC test was a tautology): real `asyncio.sleep` behavioral test verifies `_pending_embeds` lifecycle

**Key invariant learned:**
GossipBus in v1 (Perpetua-Tools) is a NEW capability — PT had no SQLite/event log before.
The v2 design targets `oramasys/perpetua-core`; v1 backport adapts module paths to `orchestrator/`.
NEVER write code to `oramasys/*` — plans only via `/docs/v2/` in v1 repos.

**Release notes:** `docs/2026-05-22-rag-backport-v1-release-notes.md`

---

## 2026-04-26 — Hardware Model Affinity Incident

**Context:**
`orama-system/scripts/discover.py` was writing unfiltered LM Studio model lists
to `openclaw.json`. This could cause `lmstudio-mac` to advertise Windows-only
27B/26B models, creating a hardware damage risk on the M2 Pro, while
`lmstudio-win` could advertise Mac-only MLX / Apple Silicon models.

**Root cause:**
Discovery trusted endpoint responses without cross-referencing a hardware policy.

**Defense-in-depth solution:**

- L1: `discover.py` filters through `Perpetua-Tools/config/model_hardware_policy.yml`
  before writing discovery state, `openclaw.json`, or `.env.lmstudio`.
- L2: `utils/hardware_policy.py`, `alphaclaw_manager.py`, and `agent_launcher.py`
  enforce affinity before routing/spawn decisions.
- L3: `api_server.py` returns HTTP 400 `HARDWARE_MISMATCH` at the API boundary.

**Canonical policy file:** `config/model_hardware_policy.yml`

**Known hallucinations removed:** `qwen3-coder-14b` and `gemma4:e4b` appeared in
AI-generated drafts of this plan. They are NOT verified model IDs in this system.
Do not re-add them.

**Status:** Implemented 2026-04-26.

**Follow-up — unified CLI/GUI management:**
Do not multiply human entry points. Hardware policy validation is exposed through
the existing orama CLI (`./start.sh --hardware-policy`, `./start.sh --status`)
and the existing Orama Portal (`http://localhost:8002`, Hardware Policy & Safe
Defaults section). `scripts/hardware_policy_cli.py` is a helper used by the
existing CLI, tests, and agents — not a separate product surface.

---

> **Canonical path**: `docs/LESSONS.md`
> **Previous path**: `.claude/lessons/LESSONS.md` (now redirects here)
> **Purpose**: GitHub-auditable persistent memory across all ECC, AutoResearcher, and Claude sessions.
> **Cross-repo companion**: [orama-system/docs/LESSONS.md](https://github.com/diazMelgarejo/orama-system/blob/main/docs/LESSONS.md)
>
> **Rules**:
>
> - Read this file at the start of every session
> - Append new learnings before ending a session
> - Keep entries dated and agent-tagged (`ECC | AutoResearcher | Claude`)
> - For organized, deep-dive explanations see the **[wiki →](wiki/README.md)**
> - For agent behavioral rules see **[SKILL.md →](../SKILL.md)**

---

## continuous-learning-v2

This repo uses [continuous-learning-v2](https://github.com/affaan-m/everything-claude-code/tree/main/skills/continuous-learning-v2).
Instincts: `.claude/homunculus/instincts/inherited/Perpetua-Tools-instincts.yaml`
Import command: `/instinct-import .claude/homunculus/instincts/inherited/Perpetua-Tools-instincts.yaml`

---

## Sessions Log

<!-- Append entries below. Format:
## YYYY-MM-DD — <agent: ECC | AutoResearcher | Claude> — <brief topic>
### What was learned
### Decisions made
### Open questions
-->

---

## 2026-04-13 — Claude — Startup fix: IP detection, stdin deadlock, concurrent backend probing

### Learned

- **Abort trap: 6 root cause**: `_gather_alphaclaw_credentials()` spawned a daemon thread calling `input()`. After `t.join(30)` timed out the thread was still alive and held the stdin `BufferedReader` lock; Python interpreter shutdown tried to flush/close that reader → SIGABRT. Three-layer fix: (1) `sys.stdin.isatty()` guard in Python skips the daemon thread in non-interactive mode, (2) `</dev/null` in start.sh redirects stdin so `input()` gets instant EOFError, (3) `stdin=subprocess.DEVNULL` on the AlphaClaw gateway `Popen` prevents the node process from inheriting the broken fd.

- **IP misconfiguration was silent**: `agent_launcher.py` read `MAC_LMS_HOST`/`WINDOWS_IP` from env but neither was exported by start.sh or present in `.env`. Fallback hard-coded defaults (`.103`, `.100`) were always used. Actual LAN addresses are `.110` (Mac LM Studio) and `.108` (Windows).

- **`.env.local` had wrong values**: `WINDOWS_IP=<YOUR_LAN_IP>` (off by several octets), `WINDOWS_PORT=1234` (LM Studio port incorrectly overriding the Ollama port — `REMOTE_WINDOWS_URL` pointed at LM Studio instead of Ollama). Fixed to `.108` / `11434`.

- **`agent_launcher.py` never called `load_dotenv()`**: it only saw shell-exported vars. Added `load_dotenv(".env")` + `load_dotenv(".env.local", override=True)` so `.env` files are always honoured.

- **`asyncio.create_task()` fires immediately; `gather()` blocks**: firing all 4 backend probes as tasks at t=0 and awaiting in two phases (local first, then LAN) gives correct ordering without sequential delay.

- **`_persist_detected_ips()`**: after each successful probe run, confirmed live endpoints are written back to `.env`. This makes the configuration self-correcting across restarts.

### Decided

- Hard-coded defaults in `agent_launcher.py` updated: `.110` Mac LM Studio, `.108` Windows.
- `network_autoconfig.py` `preferred_ips` updated to `.110` / `.108`.
- `LM_STUDIO_MAC_ENDPOINT` in both repo `.env` files updated to `http://<YOUR_LAN_IP>:1234`.
- `.env.local` corrected: `WINDOWS_IP=<YOUR_LAN_IP>`, `WINDOWS_PORT=11434`.

### Open

- Windows Ollama at `.108:11434` is probably not running — verify `windows_ollama_ok: false` path produces clean routing.json with `coder_backend: windows-lmstudio`.

→ [wiki/06-startup-ip-detection.md](wiki/06-startup-ip-detection.md)

---

## 2026-04-20 — Claude — Gate 1: Three-repo adapter, AlphaClaw HTTP client, alphaclaw_manager.py

### Learned

**Architecture decisions (do not re-debate):**

- `"type": "module"` in `packages/alphaclaw-adapter/package.json` conflicted with `require()` in all source files (copied from AlphaClaw, which is CJS). Fix: remove `"type": "module"`. Keep everything CommonJS in this package.
- `spawnSync` with `detached:true` does NOT actually detach — the parent blocks until the child exits. Always use `spawn` (not `spawnSync`) then `child.unref()` for detached background processes.
- Session cookies from AlphaClaw's `/api/auth/login` arrive in `res.headers["set-cookie"]` as an array. Must `map(c => c.split(";")[0]).join("; ")` to extract the key=value without attributes (Secure, HttpOnly, Path).

**AlphaClaw auth model (SETUP_API_PREFIXES):**

- Two auth tiers exist: "setup-allowlisted" (`/api/status`, `/api/gateway*`, `/api/restart-status`) accessible without a full session, and "session²" (`/api/models`, `/api/env`, `/api/watchdog/*`) requiring a cookie from `POST /api/auth/login`. Always probe via `/health` first (no auth), then setup-allowlisted endpoints, then login before calling session² endpoints.

**orchestrator/alphaclaw_manager.py pattern:**

- The `--env-only` flag pattern (print `export KEY='val'` lines, caller does `eval "$(...)"`) is the cleanest way to propagate PT-resolved env vars into a bash script without a temp file or JSON parsing in bash.
- `--resolve --env-only` pipes through `tee /dev/stderr` so progress messages appear in the terminal while `grep '^export '` captures only the eval-able lines.
- `subprocess.run()` with `capture_output=False` lets the Python child's stdout/stderr stream to the terminal in real time — critical for long-running operations like AlphaClaw bootstrap.

**start.sh thinning rule:**

- Sections 2a (backend probe) and 2c (mode determination) were gateway decision logic — they belong in PT, not in orama. If a shell script is making gateway routing decisions, it violates the PT-is-authoritative invariant.
- The thinned start.sh pattern: resolve via PT (`eval "$PT_ENV_EXPORTS"`), then unconditionally start services. The shell script is now a pure process manager, not a policy engine.

**Smoke test structure:**

- Group tests by auth tier (no-auth → setup-allowlisted → session-auth → watchdog) to match the contract document. This makes it obvious which section a failure belongs to.
- Mark destructive tests (restartGateway, watchdogRepair) as `null` (SKIP) by default; gate behind `SMOKE_DESTRUCTIVE=1` env var.
- Exit code 1 on any FAIL so CI can catch regressions.

**FUSE mount git limitations (still applies at Gate 1):**

- `git add`, `git commit`, `git push` in the sandbox FUSE-mounted paths often fail with `index.lock` or `Resource deadlock avoided`. Always provide Mac terminal commands for git operations.

### Decisions Made

- `packages/alphaclaw-adapter/src/index.js` is the **authoritative Node.js HTTP client** — 20+ exported functions, module-level session state, commandeer-first `discoverPort()`, proper detached `startServer()`.
- `orchestrator/alphaclaw_manager.py` is the **authoritative Python lifecycle manager** — absorbs start.sh §2a (backend probe) and §2c (mode determination). orama delegates entirely to this module.
- `packages/alphaclaw-adapter/scripts/smoke-test.js` is the **Gate 1 acceptance test** — run against live AlphaClaw before marking Gate 1 fully verified.
- Gate 1 is structurally complete. The one remaining step before Gate 1 is "fully" done: run smoke-test.js against a live AlphaClaw instance and register the MCP server in claude mcp.

### Open

- MCP server registration still pending: `claude mcp add --transport stdio alphaclaw -- node packages/alphaclaw-adapter/src/mcp/server.js`
- `packages/local-agents/tests/client.test.js` (Vitest) not yet run — pending Gate 1 verification step
- `lib/mcp/` and `lib/agents/` in AlphaClaw `feature/MacOS-post-install` not yet tagged for removal (wait for smoke-test green)
- `openclaw_bootstrap.py` in orama scope-down to apply-config only is Gate 2 work

→ [docs/MIGRATION.md §Gate 1](MIGRATION.md)
→ [docs/adapter-interface-contract.md](adapter-interface-contract.md)
→ [docs/adr/ADR-001-three-repo-adapter-architecture.md](adr/ADR-001-three-repo-adapter-architecture.md)

---

> **🔖 Salvaged from the removed stray root `LESSONS.md` (merged 2026-06-22, kept in date order; originally synced from [AlphaClaw `feature/MacOS-post-install` → `7-Lessons.md`](https://github.com/diazMelgarejo/AlphaClaw/blob/feature/MacOS-post-install/7-Lessons.md)):**
>
> #### [2026-04-21] Configuration Portability: OS-Agnostic Paths
> - **Problem**: Absolute paths (e.g., `/Users/<user>/…`) in `openclaw.json` break cross-platform deployments (Linux/Windows/macOS).
> - **Solution**: Always use `${HOME}` variables in configuration templates. The AlphaClaw gateway and onboarding runtime MUST resolve these variables relative to the OS-specific home directory.
> - **Action**: Enforce `${HOME}` in all `openclaw.json.template` and active configuration files. Avoid hardcoding usernames or absolute paths.
>
> #### [2026-04-21] Core Policy: Additive Ghost Orchestration
> - **Additive Configuration**: Never overwrite `openclaw.json`. Always read, deep-merge (via spread), and write back.
> - **Upstream Autonomy**: PT and Orama act as ghost orchestrators. They absorb and extend OpenClaw/AlphaClaw features without becoming structural dependencies.
> - **Non-Destructive Injection**: Use native onboarding hooks (like `writeManagedImportOpenclawConfig`) to inject PT/Orama configs.
> - **Portability**: Always use `${HOME}` variables for pathing to keep configurations OS-agnostic across Mac/Win/Linux.
>
> #### [2026-04-22] Symlink Portability & Validation
> - **Requirement**: Git must track symlinks as Mode 120000. Use `git ls-files -s` to verify.
> - **Automation**: Startup scripts (`start.sh`) MUST validate symlinks. If a link is missing or broken, the script should attempt to recreate it or provide clear instructions on where the missing sibling dependency should live.
> - **Agnostic Pathing**: Always use relative paths in symlinks (e.g., `../sibling`) rather than absolute paths to ensure portability across different clones.

---

## 2026-04-07 — Claude — Idempotent installs: subprocess permissions + model auto-discovery

### What was learned

- **`capture_output=True` silences bootstrap scripts** — never use in user-facing install flows; let stdout/stderr stream through
- **`npm install -g` does not guarantee execute bits** — `shutil.which()` finds the binary but `subprocess.run()` raises `PermissionError: [Errno 13]`; catching only `CalledProcessError` leaves it unhandled
- **Hardcoded model names break inference** — LM Studio returns `400`, Ollama returns `404` when model isn't loaded; always resolve via `/v1/models` or `/api/tags` at runtime
- **Windows GPU models cannot be called on Mac** — LAN isolation required; `<YOUR_LAN_IP>` (Windows) and `<YOUR_LAN_IP>` (Mac LMS) are distinct physical devices
- **AgentTracker `agents.json` must not share path with routing state** — flat routing dicts cause `AgentRecord(**v)` `TypeError`

### Decisions made

- `_resolve_ollama_model()` and `_resolve_lmstudio_model()` added — query backend before registering agent
- `openclaw_bootstrap.py` auto-`chmod +x` after `npm install -g` if execute bit missing
- `AgentTracker._load()` skips non-dict entries and rewrites file clean

### Commits

- `ffb1be0` (PT) — fix(researchers): auto-discover loaded model via /v1/models + /api/tags
- `d9e4f50` (PT) — fix(tracker): handle stale routing data in agents.json

→ [wiki/02-idempotent-installs.md](wiki/02-idempotent-installs.md)

---

## 2026-04-07 — Claude — Device identity + GPU crash recovery

### What was learned

1. **`127.0.0.1` and a LAN IP can point to the same physical machine** — UDP routing trick reveals outbound LAN IP; compare against configured endpoints before assigning roles
2. **One role per physical device** — if both Mac Ollama and Mac LM Studio are up on the same machine, two models would load on the same GPU; Ollama takes precedence
3. **Rapid model reload after crash burns GPU** — classify by HTTP status (503=loading, 404=unloaded, ConnectError=offline); enforce 30s cooldown minimum
4. **Terminal feedback during crash recovery is essential** — ASCII progress bar with role + countdown

### Prevention Rules

1. Always call `_get_local_ips()` before trusting any "remote" endpoint
2. One role per physical device — zero out probes whose host IP matches local IPs
3. On same device: Ollama > LM Studio deterministically
4. Crash recovery ≥ 30 seconds
5. Classify errors before sleeping — 503 ≠ 404 ≠ ConnectError
6. Show progress bar during recovery

### Commits

- `8af62f5` (PT) — feat(routing): one-role-per-device guard + GPU crash recovery cooldown

→ [wiki/03-device-identity.md](wiki/03-device-identity.md)

---

## 2026-04-07 — Claude — Idempotent gateway discovery (commandeer-first bootstrap)

### What was learned

- Probe before start: always check ALL candidate ports before launching any daemon
- Commandeer = use + refresh config, no restart — calling `onboard --install-daemon` when a gateway is running risks restarting and evicting models from GPU VRAM
- Protocol probe, not process check — identify by HTTP interface (`/health`, `/v1/models`), not by process name

### Prevention Rules

1. All bootstrap scripts: probe candidate ports FIRST, install/start LAST
2. Commandeer any compatible service found — do not start a duplicate
3. Never restart a running daemon in a bootstrap path
4. Set `*_GATEWAY_URL` / `*_ENDPOINT` env var after discovery for downstream use
5. Candidate port list must be env-configurable (`OPENCLAW_EXTRA_PORTS`, etc.)

### Commits

- `6bc40d0` (UTS) — feat(bootstrap): probe all candidate ports and commandeer any running gateway

→ [wiki/04-gateway-discovery.md](wiki/04-gateway-discovery.md)

---

## 2026-04-11 — Claude — AutoResearcher migration: karpathy → uditgoenka plugin

### Key Changes

1. **`AUTORESEARCH_REMOTE` is now an env var** (not hardcoded):

   ```bash
   AUTORESEARCH_REMOTE=https://github.com/uditgoenka/autoresearch.git  # default
   AUTORESEARCH_BRANCH=main  # default sync branch (was hardcoded 'master')
   ```

2. **Plugin install is primary mode:**

   ```bash
   claude plugin marketplace add uditgoenka/autoresearch
   claude plugin install autoresearch@autoresearch
   ```

3. **GPU runner is now secondary** (Verify substrate for `ml-experiment` task types only)

4. **`uv sync --dev`** replaces bare `pip install` in all bootstrap paths

5. **Valid Windows model names**:
   - `Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-v2` — valid 27B identifier
   - `Qwen3.5-27B-Instruct` **DOES NOT EXIST** — never use this string

→ [wiki/05-autoresearcher-migration.md](wiki/05-autoresearcher-migration.md)

---

## 2026-04-12 — Claude — 48-hour multi-agent sprint: collaboration patterns + version registry

### Version Number Registry — All Canonical Locations

**Current version: `0.9.9.7`.** Do NOT bump without explicit user instruction.

#### Perpetua-Tools (PT)

| File | Field |
|------|-------|
| `pyproject.toml:12` | `version = "0.9.9.7"` |
| `orchestrator/__init__.py:5` | `__version__ = "0.9.9.7"` |
| `orchestrator/fastapi_app.py:74` | `version="0.9.9.7"` |
| `orchestrator/fastapi_app.py:295` | `"version": "0.9.9.7"` (health JSON) |
| `orchestrator.py:97` | `VERSION = "0.9.9.7"` |
| `config/devices.yml:6` | `version: "0.9.9.7"` |
| `config/models.yml:6` | `version: "0.9.9.7"` |
| `SKILL.md:3` | `**Version:** \`v0.9.9.7\`` |
| `README.md:1,170` | `v0.9.9.7` |

### Multi-Agent Collaboration Protocol

1. **Read `docs/LESSONS.md` first** — scope claims are written here
2. **Scope claim** — append `## [IN PROGRESS] YYYY-MM-DD — Claude — <topic>` before touching files
3. **Additive changes** — prefer appending over rewriting; no conflict risk
4. **Commit body must name changed constants/APIs** — the only async channel between agents
5. **Never hardcode LAN IPs in source defaults** — `127.0.0.1` in code, real IPs in `.env` only
6. **One canonical source per constant** — two files defining the same IP will diverge
7. **Test isolation** — `autouse` fixture that restores module-level state after `importlib.reload()`

### Key Bugs Fixed This Sprint

- **Stash pop after rebase** — `alphaclaw_bootstrap.py` got both versions appended; required Python line-by-line surgery
- **Orphan branch in UTS** — `git merge-base` returned exit 1; fixed with `git reset --hard origin/main`
- **Hardcoded LAN IP broke CI** — `<YOUR_LAN_IP>` in fastapi_app.py defaults broke `test_health_uses_plain_string_defaults`
- **Test module state contamination** — `importlib.reload()` without restore leaked `AUTORESEARCH_DEFAULT_BRANCH = "dev"` across tests

### Pre-Commit Checklist

```bash
git fetch origin main
git log --oneline HEAD..origin/main          # changes by other agents
grep -rn "192\.168\." --include="*.py" | grep -v "test_\|#\|LESSONS\|\.env"
python -m pytest -q
```

### Commits

- `71a15f7` (PT) — fix(health): restore 127.0.0.1 loopback defaults

→ [wiki/07-multi-agent-collab.md](wiki/07-multi-agent-collab.md)

---

## 2026-04-13 — Claude — alphaclaw macOS compatibility patches + idempotent setup automation

### Error → Root Cause Map

| Startup error | Root cause | Fix |
| -------------- | ---------- | --- |
| `gog install skipped: Permission denied /usr/local/bin/gog` | `/usr/local/bin/` is root-owned on macOS | Change dest to `~/.local/bin/gog` |
| `Cron setup skipped: ENOENT /etc/cron.d/openclaw-hourly-sync` | `/etc/cron.d/` is Linux-only | macOS: use `crontab -l` user crontab |
| `systemctl shim skipped: EACCES /usr/local/bin/systemctl` | Linux/Docker-only shim | Wrap in `if (os.platform() !== "darwin")` |
| `git auth shim skipped: EACCES /usr/local/bin/git` | git shim dest hardcoded to root-owned path | Change to `~/.local/bin/git` |
| `Gateway timed out after 30s` | gateway exits on JSON schema error (`models` array undefined) | Add `models[]` arrays to ollama providers |

### `~/.local/bin` Precedence Pattern

PATH order on macOS: `~/.local/bin` (pos 4) → `/usr/local/bin` (pos 9). Installing to `~/.local/bin` = user-writable shadow of system paths. No `sudo` required.

### Idempotent Setup

`orama-system/setup_macos.py` (called from `start.sh` on every boot):

- Creates `~/.local/bin`, adds it to PATH in `~/.zshrc`
- Validates `~/.openclaw/openclaw.json` — adds `models[]` if missing
- Applies 6 alphaclaw.js patches idempotently (detect string guards)

→ [wiki/08-macos-alphaclaw-compat.md](wiki/08-macos-alphaclaw-compat.md)

---

## Wiki

All lessons above are expanded with root causes, exact fixes, and verification commands:

| # | Page | Topic |
| --- | --- | --- |
| 01 | [CI Dependencies](wiki/01-ci-deps.md) | pip extras, hatchling, pyproject.toml guard |
| 02 | [Idempotent Installs](wiki/02-idempotent-installs.md) | execute bits, capture_output, model discovery |
| 03 | [Device Identity](wiki/03-device-identity.md) | one-role-per-device, GPU crash recovery |
| 04 | [Gateway Discovery](wiki/04-gateway-discovery.md) | commandeer-first bootstrap, candidate ports |
| 05 | [AutoResearcher Migration](wiki/05-autoresearcher-migration.md) | uditgoenka plugin, uv sync, valid model names |
| 06 | [Startup IP Detection](wiki/06-startup-ip-detection.md) | stdin deadlock, load_dotenv, asyncio probing |
| 07 | [Multi-Agent Collab](wiki/07-multi-agent-collab.md) | version registry, scope claims, orphan branches |
| 08 | [macOS alphaclaw Compat](wiki/08-macos-alphaclaw-compat.md) | EACCES fixes, ~/.local/bin, setup_macos.py |

## 2026-04-26 — Claude — Cross-repo import pattern for hardware_policy

### What was learned

**utils/hardware_policy.py is PT-owned; orama imports via sys.path**
The canonical approach: orama's `api_server.py` and `scripts/discover.py` both resolve
`PERPETUA_TOOLS_ROOT` (env var with sibling-dir fallback) and call
`sys.path.insert(0, PERPETUA_TOOLS_ROOT)` to import `utils.hardware_policy` at runtime.
This avoids packaging the module twice or adding a git submodule.

**Fallback must be visible in logs**
If `PERPETUA_TOOLS_ROOT` path doesn't exist or the import fails, the except block
now emits `logger.warning(...)` with the resolved path. Operators can see when
enforcement is silently disabled.

**pre-commit hook blocks hallucinated model IDs**
`scripts/check_no_hallucinated_models.py` is registered as a pre-commit hook in both repos.
It blocks `qwen3-coder-14b` and `gemma4:e4b` — IDs that appeared in AI-generated plan drafts
but are not verified model IDs in this system. Add to this list whenever a hallucination is
discovered in any plan or code review.

### Decisions made

- PT owns `utils/hardware_policy.py` and `config/model_hardware_policy.yml`
- orama consumes via sys.path injection, not packaging or submodule
- `shared:` section intentionally empty until both machines are verified online

### Follow-up

- Populate `shared:` section after live `discover.py --status` run (Part 2 plan)
- Document `PERPETUA_TOOLS_ROOT` in both repos' `.env.example`

---

## 2026-04-26 — Codex — Windows CLI shims and AlphaClaw PR lessons (Apr 15-26)

### What was learned

**Windows command resolution should be user-local and runtime-anchored**
Use `%USERPROFILE%\.lmstudio\bin` for stable PowerShell shims instead of relying on
versioned app install paths. Anchor Node to LM Studio's bundled runtime at
`%USERPROFILE%\.lmstudio\.internal\utils\node.exe`, and keep npm's global prefix inside the
same user-owned bin directory so globally installed CLIs resolve predictably.

**npm-generated PowerShell launchers need a nearby node.exe**
The `gemini.ps1` and `codex.ps1` launchers generated by `npm install -g` expect `node.exe`
beside them on Windows. If symlink creation requires elevation, a user-owned hardlink from
`%USERPROFILE%\.lmstudio\bin\node.exe` to LM Studio's node keeps the setup frugal and avoids
maintaining a separate Node install.

**Git should follow GitHub Desktop, not a pinned app-* path**
`git.cmd` should resolve GitHub Desktop's bundled Git dynamically. This avoids breakage when
GitHub Desktop updates its versioned installation directory.

**AlphaClaw PR fixes need targeted regression proof**
The macOS post-install branch needed focused tests after conflict resolution:
`tests/server/routes-onboarding.test.js`, `tests/server/gateway.test.js`, and
`tests/server/routes-system.test.js`. The important behaviors were starting the managed
scheduler after onboarding installs hourly sync config and rejecting named cron tokens on the
managed scheduler path because the parser is numeric-only.

### Decisions made

- Keep machine-specific Windows launchers outside the repo and document the setup here.
- Verify PowerShell wiring with `git --version`, `node --version`, `npm --version`, `gemini --version`, and `codex --version`.
- Keep the AlphaClaw code-fix branch separate from process/documentation lessons so review stays narrow.
- Confirmed toolchain snapshot: Git `2.53.0.windows.3`, Node `v25.5.0`, npm `11.12.1`, Gemini CLI `0.39.1`, Codex CLI `0.125.0`.

### Follow-up

- After LM Studio updates, recheck that `%USERPROFILE%\.lmstudio\bin\node.exe` still maps to the intended bundled runtime.

---

# 2026-04-27 — Part 2 Complete: Affinity Key Normalization, Disaster Recovery, Gemini Plan Review

## Changes landed

**G3 — device_affinity → affinity key rename (PT side):**

- `config/routing.yml` autoresearch routes: `device_affinity` → `affinity`
- Value `win-rtx3080` preserved — future Windows hardware profiles (e.g. win-rtx4090) share the windows_only blocklist but need distinct whitelists. Device-specific affinity is the extension point. **Never normalize `win-rtx3080` to generic `win`.**
- Fixed stale test: `ULTRATHINK_ENDPOINT` → `ORAMA_ENDPOINT` (the rename had happened in routing.yml but the test didn't track it)
- Regression guard: `test_routing_affinity_keys_normalized` blocks future re-introduction of `device_affinity` key

**G1 — shared: section:**

- Commented out in `config/model_hardware_policy.yml` with TODO pointing to Part 2 Phase 5
- Added `_POLICY_CACHE` autouse fixture to clear module-level cache between tests (prevents test-ordering contamination)
- Parametrized test covers all 3 YAML variants (commented-out, absent, explicit-empty) × both parsers (PyYAML + `_simple_policy_parse`)

**G2 — PERPETUA_TOOLS_ROOT:**

- Documented in `.env.example` with cross-repo usage context

## Disaster Recovery Pattern (owned by orama, mirrors here for cross-repo context)

`HardwarePolicyResolver` in `orama/api_server.py` implements:

1. **PT-first**: import from `PERPETUA_TOOLS_ROOT` → authoritative
2. **Cache fallback**: `config/hardware_policy_cache.yml` → degraded (CRITICAL warning)
3. **Hard fail if cache missing**: never silently skip enforcement

**Key invariant for PT:** orama will ALWAYS try PT first and defer to PT's decisions. The cache is strictly a last resort for DR scenarios, not a way to bypass PT. PT remains authoritative — orama will call back to PT on every start and include `policy_source` in response metadata so ops can detect when the fallback was used.

## Gemini v3.1 Plan Review

**Accepted:** G2 (env docs) and G4 (hallucination purge — already done).

**Rejected — symlink proposal:** `orama/utils/hardware_policy.py → PT/utils/hardware_policy.py`. Fragile: breaks on Windows (no Unix symlinks), breaks in Docker/CI when repos at different mount paths, breaks when repos cloned to different locations. sys.path injection is more portable and already works.

**Rejected — remove _simple_policy_parse:** This fallback exists for PyYAML-absent environments. Removing it trades elegance for fragility.

## Test counts

- PT: 24/24 (16 → +8 new tests)
- orama: 23/23 (16 → +7 new schema tests)

---

## Session 2026-04-27b — Agent Automation + Portal Integration

### Codex PTY Automation Pattern (CRITICAL — add to all agent skills)

**Problem:** Codex `--full-auto` requires a TTY. Spawning from Python subprocesses fails with "stdin is not a terminal".

**Automated solution using `pty.openpty()`:**

```python
import pty, select, os, subprocess

master_fd, slave_fd = pty.openpty()
proc = subprocess.Popen(
    ["codex", "--full-auto", task],
    stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
    close_fds=True, cwd=str(repo_root),
)
os.close(slave_fd)
# Collect output via master_fd with select() + timeout
```

**This makes Codex 100% automatable — no human terminal needed, works from Claude Code, CI, FastAPI, or any Python subprocess.**

See: `orama-system/scripts/spawn_agents.py → _dispatch_codex()`

### Gemini CLI Fix

```bash
# Create wrapper in ~/.local/bin/gemini:
#!/usr/bin/env bash
exec /path/to/nvm/v24/bin/node /path/to/nvm/v24/bin/gemini "$@"
```

Fixes `??= SyntaxError` when shell resolves `node` to v14.
Auto-created by `scripts/setup_codex.sh` on every stack startup.

### Tools Available (cross-session reference)

| Tool | Status | How to use |
|------|--------|-----------|
| Codex | ✓ via PTY | `spawn_agents.py --agent codex` |
| Gemini CLI | ✓ via wrapper | `spawn_agents.py --agent gemini` or `~/.local/bin/gemini --yolo -p "..."` (yolo = auto-approve; required non-interactive) |
| LM Studio Mac | ✓ when .110 online | `spawn_agents.py --agent lmstudio-mac` |
| LM Studio Win | ✓ when .101 online | `spawn_agents.py --agent lmstudio-win` (GPU serialized) |
| All agents | parallel + serial | `spawn_agents.py --agent all` |

### Module Loading Pattern (sys.modules registration)

When loading a Python module with `importlib.util.exec_module` and it contains dataclasses:

```python
mod = importlib.util.module_from_spec(spec)
sys.modules['module_name'] = mod  # MUST register before exec_module
spec.loader.exec_module(mod)       # otherwise dataclass field annotations fail
```

## [2026-04-27] Hardware × Agent Matrix Test — Full Results

### Confirmed Facts

- **Model IDs are case-sensitive** in LM Studio. Config `Qwen3.5-9B-MLX-4bit` fails with HTTP 400.
  Correct IDs (all lowercase): `qwen3.5-9b-mlx`, `qwen3.5-27b-claude-4.6-opus-reasoning-distilled-v2`
  Also: Mac LM Studio does NOT have the `-4bit` suffix in the model ID.

- **openclaw CLI requires Node.js ≥ v22**. System default (v14.21.3) fails instantly.
  Fix: `export PATH=$HOME/.nvm/versions/node/v24.14.1/bin:$PATH` or use full path.
  Installed at: `~/.nvm/versions/node/v24.14.1/bin/openclaw`

- **Both LM Studio nodes load the same models** (MLX 9B and GGUF 27B):
  - Mac `localhost:1234`: `qwen3.5-9b-mlx` (ctx=56384, MLX), `qwen3.5-27b-...` (ctx=131072, GGUF)
  - Win `<YOUR_LAN_IP>:1234`: `qwen3.5-27b-...` (ctx=131072, GGUF), `qwen3.5-9b-mlx` (ctx=56384)

- **Both models are extended thinking/reasoning models.** They generate `<think>` blocks
  (stored in `reasoning_content`) before visible output. This makes agent turns slow:
  - Win 27B GGUF (RTX 3080): 107–130s per agent turn ✅ succeeds
  - Mac 9B MLX: 105–308s per agent turn ✅ succeeds (via Gemini fallback on long turns)
  - Direct API calls (tiny prompt): Mac 9B ~8–15s, Win 27B ~3s

- **Mac 9B stall root cause**: Parallel=1 + reasoning model generates large think blocks.
  Multiple rapid test requests queue up in LM Studio; each waits its turn. Clear by restarting
  LM Studio or waiting ~2 min for queue to drain.

- **Thinking models return empty `text` field** for simple prompts — response is in
  `reasoning_content`. The `openclaw agent --json` output `text` field is empty; check
  `reasoning_content` or use `--thinking minimal` to get brief visible responses.

- **commandTimeout must be ≥ 300s** for reasoning model agent turns.
  Set `agents.defaults.commandTimeout: 300000` in openclaw.json.

### Patterns

- **Agent fallback chain** (Mac 9B primary): lmstudio-mac → gemini-3.1-pro-preview (429) →
  gemini-3-flash-preview (succeeds). Agents do work end-to-end even when LM Studio is slow.
- **Gemini free tier rate-limits fast** under repeated tests. Space out calls or use paid tier
  for production load. `google/gemini-3-flash-preview` is the working fallback for now.
- **ollama-win stub needed** in openclaw.json to suppress setup_macos.py warning.
  Added: `providers.ollama-win.baseUrl = http://<YOUR_LAN_IP>:11434`

### Full Matrix Results

| Agent          | Node | Model         | Status  | Time   | Notes                            |
|----------------|------|---------------|---------|--------|----------------------------------|
| win-researcher | Win  | qwen3.5-27b   | ✅ PASS | 130s   | empty text; reasoning_content ok |
| coder          | Win  | qwen3.5-27b   | ✅ PASS | 107s   | empty text; reasoning_content ok |
| autoresearcher | Win  | qwen3.5-27b   | ✅ PASS | 116s   | empty text; reasoning_content ok |
| main           | Mac  | qwen3.5-9b    | ✅ PASS | 308s   | fell back to gemini-3-flash      |
| mac-researcher | Mac  | qwen3.5-9b    | ✅ PASS | 105s   | fell back to gemini-3-flash      |
| orchestrator   | Mac  | qwen3.5-9b    | ✅ PASS | ~120s  | fell back to gemini-3-flash      |

---

## [2026-04-27] Perpetua-Tools git write-hang — root cause & workaround

**Symptom:** `git status`, `git diff --stat HEAD`, `git commit`, and `git update-ref`
all hang indefinitely (timeout at 10–20s) in the Perpetua-Tools working tree.
Fast read-only commands (`git log`, `git rev-parse`, `git diff --name-only HEAD -- <specific file>`)
work fine. Only commands that scan the full worktree or acquire a ref lock hang.

**Root cause (confirmed):** Repo has two active submodules (`vendor/ecc-tools`, `vendor/agentic-stack`) whose upstream URLs require network access. Git's submodule
status check inside `git status` attempts network probes that time out on any
submodule that isn't checked out cleanly. Combined with macOS filesystem event
watching (`git fsevents` daemon), write-locking operations stall waiting for event
confirmation that never arrives.

**Verified:** `git log` (pure read, no lock) returns instantly. `git write-tree`
(index snapshot, no ref lock) returns instantly. `git commit-tree` (object creation,
no ref lock) returns instantly. `git update-ref` (acquires `.git/refs/heads/main.lock`)
hangs at 5s. `git status --no-optional-locks --ignore-submodules=all` also hangs —
confirming the fsevents daemon, not submodule scanning, is the primary blocker.

**Workaround (used successfully):**

```bash
# 1. Stage specific files directly (bypasses full worktree scan)
git add docs/LESSONS.md .claude/skills/alphaclaw-session/SKILL.md

# 2. Create tree + commit object via plumbing (no ref lock needed)
TREE=$(git write-tree)
PARENT=$(git rev-parse HEAD)
COMMIT=$(GIT_AUTHOR_NAME="cyre" GIT_AUTHOR_EMAIL="Lawrence@cyre.me" \
  GIT_COMMITTER_NAME="cyre" GIT_COMMITTER_EMAIL="Lawrence@cyre.me" \
  git commit-tree "$TREE" -p "$PARENT" -m "commit message")

# 3. Advance branch ref via direct file write (bypasses git lock mechanism)
echo "$COMMIT" > .git/refs/heads/main

# 4. Push works normally (network op, not blocked)
GIT_TERMINAL_PROMPT=0 git push origin main
```

**Permanent fix options:**

- `git config core.fsmonitor false` in PT repo (disables fsevents polling)
- `git submodule deinit --force vendor/ecc-tools vendor/agentic-stack` if submodules
  are not actively used
- VS Code "git.scanDelay" setting if using the VS Code git integration

**Status:** Direct-write workaround documented and working. Permanent fix not yet applied.
`Agent: Claude | 2026-04-27`

---

## [2026-04-27] Codex + Gemini dual code review — start.sh _print_banner()

Five bugs found and fixed across two review passes:

**Codex review (claude-code-reviewer subagent) found:**

1. `local win_ip="${WIN_IP:-?"}"` — malformed bash param expansion; `"` closed outer
   double-quote. Caused syntax error on `--status`/`--stop` paths. Fix: `"${WIN_IP:-?}"`
2. `$_` instead of `${_exit}` in discover.py fallback warning (line 203) — printed
   last shell arg, not exit code.
3. `&>/dev/null 2>&1` redundant double-redirect on all three `nc` probes.
4. `tier_color` declared but never used — commented as reserved for future ANSI.

**Gemini CLI review (v0.39.1) found:**
5. `nc` probes had no `-w` timeout flag — unreachable WIN_IP could hang startup
   for OS default (~30s). Fixed: added `-w 1` to all three probes.
6. Tier 3 label "CLOUD" was misleading — nc can't distinguish cloud-available from
   total network failure. Relabeled: "LOCAL DOWN · cloud fallback (check network)".

All fixes: `bash -n` passes. Three orama-system commits pushed: 86391c3, 128f7a6, 342edbc.
`Agent: Claude | 2026-04-27`

---

## [2026-04-27] Win Machine Hardware Spec (confirmed)

| Field | Value |
|-------|-------|
| Machine | DELL Precision Tower 3660 |
| RAM | 32 GB |
| GPU | NVIDIA RTX 3080 10GB VRAM |
| LM Studio | `<YOUR_LAN_IP>:1234` |
| CUDA constraint | ONE model at a time (RTX 3080 VRAM limit) |
| Active model | `qwen3.5-27b-claude-4.6-opus-reasoning-distilled-v2` (GGUF) |
| Secondary | `qwen3.5-9b-mlx` also loaded (but MLX won't run on CUDA; LM Studio falls back to CPU) |

**Important:** The Win 27B GGUF model responds in 107–130s per agent turn at full RTX 3080 capacity.
Do not load a second model on Win while a first is actively inferring.
`is_gpu_idle()` check is required before dispatching any new heavy Win agent task.

---

## [2026-04-27] thinkingLevel=off — Mac 9B Agents

**Problem:** Mac 9B MLX model generates large `<think>` blocks, extending agent turns to
100–308s. This is 5× slower than with thinking disabled (~15–25s expected).

**Solution (two-layer):**

1. **LM Studio UI** — toggle "Thinking Mode" off in the model settings panel.
   Must be done manually per LM Studio session; resets on restart.
2. **openclaw.json** (persistent) — set `thinkingLevel: "off"` and
   `modelParameters.budget_tokens: 0` per Mac agent:

```python
# Apply to all Mac agents in openclaw.json
import json, pathlib
cfg = json.loads(pathlib.Path.home().joinpath('.openclaw/openclaw.json').read_text())
for agent in cfg['agents']['list']:
    if agent.get('id') in ['main', 'mac-researcher', 'orchestrator']:
        agent['thinkingLevel'] = 'off'
        agent.setdefault('modelParameters', {})['budget_tokens'] = 0
pathlib.Path.home().joinpath('.openclaw/openclaw.json').write_text(
    json.dumps(cfg, indent=2, ensure_ascii=False))
```

**Status → AUTOMATED 2026-04-27.** `setup_macos.py` (step 3b) now enforces this on every
`start.sh` startup — no manual LM Studio toggle required.

**OpenClaw overwrite race (solved):** OpenClaw holds openclaw.json in memory and writes it
back on shutdown. Fix: `_restart_openclaw_if_running()` sends SIGTERM, waits for full exit,
then writes patched config — shutdown write completes first, our write wins.
Commit: `orama-system 3cba5bd`

**Win agents:** Leave thinking as-is. Win 27B always returns `reasoning_content`;
`text` field is often empty — agent reply parsers must check `reasoning_content` as fallback.
`Agent: Claude | 2026-04-27`

---

## [2026-04-27] Known AlphaClaw + OpenClaw working versions

- **AlphaClaw**: all versions 0.9.3 through **0.9.11** are confirmed working
- **OpenClaw**: all versions working (tested against AlphaClaw 0.9.3–0.9.11)
- `KNOWN_ALPHACLAW_VERSION` in setup_macos.py is set to `0.9.3` (minimum confirmed baseline)
  — patches are re-verified on version mismatch, so bumping this string is safe when a new
  version is confirmed working
`Agent: Claude | 2026-04-27`

---

## [2026-04-29] Win IP is dynamic — detect, never hardcode

**Problem:** Win LM Studio IP was hardcoded as `<YOUR_LAN_IP>` in SKILL.md and
referenced in openclaw.json. After a DHCP reassignment Win moved to `.105`, breaking
all Win agent dispatches.

**Root cause:** Two separate issues mixed into one symptom:

1. IP hardcoded in docs/skills instead of reading from openclaw.json
2. `discover.py` used `--force` flag for "always probe" — unintuitive for automation

**Fixes (automated, no manual steps required going forward):**

1. **discover.py default reversed:** Always probes on every call (no TTL skip by default).
   `--cached` flag is the new opt-in to use TTL-cached state. `--force` kept as no-op alias.

   ```bash
   python3 ~/.openclaw/scripts/discover.py          # always scans — finds new IP
   python3 ~/.openclaw/scripts/discover.py --cached # skip if < 5 min old
   ```

2. **SKILL.md updated:** Win IP row now reads "dynamic (auto-detected)" — no IP literal.
   Lookup pattern:

   ```python
   import json, pathlib
   cfg = json.loads(pathlib.Path.home().joinpath('.openclaw/openclaw.json').read_text())
   win_ip = cfg['models']['providers']['lmstudio-win']['baseUrl'].split('//')[1].split(':')[0]
   ```

3. **thinkingDefault fix:** OpenClaw schema rejected `thinkingLevel`/`modelParameters`.
   Correct field is `thinkingDefault: "off"` (enum, schema-valid). setup_macos.py step 3b
   now writes `thinkingDefault` and strips stale `thinkingLevel`/`modelParameters` on startup.

4. **gateway.js PATH fix (Patch G in setup_macos.py):** AlphaClaw spawned `openclaw gateway`
   with system PATH → Node v14 → "Node.js v22.12+ required" crash on every gateway start.
   Fix: `gatewayEnv()` prepends `path.dirname(process.execPath)` so child inherits Node v24.
   Applied idempotently by `step_patch_gateway()` on every `start.sh` run.

**Current state:** Win at `.105`, gateway live (`{"ok":true,"status":"live"}`), all 6 agents reachable.
`Agent: Claude | 2026-04-29`

---

## [2026-04-29] Git status hang — root cause was tracked node_modules (3818 files)

**Symptom:** `git status`, `git commit`, `git update-ref` hang indefinitely in PT.
For weeks we worked around it with git plumbing (`write-tree` → `commit-tree` →
direct `.git/refs/heads/main` write). This was treating the symptom, not the cause.

**Investigation (replicable diagnostic recipe):**

```bash
# 1. Check obvious culprits (all came back clean for PT)
git config --local --list | grep -E "fsmonitor|untracked|gpgsign"
ls -la .git/index.lock           # stale lock?
ls -la .git/hooks/               # hung pre-commit hooks?
pgrep -fl fsmonitor              # daemon?

# 2. Trace where git status is getting stuck
GIT_TRACE=1 GIT_TRACE_PERFORMANCE=1 timeout 6 git status 2>&1
# → trace ended at "preload-index.c:172 performance: …  preload index"
#   git was hanging in the SERIAL refresh phase that runs after preload

# 3. Confirm refresh is the hang
time timeout 5 git update-index --refresh   # → 30s timeout, never completes
time git ls-files                            # → 38ms (no stat)
time git write-tree                          # → 37ms (no stat)
# → smoking gun: lstat-each-tracked-file is what hangs

# 4. Bisect to find the bad path
for d in */; do
  start=$(date +%s)
  timeout 3 git status -uno -- "$d" >/dev/null 2>&1; rc=$?
  echo "$d: $(($(date +%s) - start))s exit=$rc"
done
# → packages/ exit=124 (hung), every other dir exit=0

# 5. Check tracked file count + symlinks
git ls-files | wc -l                         # → 3980
git ls-files | grep node_modules | wc -l     # → 3818 (96% of all tracked!)
git ls-files --stage | awk '$1=="120000"'    # → 6 tracked symlinks in node_modules
```

**Root cause:** `packages/alphaclaw-mcp/node_modules/` (3818 files including
6 cross-package symlinks) was committed by accident. Every `git status` had to
`lstat` all 3818 files. With APFS + macOS attribute lookups + symlink chains,
this exceeded any reasonable timeout.

**Fix (non-destructive, both repos preserved):**

```bash
# Add to .gitignore
echo "node_modules/" >> .gitignore
echo "**/node_modules/" >> .gitignore

# Untrack from index — --cached keeps files on disk
git rm -r --cached packages/alphaclaw-mcp/node_modules

# Commit normally (now ~140 files instead of 3980, status returns in <50ms)
git add .gitignore && git commit -m "chore: untrack node_modules (caused git status hang)"
```

**Universal rule (for the skill):** **`node_modules/` is never tracked.** Same
for `__pycache__/`, `.venv/`, `dist/`, `build/`, `target/`, `*.pyc` — anything
auto-generated by a package manager or compiler. The lockfile (`package-lock.json`,
`pnpm-lock.yaml`, `poetry.lock`, `Cargo.lock`) is the source of truth — that's
what gets committed. `npm install` (or equivalent) reproduces `node_modules/`
exactly from the lockfile.

**Why this matters beyond performance:**

1. `node_modules/` binaries are platform-specific (`darwin-arm64` won't run on Linux CI)
2. Inflates clone size (often 100MB+ per workspace)
3. Pollutes diffs (any `npm install` produces thousands of file changes)
4. Breaks `git status`/`git commit` performance once it crosses ~3k files on macOS

**For agents debugging future "git hangs":** the diagnostic recipe above takes
~2 minutes and reliably identifies the root cause. Start there before reaching
for plumbing workarounds. The plumbing workaround we used for weeks (write-tree

- commit-tree + direct ref write) was the wrong layer to fix at — the index
itself was healthy; the working tree was the problem.

`Agent: Claude | 2026-04-29`

## [2026-04-29] Module Rename → Test Drift Pattern

**Problem**: File renames (ultrathink_bridge.py → orama_bridge.py, ultrathink_mcp_client.py → orama_mcp_client.py) caused 16 test failures because:

1. Internal import in orama_bridge.py still referenced old module path
2. `patch()` strings in tests referenced old module paths
3. Routing config env vars changed (ULTRATHINK_ENDPOINT → ORAMA_ENDPOINT, ultrathink_available → orama_available) but test assertions were not updated
4. Hardware affinity tests relied on live policy file content, which was intentionally emptied

**Fix pattern**:

- After any file rename: `grep -rn "old_module_name" tests/` immediately
- Hardware policy tests: always pass explicit `policy={}` dict — never couple test logic to live YAML
- Routing contract tests: env var names come from `routing.yml`; update tests when routing.yml changes

**Guard**: Pre-commit hook at `.claude/hooks/pre-commit` enforces 5 naming-drift checks on every `git commit`.

**Runbook note (P2 badge restore):** This repo does **not** contain `scripts/discover.py`; use `python3 ~/.openclaw/scripts/discover.py --status` until a canonical in-repo wrapper is added in a future session.
To install on a fresh clone: `cp .claude/hooks/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit`

---

## Session 2026-05-08 — Startup Intelligence Engine (v0.9.9.8 → 0.9.9.9)

**Problem:** Startup probes were single-shot, scenarios were inferred via ad-hoc `if/else`, and a `WINDOWS_IP` line in `.env.local` could silently override a corrected `.env` value.

**Fixes shipped (4 commits, 38/38 tests green):**

1. `orchestrator/startup_intelligence.py` — pure-stdlib scenario engine (zero I/O):
   - `StartupScenario` enum: `FULL_DISTRIBUTED`, `MAC_DUAL`, `MAC_OLLAMA_ONLY`, `MAC_LMS_ONLY`, `CLOUD_ONLY`, `FULLY_OFFLINE`
   - `FallbackChain` dataclass + `SCENARIO_TABLE` mapping
   - `classify_scenario(mac_ok, mac_lms_ok, win_ok, lms_ok, cloud_ok)` — 6 priority rules
   - `build_routing_hints(history)` — P50 over last 5 runs → adaptive timeout (6s if Win LMS p50 > 2000ms, else 3s)
2. `agent_launcher.py`:
   - Probes return `tuple[bool, int | None]` (reachable, latency_ms); 1 retry with 2s sleep
   - Records each run to `.state/startup_history.jsonl` (rolling 10)
   - Cloud fallback: when `coder_backend == "mac-degraded"` and `PERPLEXITY_API_KEY` (preferred) or `ANTHROPIC_API_KEY` is present → routes to cloud, skips affinity check
   - `_persist_detected_ips()` patches **both** `.env` and `.env.local`
   - `scenario_name` surfaces in routing state dict
3. `tests/test_startup_intelligence.py` — 20 offline tests
4. `hardware/startup-intelligence/SKILL.md` — full agent skill doc (scenarios, retry, history, fallback, diagnostics, extension checklist)

**Win-without-Mac is intentionally `FULLY_OFFLINE`** — Mac is the manager tier; Windows is coder-only.

**Gemini CLI syntax update:** all production gemini invocations must use `--yolo` (alias `-y`). Without it, the subprocess hangs on the first sandbox/tool prompt. Updated `spawn_agents.py` + docs.

**Deferred** (needs both Mac + Win on LAN):

- `test_full_distributed_scenario_e2e` — actual probe both backends
- `test_routing_hints_with_real_p50` — needs ≥2 real Windows runs

Re-run when both nodes are up:

```bash
python3 -m pytest tests/ -k "distributed or real_p50" -v
```

---

## 2026-05-08 — V1 OrchestrationSupervisor shipped (file-based, no DB)

**Context:** Synthesised three reference files (`v1/B2-ai-cli-mcp.md`, `v1/003-Gemini-Hardware.md.md`, `v2/5-Anthropic-agent-design.md`) and adapted them for V1 repos under the no-DB/no-SQLite constraint.

**New files shipped:**

- `orchestrator/supervisor.py` — `OrchestrationSupervisor` + `JobSpec` + `JobStatus` (jsonl-only, no SQLite)
- `orchestrator/worker_registry.py` — static `WORKER_REGISTRY`; all workers use `POST /api/chat` or `POST /v1/chat/completions`, never `ollama run`
- `utils/action_validator.py` — two-phase validate-then-execute gate (IRREVERSIBLE + REQUIRES_HITL)
- `scripts/mac_probe.sh` — zero-dependency hardware detection; emits `{model_id, ram_gb, gpu_cores, private_ip, ai_tier, ollama_recommended_parallel}`
- `tests/test_supervisor_smoke.py` — 13 Mac-only smoke tests; **192/192 suite green**
- `tests/test_supervisor_lan.py` — LAN integration tests (auto-skipped until both nodes live)

**FastAPI surface added (`orchestrator/fastapi_app.py`):**

- `POST /v1/jobs` — submit job
- `GET /v1/jobs` — list jobs
- `GET /v1/jobs/{id}` — get status
- `POST /v1/jobs/{id}/cancel` — cancel
- `POST /v1/jobs/{id}/replay` — replay

**Anthropic pattern constants:**

- `MAX_DEPTH = 1` — workers cannot spawn sub-workers (hard limit)
- `MAX_THREADS = 25` — Anthropic spec ceiling
- Write final checkpoint BEFORE propagating `CancelledError` (not after)

**Model instantiation rules confirmed:**

- All workers use `POST /api/chat` (Ollama) or `POST /v1/chat/completions` (LM Studio/OpenAI)
- Never use `ollama run` in a shared shell
- Mac Ollama (localhost:11434) + Windows LM Studio (remote IP:1234) = safest simultaneous LAN pair
- 1 instance per model per physical device

**mac_probe.sh output (this Mac, 2026-05-08):**

```json
{"model_id":"Mac14,9","ram_gb":16,"gpu_cores":16,"private_ip":"<YOUR_LAN_IP>","arch":"arm64","is_apple_silicon":true,"ai_tier":"standard","ollama_recommended_parallel":2}
```

**V2 spec:** `orama-system/docs/v2/14-supervisor-and-anthropic-patterns.md` — DB persistence, audit log, MAESTRO gates, SWARM guardrails (planning only).

**Deferred (LAN):**

- `test_supervisor_lan.py::test_winonly_model_routes_to_win` — Win node required
- `test_supervisor_lan.py::test_failclosed_when_win_offline` — Win node required
- `start.ps1` end-to-end on a real Windows box

---

## 2026-05-08 — mac_probe.sh Linux/cross-platform rewrite

**Context:** `mac_probe.sh` used three macOS-only tools (`sysctl`, `system_profiler`, `ipconfig getifaddr`) and would silently produce zeroed-out JSON on Linux CI runners, Docker containers, and any future Linux node. The script name was also misleading — it probes hardware primitives generically, not macOS specifically.

### What broke

| Tool | macOS | Linux |
|------|-------|-------|
| `sysctl -n hw.memsize` | ✓ unified memory in bytes | ✗ — `sysctl` exists but `hw.memsize` key absent; returns empty string → `$(( / 1024...))` division error |
| `sysctl -n hw.model` | ✓ `Mac14,9` etc. | ✗ — key not present on Linux |
| `system_profiler SPDisplaysDataType` | ✓ Apple Silicon GPU cores | ✗ — binary not installed |
| `ipconfig getifaddr en0` | ✓ primary LAN IP | ✗ — `ipconfig` is a Windows command on Linux (wrong binary); `en0` doesn't exist |

Silent failure mode: `RAM_GB=0`, `GPU_CORES=` (empty string), `PRIVATE_IP=0.0.0.0`, `AI_TIER=base`, `OLLAMA_PARALLEL=1` — supervisor would under-provision every Linux node.

### Fixes shipped (commit e670525 on main)

Full rewrite with platform detection at the top (`_OS="$(uname -s)"`):

**RAM:**

```bash
# macOS (unchanged)
RAM_BYTES=$(sysctl -n hw.memsize 2>/dev/null || echo "0")
# Linux
RAM_KB=$(grep '^MemTotal:' /proc/meminfo | awk '{print $2}')
RAM_GB=$(( RAM_KB / 1024 / 1024 ))
```

**Model ID:**

```bash
# macOS
MODEL_ID=$(sysctl -n hw.model)          # "Mac14,9"
# Linux — DMI
MODEL_ID=$(cat /sys/devices/virtual/dmi/id/product_name)  # "ThinkPad X1" etc.
# Linux — ARM SBC (Raspberry Pi, Jetson)
MODEL_ID=$(tr -d '\0' < /proc/device-tree/model)          # "Raspberry Pi 4 Model B"
```

**GPU:**

```bash
# macOS — Apple Silicon GPU core count via system_profiler (unchanged)
# Linux NVIDIA
SM_COUNT=$(nvidia-smi --query-gpu=multiprocessor_count --format=csv,noheader,nounits)
# Linux generic (count GPU devices; rough approximation)
GPU_COUNT=$(lspci | grep -ciE 'VGA|3D|Display')
```

**Private IP:**

```bash
# macOS — interface-based (unchanged)
ipconfig getifaddr en0 || ipconfig getifaddr en1
# Linux — routing-table-based (correct interface auto-selected)
ip route get 8.8.8.8 | awk '/src/{for(i=1;i<=NF;i++) if($i=="src") {print $(i+1); exit}}'
# Linux fallback
hostname -I | awk '{print $1}'
```

**New output field:** `"os": "Darwin"|"Linux"` — backwards-compatible addition.

### Validation on this Mac (2026-05-08)

```json
{
  "model_id": "Mac14,9",
  "ram_gb": 16,
  "gpu_cores": 16,
  "private_ip": "<YOUR_LAN_IP>",
  "arch": "arm64",
  "os": "Darwin",
  "is_apple_silicon": true,
  "ai_tier": "standard",
  "ollama_recommended_parallel": 2
}
```

All fields identical to V1 output except new `"os"` key — supervisor `detect_hardware()` is unaffected.

### Key rules derived

- **Always guard `sysctl` keys** — `sysctl -n hw.memsize` on Linux returns nothing, not an error exit; `|| echo "0"` is mandatory or arithmetic will blow up with `integer expression expected`.
- **`/proc/meminfo` MemTotal is in kB, not bytes** — divide by `1024 * 1024` (not `1024^3`) to get GB.
- **`ip route get 8.8.8.8`** is the canonical Linux way to find which interface the machine uses to reach the outside world — it correctly handles multi-homed hosts and avoids guessing interface names (`eth0`, `ens3`, `enp0s3` all work automatically).
- **`ipconfig` on Linux is a different binary** — it shows DHCP client info (from `isc-dhcp-client`), not interface IPs. Never use `ipconfig getifaddr` on Linux.
- **`system_profiler` is macOS-only** — on Linux use `nvidia-smi` for NVIDIA or `lspci` for generic GPU detection. For Apple Silicon on macOS, `system_profiler SPDisplaysDataType` remains the only reliable source of Neural Engine / GPU core count.
- **`/dev/tcp` bash built-in** — available in bash 3.2+ without any external tool. Standard `/dev/tcp/host/port` open succeeds on connection, fails with exit code 1 on refusal. Use as the `nc` fallback everywhere.

### Deferred

- Validate on Ubuntu 22.04 LTS (GitHub Actions runner — expected to work with `/proc/meminfo` + `ip`)
- Validate on Alpine 3.19 (no `lspci`, no `DMI` in `/sys` — `GPU_CORES` will be 0; acceptable)
- Validate on Raspberry Pi 4 (`/proc/device-tree/model` path)
- `nvidia-smi` output format test on a real CUDA box

---

## 2026-05-20 — CI: `respx` missing from workflow pip install

### Problem

GitHub Actions CI (`lint-and-test` matrix, both 3.11 and 3.12) failed at test collection with:

```
ModuleNotFoundError: No module named 'respx'
ERROR tests/discovery/test_probe.py
ERROR tests/discovery/test_registry.py
```

### Cause

`respx` is declared as a runtime dependency in `pyproject.toml` (line 114: `"respx>=0.23.1"`) and is used by `tests/discovery/` for mocking `httpx` calls via `@respx.mock`. However, the CI workflow installs dependencies with explicit `pip install` lines rather than `pip install -e ".[dev]"` — so `pyproject.toml` is never read by CI, and `respx` is never installed.

The `[project.optional-dependencies].dev` section in `pyproject.toml` also does not list `respx`, which is a secondary inconsistency (it should be there too for anyone doing `pip install -e ".[dev]"`).

### Fix

Added `pip install respx` to `.github/workflows/ci.yml` Install dependencies step, after the `slowapi` line. One-line change.

### Key rule derived

- **CI workflow installs are independent of `pyproject.toml`** — adding a dep to `pyproject.toml` (even under `dependencies`, not `[dev]`) does NOT make it available in CI unless the workflow explicitly installs it or uses `pip install -e "."`. Any new test dependency that isn't in `requirements.txt` must also be added to the `pip install` block in `ci.yml`.
- **Check `[project.optional-dependencies].dev`** — test-only deps like `respx`, `pytest-asyncio`, `pytest-cov` should live there so `pip install -e ".[dev]"` gives a working local environment. `respx` is missing from that section; fix in a follow-up.

## 2026-05-27 — PR #50: GossipBus emit was a silent no-op + gbrain venv gap

### Bug discovered (PR #50)
`GossipBus.emit()` was NEVER called in production despite RAG items 5–7
shipping in PR #49. `_inject_memory_context()` ran (reading from gossip_db
path on stdin), but `_record_to_gossip()` used a bare `import + emit` pattern
that silently failed on every job because `GossipBus` was instantiated fresh
each call with no schema init — and then discarded without ever calling `emit`.

**Fix pattern (PR #50, commit c1ae82e):**
- `self._gossip_bus = None` lazy cached on `Supervisor.__init__`
- `self._gossip_warned = False` rate-limits log spam
- `_record_to_gossip()` lazy-inits bus, calls `ensure_gossip_db_ready()`, then `emit()`
- First gossip failure: `log.warning(...)` (ops sees broken recall). Subsequent: `log.debug(...)`.

### Python venv gap
Running `pytest` in a git worktree without activating the canonical `.venv`
falls back to system Python 3.9.6 (macOS). `aiosqlite` isn't installed there
→ `ModuleNotFoundError` on 2 of 46 tests.

**Fix:** Always `source .venv/bin/activate` from
`perplexity-api/Perpetua-Tools/` before running tests in any PT worktree.
The `.venv` uses Python 3.12.13 (miniconda3) and has all deps. CI uses 3.11
and 3.12 — both pass fine. System Python (3.9, EOL Oct 2025) should never
be the test runner for this repo.

**Rule:** If tests fail with `ModuleNotFoundError: No module named 'aiosqlite'`
the cause is almost certainly the wrong Python. Check: `python3 --version`
should show 3.11+; if not, activate `.venv` first.

### gbrain sync has 29-skipped-file gap in PT source
`gbrain sync --skip-failed` advanced checkpoint to `f60a7173` but left 29
Python files (including `orchestrator/gbrain_search.py`) unindexed as code
symbols. Caused by PgBouncer transaction-mode prepared-statement errors.

**Fix:** `gbrain sync --force --source gstack-code-ools-27e2b79c-df8a28`
(run once, ~10 min). Kicked off 2026-05-27.

### LESSONS.md not in gbrain isolated source
`orama-src` isolated source indexes only `docs/v2/*`, `bin/orama-system/*`,
`docs/superpowers/*` — not the 2,400-line `docs/LESSONS.md`.

**Fix:** `gbrain put "orama-system/lessons" < docs/LESSONS.md` (idempotent,
run once per major update). Now makes `gbrain search "HITL"` work cross-session.

## [2026-05-28] Stop source-archaeology when hardware topology changes

**Anti-pattern discovered:** 30+ tool calls tracing `lan_discovery.py` ancestry to find why CI returned `<YOUR_LAN_IP>` instead of `.103`, checking git logs, commit diffs, installed packages, and shadow modules — all because tests were written against a hardcoded `.103` fallback that was already wrong.

**Root cause (trivially obvious in hindsight):** The Windows GPU machine IP changed from `.103` → `.108`. Cursor had already created PRs #58/#59/#60 fixing this. The old CodeRabbit-added tests were stale.

**Rule:** When a test fails with an unexpected IP/hostname, **check hardware topology first** (`discover.py` or the memory file `project_lan_topology.md`) before any code archaeology. Cost: 1 tool call. Saves 30+.

**Pattern:** `assert result == "http://<YOUR_LAN_IP>"` FAILING with `http://<YOUR_LAN_IP>` → the hardware changed, not the code.

**Corollary:** When Cursor/CodeRabbit have created new branches since your last session, `git fetch --all` and READ THOSE BRANCHES before diagnosing anything. They likely already fixed it.

---

## 2026-05-31 — Claude (Opus 4.8) — Tri-repo migration audit, dedup, alignment plan

> **Doc trio (use together):**
> - **Execution + decisions:** [`docs/2026-05-31-tri-repo-alignment-completion-plan.md`](2026-05-31-tri-repo-alignment-completion-plan.md) — canonical combined plan [`a261d70`](https://github.com/diazMelgarejo/Perpetua-Tools/commit/a261d70e41e1825353654b7f3d9703270a33fa00)
> - **Gate ladder:** [`docs/MIGRATION.md`](MIGRATION.md) — milestone checklists; cross-links completion plan
> - **Session log:** this file

### What was done
- **Migration audit (3 parallel code-explorers):** mapped every AlphaClaw feature capability → PT counterpart. Verdict: overarching goal (PT controls all AlphaClaw+OpenClaw) is **Gate-2 partial**, **8 gaps** open. `lib/mcp`(11 JS tools)+`lib/agents` are **superseded** by `packages/alphaclaw-mcp`(14)+`packages/local-agents`, but retirement is **held until Gate 2 green**.
- **Master plan** → [`docs/2026-05-31-tri-repo-alignment-completion-plan.md`](2026-05-31-tri-repo-alignment-completion-plan.md). **Read it first next session.** Combined A+B variant on `main` at [`a261d70`](https://github.com/diazMelgarejo/Perpetua-Tools/commit/a261d70e41e1825353654b7f3d9703270a33fa00).
- **orchestrator.py LM Studio bug fixed** (`bd6aeda`): `/api/v1/chat` (nonexistent) → `/v1/chat/completions`.
- **PR #2** merged `-s ours` (records 2026-04-22 salvage, zero regression); **PR #3** retargeted main→feature + merged (ECC bundle, model bumped `gpt-5.4`→`gpt-5.5`).

### Key learnings
- **gbrain broke on `prepare:true` against the Supabase pooler.** Fix: `prepare:false` in `~/.gbrain/.env` (source it for CLI). CRG registry empty (build per repo).
- **macOS dup `* 2` and `* 3` files: NOT OneDrive/iCloud** (both audited + cleared). Historical Finder/IDE keep-both, dormant (newest May 28). 31 identical deleted, 209 files/23 dirs quarantined → `~/dup-quarantine-2026-05-31` (all unique content was stale).
- **Subagent Bash is sandboxed** (git/npm/node denied) — run live-server/build/git in the MAIN session.
- **Two “agent” registries:** OpenClaw `agents.list` in `openclaw.json` (PT `alphaclaw_bootstrap`) ≠ orama `bin/config/agent_registry.json` (ultrathink stages). See completion plan § Config & agent creation (**D2**).

### Resolved decisions (2026-05-31, code-verified — details in completion plan)

| ID | Choice |
|----|--------|
| **D1** | Gate 4 → `0.9.9.9`; MCP → `0.9.16.9` |
| **D2** | Bootstrap + orama `apply_runtime_payload`; gap: `reconcile_gateway` lacks `openclaw_config` |
| **D3** | AlphaClaw `feature/MacOS-post-install` @ `b540eca1`; `lib/mcp` present on remote |
| **D4** | `SETUP_PASSWORD` order env → `ALPHACLAW_ROOT/.env` → `~/.alphaclaw/.env` → ask; fail-closed **no** |
| **D5** | `orchestrator.py` CLI + `fastapi_app` supervisor HTTP |

### Still open (implementation, not policy)
- Live smoke (#1), `lib/mcp` retirement (#2), Gate 3 bridge (#3), version file alignment (Gate 4).

### Gate 2 code landed on `main` (2026-05-31)
- **#7** `reconcile_gateway()` → `openclaw_config` + `role_routing` via `alphaclaw_bootstrap --json`
- **#4** `packages/alphaclaw-adapter` `stopServer()` + PID file
- **#6** `mcp-stdio.mjs`, canonical `mcpb-agents` paths, Vitest in `local-agents`
- **Track B+C:** `vendor/Claude-Desktop-LLM` submodule + real MCPB (`install.sh`, `scripts/install-claude-desktop-llm.sh`); JSON knockoffs removed — see [`plans/2026-05-31-track-bc-claude-desktop-mcpb.md`](plans/2026-05-31-track-bc-claude-desktop-mcpb.md)
- Plan: [`docs/plans/2026-05-31-gate2-implementation-plan.md`](plans/2026-05-31-gate2-implementation-plan.md)

**Cross-repo:** [orama LESSONS](../../orama-system/docs/LESSONS.md) · [AlphaClaw Lessons](../../AlphaClaw/docs/Lessons.MD)

---

## 2026-06-05 — PT `main` was rewritten; branch salvage map + the FM7 repeat

**Context.** While re-anchoring branches across the stack, an agent (me) hand-rolled a
`git rev-list --count` / `merge-base` ahead-behind table on PT and concluded "no orphans,
nothing to do." The tell that broke it: a branch showed `479 behind` yet its tip was
**byte-identical** to a commit in `main`. That is impossible unless `main` was **rewritten** —
which it was. Ahead/behind and merge-base are SHA-graph proxies and are **meaningless across
a rewrite boundary**. The correct test is the **tree-twin** (`%T` match), per the orama
[git-reanchor SKILL.md](https://github.com/diazMelgarejo/orama-system/blob/main/bin/orama-system/skills/git-reanchor/SKILL.md) § 5.

**Mandatory method for PT branch work** (canonical tool now in-repo):
```bash
scripts/git/reanchor_scan.sh . origin/main heads     # tree-twin scan of LOCAL branches
git cherry -v origin/main <tip> <base>               # + = missing from main, - = already in
```
Never substitute `rev-list --count` / `merge-base` for orphan or divergence judgment here.
Why this must be enforced at point-of-use, not memorized: see orama
[LESSONS § 2026-06-05](../../orama-system/docs/LESSONS.md) · [GitHub](https://github.com/diazMelgarejo/orama-system/blob/main/docs/LESSONS.md#2026-06-05).

**Branch salvage map (tree-twin + `git cherry`, 2026-06-05).** Local branches across the
PT clones, after the rewrite:

| Group | Branches | Action |
|-------|----------|--------|
| **Already in main** (tip tree-twin present, `cherry` all `-`) | `2026-04-25-perpetua-recovery`, `2026-06-01-073-fix-test-portability`, `tmp-pr42-test`, `wt-pr42`, `2026-05-27-009-fix4-5-path-boundary-mcp`, `2026-05-28-004-dependabot-security-bumps`, `cursor/critical-bug-investigation-0df5`, `feat/ip-aware-discovery`, `fix/pt71-clean` | none — work landed; delete local or re-anchor ref to twin |
| **Missing work to salvage** (`cherry` has `+`) | **`fix/pt71-review-v2`** (9: `alphaclaw_manager` bootstrap-JSON progress-prefix parse, `startServer` pidFile ReferenceError fix + regression tests, `install.sh` exec-bit, remaining PT#71 review fixes) · **`fix/ci-69`** (MCPB `Claude-Desktop-LLM` submodule + fail-fast Ollama probe) · **`fix/ci-71`** (pidFile fix + progress-prefix parse) · **`fix/pt71-onto-main`** (subset of review-v2) · **`temp-recovery`** (3-tier priority IP detection) · **`recover/2026-05-31-codex-plan-revision`** (user-input-queue test isolation) | re-anchor onto twin (git-reanchor § 4), then open a reviewed PR for the `+` commits |

`fix/pt71-review-v2` is the richest "missing link" — the finished PT#71 review work that
never merged. **Reviving any remote branch requires explicit user authorization** per
[`AGENTS.md`](../AGENTS.md) § Security PR stacking; not done unattended.

> **AUDIT RESULT (2026-06-05, RESOLVED — no salvage PR needed).** Both a tree-twin graft and a
> surgical 9-commit cherry-pick **conflicted from the first commit**. A 3-way diff-audit (each
> commit's file vs its parent vs current `main`) showed **the work is already in main**, often
> extended: `orchestrator/alphaclaw_manager.py` progress-prefix parse (`07cd00e`) = **0 diff**;
> `install.sh` (`b2b7638`,`1d72630`) = **0 diff**; `tests/test_alphaclaw_manager.py` (`f4ab810`)
> = **0 diff**; `packages/alphaclaw-adapter/src/index.js` pidFile fix (`061c0ee`) is present in
> main **and superseded** by the fuller `startServer({port,alphaclawRoot,logFile,pidFile})`
> signature + Gate-2 `configure({port})` lifecycle. The branch was merged-by-reimplementation
> post-rewrite. **Lesson: across a rewrite, `git cherry +` means "no identical patch-id", NOT
> "content missing" — always confirm with a 3-way file diff before spending salvage effort.**
> Backup tag `backup/salvage-pt71-review-*` retained; local branch fix/pt71-review-v2 kept for
> reference. Same audit applies to the other "missing-work" branches (fix/ci-69 MCPB, temp-recovery
> IP-detection, recover/codex-plan queue-test): diff-audit before assuming a PR is needed.
>
> **Harmonization check (CIDF, additive principle).** Before closing, verified the branch holds
> no additive content main lacks: `stop-server.test.cjs` = **14 test cases vs main's 31**
> (0 unique-to-branch); `tests/test_alphaclaw_manager.py` = **24 vs 24** (0 unique-to-branch).
> Main is a strict **superset**. So "combine/merge/harmonize" yields nothing to merge — closing
> is CIDF-correct (verified-subsumed), not a wholesale discard. The orama rule held: we checked
> for additive bits to harmonize *before* concluding done, rather than assuming.

**Cross-repo:** [orama LESSONS](../../orama-system/docs/LESSONS.md) · [AlphaClaw Lessons](../../AlphaClaw/docs/Lessons.MD) · tool [`scripts/git/reanchor_scan.sh`](../scripts/git/reanchor_scan.sh). periscope excluded (its `main`/`agentsview` are pure upstream mirrors, never rewritten by us).

### 2026-06-05 (cont.) — attribution-guard fragmentation, unified to a single source

Pushing the docs above tripped PT's `pre-push` (`.githooks/pre-push` → `audit_attribution.sh`
with `GIT_AUDIT_STRICT=1`): strict mode audits the **full reachable history**, and PT's guard
copies still flagged 79 mainstream-AI bot co-authors + 7 AI authors that **orama's allowlist
already permits** (orama PR #71). Root cause: PT's `audit_attribution.sh`,
`check_commit_message.sh`, `check_identity.sh` were **stale forks** of orama's canonical guards.

Fixes (now reflected in [`CLAUDE.md` §6](../CLAUDE.md) + [`AGENTS.md`](../AGENTS.md)):
- The orama sync tool `sync-attribution-guard-scripts.sh` **omitted `check_commit_message.sh`
  and `check_identity.sh`** from its copy list → permanent drift. Added them.
- Re-synced → all guard scripts **byte-identical orama↔PT** (`bad_author` 7→0,
  `bad_coauthor` 79→3; push range clean=yes).
- The sync wrote a *thin wrapper* for `daily-attribution-guard.sh` that, on PT itself, **execs
  itself (infinite recursion)**. Backported orama's now-canonical **self-contained full impl**
  (`REPO_ROOT`-derived) to all repos and dropped the wrapper special-case entirely.
- **Rule:** never hand-edit a guard in a downstream repo. Edit orama's canonical copy, then
  `bash ../orama-system/scripts/git/sync-attribution-guard-scripts.sh .`.

**Cross-repo:** mirrored in orama [`docs/LESSONS.md` § 2026-06-05 (cont.)](../../orama-system/docs/LESSONS.md) · [GitHub](https://github.com/diazMelgarejo/orama-system/blob/main/docs/LESSONS.md). Org-wide zero-fragmentation governance plan: orama [`docs/v2/`](../../orama-system/docs/v2/).

## 2026-06-06 — opus-4-8 migration + concurrent-agent collision (caught a 404 regression)

During the `/claude-api migrate` task, a **parallel agent** (same approved identity
`cyre <Lawrence@cyre.me>`) ran the *same* migration and pushed to PT `main` concurrently.
What it got wrong, caught before harm:

- **Malformed model IDs that would 404 at runtime** — `claude-4-6-sonnet-thinking`,
  `claude-4-6-sonnet`, `claude-4-5-haiku` (in `orchestrator.py:call_perplexity` default +
  `tests/test_alphaclaw_manager.py`). The correct order is `claude-<family>-<major>-<minor>`:
  **`claude-sonnet-4-6`** / **`claude-haiku-4-5`**; `thinking` is a request param, never part
  of the ID. Fixed forward (kept the sonnet/haiku choice, corrected the strings) — commit
  `32f770c`. **Always validate every model-ID string against the real catalog — these
  plausible-looking typos only fail when the API call actually fires.**
- **Stray upstream tracking + racing dependabot push** — local `main` was tracking a dated
  branch another agent created, so a bare `git push` falsely reported "up-to-date"; a
  dependabot starlette bump (#107) landed on `origin/main` mid-push. Fix: explicit
  `git push origin HEAD:main`, rebase onto the dep commit (no overlap), then **return the
  shared checkout to `main`** so the next agent doesn't inherit a stray HEAD.

**Rule (shared checkout):** before commit/push, run `git rev-parse --abbrev-ref HEAD` +
`@{u}` — a fellow agent may have moved HEAD onto their branch. Land via explicit `HEAD:main`.

**No destructive damage this session:** audited recent commits on both repos — all additive,
approved identity, zero banned attribution, no force-push dropped any prior commit. The
concurrent agent's other pushes (sed-portability hook fix, cursor-identity test update,
posterity lesson) are benign. Guard-parity gate (`scripts/git/verify-guard-parity.sh`,
synced from orama) verifies byte-identical guards across repos — currently PASS.

**Cross-repo:** orama [`docs/LESSONS.md` § 2026-06-06 (cont.)](../../orama-system/docs/LESSONS.md) ·
[GitHub](https://github.com/diazMelgarejo/orama-system/blob/main/docs/LESSONS.md). **Priorities
next:** (P1) repair gbrain (`broken-config` → `/setup-gbrain`); (P2) resume tri-repo Gate 2→3
(canonical plan: [`docs/2026-05-31-tri-repo-alignment-completion-plan.md`](2026-05-31-tri-repo-alignment-completion-plan.md));
(P3) wire `verify-guard-parity.sh` into CI + `daily-attribution-guard.sh`.

## 2026-06-08 — Claude patch review: P0 oramasys rename without skill fragmentation

Claude's attached recommendations were accepted only for the missing P0 contract pieces: PT now targets canonical `/oramasys`, uses `ORAMASYS_*` env keys with legacy `ULTRATHINK_*` fallbacks, and keeps legacy response keys only as a compatibility alias during the transition. The proposed extra oramasys method skill was intentionally not copied into PT/orama because the existing skill stack already carries the 5-stage method, CIDF, AFRP, CRG/gbrain frugality, and first-run references.

Decision rule: consolidate knowledge into the canonical repo docs/skills instead of maintaining a parallel Claude-generated tree. When adding `mcp/oramasys`, preserve existing MCP server setup and follow the established GitHub/LM Studio stdio config pattern; do not overwrite `.cursor/mcp.json` or split bridge ownership. P1/P2 pipeline/version-bump work remains deferred until after P0 lands.

## 2026-06-08 (cont.) — Windows Git shim must expose GitHub Desktop's HTTPS helper path

During the P0 oramasys commit/rebase flow, `git pull --rebase origin main` failed
with `git: 'remote-https' is not a git command` even though `git --exec-path`
pointed inside GitHub Desktop. Root cause: the local `%USERPROFILE%\.lmstudio\bin\git.cmd`
shim launches GitHub Desktop's `cmd\git.exe`, but it does not put the bundled
`mingw64\bin` helper directory on `PATH` or set `GIT_EXEC_PATH` to the directory
that contains `git-remote-https.exe`.

Temporary working command:
```powershell
$gitRoot = "$env:LOCALAPPDATA\GitHubDesktop\app-3.5.9-beta3\resources\app\git"
$env:PATH = "$gitRoot\mingw64\bin;$gitRoot\cmd;$env:PATH"
$env:GIT_EXEC_PATH = "$gitRoot\mingw64\bin"
& "$gitRoot\cmd\git.exe" pull --rebase origin main
```

Permanent shim rule: keep the LM Studio-style lightweight wrapper, but when it
finds a GitHub Desktop app directory, prepend both `resources\app\git\mingw64\bin`
and `resources\app\git\cmd` before invoking `cmd\git.exe`, or set
`GIT_EXEC_PATH` for that child process. Do not replace the shim with a hardcoded
single GitHub Desktop version path; keep edition/version discovery frugal.

PowerShell gotchas from the same run:
- Quote upstream shorthand as `git rev-parse --abbrev-ref '@{u}'`; bare `@{u}` is parsed as a hashtable.
- Do not use `&&` in this Windows PowerShell session; run commands separately or use PowerShell-native control flow.
- If the HTTPS helper error disappears and the next failure is `Failed to connect to github.com ... 127.0.0.1`, the Git shim is fixed enough for HTTPS and the remaining issue is network/proxy access, not Git packaging.
---

## 2026-06-12 — OpenClaw gateway :18789 won't start ("Not onboarded"): drive the openclaw CLI directly (don't guess)

**Symptom:** Gateway `:18789` down. AlphaClaw manager (`:3000`) `POST /api/gateway/restart` → `{"ok":false,"error":"Not onboarded"}` even though `~/.alphaclaw/onboarded.json` exists.

**Root cause:** That "Not onboarded" is AlphaClaw's OWN read-only onboarding-marker gate (`onboarded.json` `{"readOnly":true,"reason":"read_only_complete"}`) — SEPARATE from OpenClaw gateway readiness. It is not the gateway's blocker.

**Fix (verified live 2026-06-12; OpenClaw is a PUBLIC project — docs.openclaw.ai, github.com/openclaw/openclaw — search, don't reinvent):** bypass AlphaClaw's manager and drive the bundled `openclaw` CLI directly:
```
node <repo>/AlphaClaw/node_modules/openclaw/openclaw.mjs gateway --port 18789 --force
```
- Needs `gateway.mode=local` in `~/.openclaw/openclaw.json`. Docs: gateway refuses to start without it; a clobbered config that lost `gateway.mode` is "broken" → repair via `openclaw onboard --mode local` or `openclaw setup`. Ad-hoc/dev override: `openclaw gateway --allow-unconfigured`.
- Verify: `openclaw gateway status --deep --json` → port `busy` + listener pid on 18789.
- Durable service: `openclaw gateway install` + `openclaw gateway restart --force` (LaunchAgent `ai.openclaw.gateway`; keep service PATH minimal — doctor warns on version-manager PATHs).
- Non-interactive onboard (scripts): `openclaw onboard --non-interactive --mode local --auth-choice apiKey --anthropic-api-key "$KEY" --gateway-port 18789 --gateway-bind loopback --install-daemon --daemon-runtime node --skip-skills`.
- Port/bind precedence: `--port` → `OPENCLAW_GATEWAY_PORT` → `gateway.port` → 18789.

**Relevant OpenClaw-operation skills:** `alphaclaw-session` (commandeer/self-heal runtime — PRIMARY owner of this fix), `model-routing-check` (gateway must be live before dispatch), `self-discovery` (gateway status = live-state probe).
---

## [2026-06-12] Write-time path-hygiene guard (don't rely on memory)

- **Pattern**: enforce "no workstation/absolute paths in tracked files" at WRITE time, not only at commit/CI. PreToolUse hook `~/.claude/hooks/no-workstation-paths.py` (matcher `Write|Edit`) blocks (exit 2) when an edit injects an absolute home path or a synced-tree path into a git-tracked, non-gitignored file; allows scratch/`/tmp` and gitignored files.
- **Rule**: use repo-relative paths — `"$(git rev-parse --show-toplevel)/…"` or sibling `"../../<repo>/…"`. `repo_hygiene.py` (pre-commit + CI) remains the backstop.
- **Why**: relying on memory failed (a workstation path re-leaked into a tracked skill); a deterministic harness guard is the durable fix. Fresh-install bootstrap imperative for the guard lives in the CIDF skill.

---

## [2026-06-12] Discovery must update ALL endpoint sinks at runtime

- **Fact**: `discover.py` subnet-scans (`scan_subnet_async` over the LAN range) → auto-detects DHCP moves and updates openclaw.json/config/last_discovery. Stale cache = hadn't re-run; `--force` bypasses TTL.
- **Bug fixed**: PT `.env` is synced separately by `lan_discovery._sync_win_endpoint_env`, which only knew 4 canonical keys → `GPU_BOX`/`DELL_ENDPOINT` (same Win RTX3080 box) drifted. Extended the holder map to cover them; now every Win-box ref follows live discovery.
- **Gotcha**: set `PERPETUA_TOOLS_ROOT` after a tree move or `discover.py` skips PT hardware_policy (falls back to local filter).

---

## [2026-06-12] Codex skill installs are thin wrappers; canonical skills stay in repo

- **Decision**: local Codex installs under `~/.codex/skills` must be thin wrappers only. They should contain a Codex-valid `SKILL.md` with trigger text, canonical repo root, canonical in-repo `SKILL.md` path, and an origin-sync rule. Do not copy canonical skill bodies, references, scripts, or assets into the local install.
- **Canonical owner**: orama-system `bin/orama-system/skills/skillify/references/codex-thin-wrapper-installs.md` owns the detailed policy. Perpetua skills should cross-reference that rule instead of duplicating it.
- **Origin rule**: before using a canonical card, run `git fetch origin --prune`. Run `git pull --ff-only` only when the repo is clean and on a tracking branch. If dirty or non-fast-forward, preserve local work, report drift, and read the current canonical card with that caveat.
- **Windows encoding rule**: generated skill roots must be UTF-8 without BOM. In Windows PowerShell, set console/output encodings explicitly and use `[System.Text.UTF8Encoding]::new($false)` with `[System.IO.File]::WriteAllText(...)`. `Set-Content -Encoding utf8` can leave a BOM in Windows PowerShell 5.1; Python validators may also need `PYTHONUTF8=1`.
- **Qwen/LM Studio testing**: use compact `/no_think` JSON prompts. Large canonical excerpts can time out on `qwen3.5-27b-claude-4.6-opus-reasoning-distilled-v2`; prefer deterministic path/frontmatter audits first, then ask Qwen to review the compact name/description manifest.
- **Penultimate completion habit**: before declaring a long-running goal achieved, collect session lessons and update canonical skills/docs first, then refresh local wrappers if trigger text or canonical paths changed.

---

## [2026-06-12] PT-MCP should expose callable local LM Studio model metadata

- **Fact**: LM Studio's OpenAI-compatible `/v1/models` endpoint returns the exact loaded local model IDs that PT-MCP callers need for delegated work. On this Windows host it exposed `qwen3.5-27b-claude-4.6-opus-reasoning-distilled-v2` plus the other loaded models at `http://127.0.0.1:1234`.
- **Pattern**: keep legacy `ollama` and `lmstudio` string arrays for compatibility, but add structured `loaded` and `callable` metadata with `backend`, `baseUrl`, `chatCompletionsUrl`, `loaded`, and `callable`. New callers should select exact model IDs from `callable`; old callers should continue reading the arrays.
- **Rationale**: exact local delegation should not depend on scraping CLI output, stale config defaults, or a hosted Codex subagent model menu. PT-MCP is the repo-controlled bridge that can expose live LM Studio state deterministically.
- **Windows test lesson**: Node ESM imports on Windows must use `pathToFileURL(absPath).href` for absolute `C:\...` paths. Tests that spawn npm should prefer `process.execPath` plus `process.env.npm_execpath` when available, then fall back to `npm.cmd`; this follows LM Studio's bundled Node/npm layout without requiring a global npm shim.
- **Build lesson**: package scripts should rely on npm's PATH injection (`"build": "tsc"`) instead of hardcoding `node_modules/.bin/tsc`; the hardcoded path is not portable in Windows PowerShell. If npm is used only to install missing dependencies in a pnpm-locked package, do not commit the generated `package-lock.json`.

---

## [2026-07-04] Hermes bb70a6833f36: cross-machine learning pathway + .agent/ misfire autopsy

- **Cross-machine learning pathway**: Win AutoResearcher (`start.ps1` / Hermes) generates episodic evidence via skills (e.g. `skill-absorption-map`) → `auto_dream.py` clusters them into candidates in `.agent/memory/candidates/` → candidates persist across dream cycles until a human reviews on Mac. Win-originated candidates can sit `staged` for days (bb70a6833f36 was re-staged 47× over 12 days) because `auto_dream` runs on both machines but only a human session on either can graduate them.
- **skill-absorption-map `FAILURE` label**: a diagnostic output, NOT a system crash. It means the map found unabsorbed skill clusters. Treat as architecture TODOs: `hermes-harness` should absorb `hermes-agent` + `pt-orama-harness-integration`; `perpetua-hardware` should absorb `local-inference`. Act as refactoring targets.
- **Misfire 1 — `endpoint-policy-contract.yml` (2026-06-29, `cyre <Lawrence@cyre.me>`)**: Valid contract written to `.agent/` root instead of `.agent/protocols/`. The agent listed `AGENTS.md` in `required_local_files` — knowing the file exists is not the same as reading it for behavioral guidance. Correct move: read `.agent/AGENTS.md` BEFORE creating any file under `.agent/`.
- **Misfire 2 — `.agent/lessons.md` (2026-07-04 07:15, owner Gmail identity)**: Agent hand-wrote a markdown lessons file instead of using `python3 .agent/tools/learn.py`. Created a phantom file nothing reads, bypassing the full stage→graduate→render pipeline. Correction: the private owner identity is canonical when supplied from local-only configuration; the actual defect was stale attribution tooling and wrong memory-file procedure.
- **Anti-pattern — listing ≠ reading**: Cargo-culting a convention file's name into a checklist/plan while skipping its content is how AFRP Trigger 3 failures happen. A file that appears in your output as a reference MUST be opened and read before acting in its domain.

---

## [2026-07-01] Hermes coord-pulse hardening: race dispatch, pause/resume, memory pipeline encoding sweep

- **Fact**: `coord_pulse.ps1` (orama-system) was upgraded from single-leg Hermes dispatch to `spawn_agents.py --agent race` — races `cursor-agent` against Hermes+LM Studio Win, first success wins, falls back to direct LM Studio. Added a sticky `coord_pulse_pause.json` gate checked independent of the Task Scheduler enable state (default: stays paused until explicit resume), backed by a new user-local Hermes skill (`coord-pulse-control`) so "pause/resume coord pulse" works conversationally.
- **Bug fixed**: `Register-ScheduledTask` rejected `[TimeSpan]::MaxValue` as a `RepetitionDuration` (`P99999999DT23H59M59S` invalid XML) — fixed to `New-TimeSpan -Days 3650`.
- **Gotcha**: Hermes user-local skills resolve from `HERMES_HOME` env var (`skill_manager_tool.py::SKILLS_DIR`), not a hardcoded `~/.hermes` — a skill dropped at `~/.hermes/skills/...` silently never appeared in `hermes skills list` until moved to `$HERMES_HOME/skills/...`.
- **Gotcha**: when a branch has diverged from origin with unrelated concurrent commits, `git reset --hard origin/<branch>` + re-apply only your own deltas beat fighting an interactive rebase across duplicate/superseded history (rebase kept dropping commits as "already upstream" and hit real conflicts on files a concurrent session had independently rewritten).
- **Gotcha**: a file showing 100% line-changed in `git diff` with zero semantic difference (verified via `diff <(tr -d '\r' ...)`) is `.gitattributes` EOL false-dirty — fix once with `git add <file>` to renormalize the blob, never `git checkout --` (which can silently discard real changes if the diagnosis is wrong).
- **Encoding sweep**: the UTF-8/cp1252 codec bug documented 2026-06-XX (promote.py, auto_dream.py) recurred at every new read site in the memory pipeline — `graduate.py` (candidate JSON, LESSONS.md), `render_lessons.py` (4 more call sites), `learn.py`. Fixed the full `learn.py → graduate.py → render_lessons.py` chain in this session. **Not yet fixed**: `recall.py`, `show.py`, `skill_loader.py`, `decay.py`, `review_state.py` still have unencoded `open()` calls on tracked `.md`/`.jsonl` — flagged for a follow-up sweep, not blocking today's work.
- **Gotcha**: `graduate.py`'s retry-safety print path (`f"... {lesson_id} (retry)"` containing `→`) crashes with `UnicodeEncodeError` on Windows cp1252 stdout even after all file reads are UTF-8-safe — this is a *stdout* encoding issue, not a file-read issue; `PYTHONIOENCODING=utf-8` env var unblocks it without a source patch. The underlying graduation had already completed by the time the print crashed, so treat a post-completion print crash as cosmetic, not a rollback signal — verify via `grep lesson_<id> lessons.jsonl` before retrying.

## 2026-07-11 — PR #203 Blend Verdict (Sonnet 5 Architectural Review)

**Status:** Decision published, ready for execution  
**Confidence:** 4/5

### Finding: Two Parallel Lineages Required (Not Duplicates)

- **Lineage A** (`stm-pattern-integration-local`, commit `0f2a3829`): Docs + spec pseudocode fixes
- **Lineage B** (`worktree-pr-203-stm-integration`, `3376fa99` + `c62af7c3`): Code fixes + docs fixes

**Critical Discovery:** `orchestrator/state_transition_manager.py` does not exist on `main`. Lineage A fixes the SPEC pseudocode; Lineage B fixes the REAL Python code. Both required.

### Blend Strategy

1. Cherry-pick `3376fa99` (code fixes) onto `stm-pattern-integration-local`
2. Cherry-pick `c62af7c3` (docs fixes) onto `stm-pattern-integration-local`
3. Diff against `0f2a3829`, fold in A-only spec commentary
4. Push result to PR #203

### Outcome

- All 10 CodeRabbit findings closed
- No duplicate fixes
- No deferred work items (3 "TODOs" in Lineage A are already done in 3376fa99)

**Next agent:** Execute the blend execution checklist in `docs/phase-0-specifications/2026-07-11-PR203-BLEND-VERDICT.md`.


## 2026-07-11 — PR #203 Blend Execution Complete (Codex Review)

**Final Status:** ✅ READY TO MERGE with tracked Phase 2 TODOs

### Execution Summary

Selective blend (commit 482d7199) completed by executing agent after Codex verified:
- ✅ G4→G5 reputation feedback loop wired (record_equivocation targeting observer_id)
- ✅ Subnet-aware Sybil clustering via provenance_bucket() implemented
- ✅ Sybil accept-with-flag semantics correct
- ✅ Tests passing (24/24)

### Two TODOs Deferred (Non-Blocking)

**TODO-stm-observation-dedup** (Phase 2, Medium priority)
- Issue: Observation dedup via _seen_observations cache was dead scaffolding in Lineage B (declared but never read/written)
- Root cause: Sonnet's plan incorrectly assumed B's cache was functional
- Action: Implement bounded observation dedup (digest-based or TTL-based retention policy)
- Blocker: No (dedup risk lives in injected equivocation_log, not STM state)

**TODO-stm-concurrency-model** (Phase 2, Medium priority)
- Issue: threading.RLock() proposed by Sonnet doesn't serialize async pipeline (no atomicity across awaits)
- Root cause: Sonnet used threading primitive for async code (incorrect)
- Action: Implement asyncio.Lock() serializing full evaluate_observation pipeline
- Blocker: No (no concurrent caller path exists yet in orchestrator)

### Elegance Assessment

**Codex verdict:** 4/5 (Selective blend was architecturally superior to blind cherry-pick; agent correctly rejected unsafe fixes; tests added)

**Weakness:** Blend-verdict doc still claimed "all findings closed" (now false) — corrected below.

### Next: Phase 2 Planning

Two tracking documents updated:
1. Phase 2 integration backlog (formal TODO entries)
2. Blend verdict doc (correction note added)

## 2026-07-11 — agentic-stack `.agent/` Blend Tool + First Resolution Cycle

Built `scripts/git/agentic-stack-agent-blend.sh` to replay PT's `.agent/` customizations
across a `vendor/agentic-stack` pin bump (v0.9.0 → v0.18.0), mapping the AlphaClaw
`feature/MacOS-post-install` reverse-merge precedent onto file-level `git merge-file`
3-way merges (`.agent/` isn't its own submodule/branch, so the branch-level trick
doesn't apply directly). 16 files merged/staged clean; 7 real conflicts walked through
with the user via AskUserQuestion and resolved (2 needed combining both sides' fixes,
not picking one — a wrong single-side pick would have silently reintroduced an
already-fixed bug in each case). Brain-integration files stayed correctly blocked per
orama doc 41 §5.

Full writeup + reusable conflict-resolution playbook:
[`wiki/11-agentic-stack-agent-blend.md`](wiki/11-agentic-stack-agent-blend.md).

## 2026-07-12 — orama-system eats its own dogfood: the coordination system coordinated its own construction | Claude Code

**Session:** PR #206 (`chore(skills): salvage heartbeat wrapper...`) — started as a
one-file skill-wrapper salvage; by merge time it also carried STM security-pipeline
hardening, atomic claim/release transaction fixes, and memory-durability fixes.

**What happened:** Four sibling branches (#205 STM concurrency, #206 this one, #207
agentic-stack gitlink cleanup, #208 agentic-stack v0.18 bump) were being developed by
multiple concurrent AI coding sessions against the same repo in real time. None of the
sessions explicitly coordinated with each other. Instead, they coordinated *through
the exact system under construction*: `scripts/agent_coordination.py`'s GossipBus-backed
distributed task queue (claim → release → heartbeat, append-only events folded into
current state) — the same primitives one session was actively hardening became, purely
via shared git state on the branch, the de facto hand-off mechanism between sessions. One
session's committed fix was the next session's starting point; a gap one session left
open was frequently already closed by the time another session went looking for it.

**Why this is notable, not just messy:** it's an unplanned, real-load stress test of
the exact coordination guarantees being built — several sessions independently
converged on solutions to the same problems (an atomic claim+event transaction, a
Sybil witness-witness correlation signal, a dedup-key fix), and at least once one
session's fix silently regressed another's in-flight work on the same file (a stale
`obs.to_json()` dedup key reappeared on one branch after being fixed on another). That
regression was only caught because the final merge was reconciled by genuine line-level
harmonization across 19 conflicted files — not "pick HEAD or pick main" — preserving
each lineage's real improvements (one favored defensive engineering: `BEGIN IMMEDIATE`
write-locking, bounded retry-on-lock, event-loop guards; the other favored
crash-consistency and documentation depth: `fsync`-backed durability, hash cross-checks
on replay, thorough inline rationale) while dropping the handful of places a fix had
quietly gone backward.

**Lesson for future multi-agent sessions on a shared branch:** treat GossipBus/task-queue
state as a real coordination channel even when no session explicitly designed it that
way — `git fetch` + `git log HEAD..origin/<branch>` before starting substantial work
catches most of this early; for the unavoidable remainder, resolve merge conflicts by
reading and understanding both sides' *reasoning*, not by picking the side with more
lines or the side that landed first.

PR body updated with a matching explanation, appended before CodeRabbit's
auto-generated summary (not replacing it):
[PR #206](https://github.com/diazMelgarejo/Perpetua-Tools/pull/206).

## 2026-07-25 — Literal `~/` under Perpetua-Tools — `ALPHACLAW_INSTALL_DIR` tilde bug | Cursor

**Incident:** `Perpetua-Tools/~/.alphaclaw/` (~352 MB) created 2026-07-22 in ~2 minutes by
`alphaclaw_bootstrap --bootstrap` — not a recurring daemon.

**Root cause:** PT `.env` had `ALPHACLAW_INSTALL_DIR=~/.alphaclaw`; python-dotenv loads
tilde literally; `Path(...)` without `.expanduser()` is relative when bootstrap `cwd` is
PT repo root → literal `~/` folder under the repo. Nested `~/.alphaclaw/~/.alphaclaw/`
from writing `ALPHACLAW_ROOT_DIR='~/.alphaclaw'` into junk `.env`.

**Fix:** `src/utils/env_paths.py` (`resolve_alphaclaw_install_dir`), wired in
`alphaclaw_bootstrap.py` + `setup_wizard.py`; regression tests; `.gitignore` `/~/`;
wiki [`12-literal-tilde-alphaclaw-install-dir.md`](wiki/12-literal-tilde-alphaclaw-install-dir.md)
(+ orama mirror wiki/18). Merge archive deleted after additive merge to real install dir.

**Agent memory:** `lesson_fa44fbb4eb15`, `lesson_6bab6d268971`.

→ [wiki/12-literal-tilde-alphaclaw-install-dir.md](wiki/12-literal-tilde-alphaclaw-install-dir.md)
