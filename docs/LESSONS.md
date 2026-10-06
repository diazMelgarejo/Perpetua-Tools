# Lessons — Perpetua-Tools

> **Cross-repo companion:** [`orama-system/docs/LESSONS.md`](../../orama-system/docs/LESSONS.md) — read both at session start for joint context.
> **Architecture authority:** [`orama-system/docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md`](../../orama-system/docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md)
> **Navigation hub:** [`CLAUDE-instru.md`](../../../CLAUDE-instru.md)

---

## 2026-10-03 — Harness model governance pin (Alexandria)

Local pin: `docs/standards/model-governance.md` + `config/model-governance.yml`.
Canonical: alexandria `docs/standards/model-governance.md` (PR #1, tip `e7ee9db6`).
Sister: orama-system PR #381 (`812147f7`).

Cursor / Grok Bot default is `grok-4.6` medium with fast off.
Anthropic default is `claude-sonnet-5-5` medium.
`grok-4.5` is banned from catalog, defaults, and fallbacks.
Escalation token is S-AuthZ bearer plus fresh signed HITL (≤24h).
Cost gate stays fail-closed. Cloud escalation stays default-deny.
The local-first frugality ladder is not reordered.

---

## 2026-09-27 — Orama Knowledge Portal / swarm facade gap (PT)

Read-only Knowledge Portal search/MCP/A2A stays in orama-system and does not need PT endpoints. The swarm-approval slice already POSTs `PT /models/route` and `PT /v1/jobs` with role metadata. PT previously only had GET `/models/route` (`fallback_chain`) and left `JobSpec.role` empty when identity lived in `metadata`. Minimal facade: POST `/models/route` returning `backend_hint`/`model_hint`, hoist portal metadata onto `JobSpec`. Approval HMAC remains Orama-owned.

## 2026-09-28 — Swarm launch cache and job identity

Perpetua-Tools draft #404 was reopened on `cursor/portal-facade-route-jobs-3c54`. `POST /v1/jobs` now prefers top-level `role` / `session_id` / `artifact_policy` over the same keys in `metadata`. Orama portal launch dispatches the cached approved preview, fails closed without an approval secret, and sends `metadata.model` plus those top-level fields (`cursor/portal-swarm-approval-fixes-3c54`). Chronicle: `.agent/memory/working/PORTAL_FACADE_ORAMA_SWARM_2026-09-28.md`. Lesson: `lesson_8a6c4326be42`.

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

## 2026-07-08 — Cline Instance Map | Claude Code

**Lesson ID:** `lesson_d05c151e5302` | Salience: 7.0 | Confidence: 0.95

| # | PID | Process | Caller | Role |
|---|---|---|---|---|
| 1 | 51483 | node cline | zsh (terminal) | CLI launcher |
| 2 | 51484 | .cline main | PID 51483 | Active session (66.8% CPU, 619MB) |
| 3 | 44584 | .cline --cline-hub-daemon | PID 51484 (auto) | Hub daemon ws://127.0.0.1:25463/hub |
| 4 | 71165 | cline_mcp_server.mjs | Claude Code 0a13d9d5 | MCP stdio bridge |

Process tree: zsh -> node cline -> .cline -> .cline --cline-hub-daemon; claude --resume -> cline_mcp_server.mjs
cline-agent allowlisted in openclaw.json but NOT dispatched via gateway. All running ~2h.

> **Cross-repo memory note:** Preserved from `orama-system`; duplicated here by operator request so Perpetua-Tools main also carries the lesson.

---

## 2026-09-19 — PT PR #395 TLS bearer hops + Orama PR #363 peer ref

Follow-up on `fix/pt-pipeline-endpoint-tls-20260917`: keep bearer credentials on HTTPS for every pinned-transport redirect hop; reject spoofed `127.`-prefix hostnames in packaged endpoint-policy; CI checks out Orama via `refs/pull/363/head` (equivalent branch `cursor/tiered-pipeline-runtime-fb76`), not a missing `pr-363` ref. Graduated lesson `lesson_b7d7be187d74` plus working chronicle `.agent/memory/working/PT395_PIPELINE_ENDPOINT_TLS_FOLLOWUP_2026-09-19.md`. Publish was one ordinary fast-forward onto the existing PR branch (parent `d751f2aa`).

---

## 2026-09-17 — oramasys PR #14 review-thread cleanup (accept-risk deferred)

After [oramasys/oramasys#14](https://github.com/oramasys/oramasys/pull/14) cleanup: 11 fixed threads resolved, 0 open remain; PR still unmerged at `e424391fb35c`. Deferred accept-risk with **no open GitHub threads left to keep**: (1) FleetBindingStore ceremony vs S-AuthZ `/run` Bearer, (2) raw `uvicorn --host` without `bin/serve`, (3) in-process-only NIP-98 replay. Durable note: `.agent/memory/semantic/ORAMASYS_PR14_REVIEW_THREAD_CLEANUP_2026-09-17.md`.

---

