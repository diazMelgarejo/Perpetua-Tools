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

