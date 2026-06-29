# Review Queue

<!-- review-queue-dynamic -->

**Pending:** 1
**Oldest staged:** 2026-06-22T12:58:32.342470+00:00

Run `python .agent/tools/list_candidates.py` for detail, then:
- `python .agent/tools/graduate.py <id> --rationale "..."` to accept
- `python .agent/tools/reject.py <id> --reason "..."` to reject
- Review in a batch so cross-candidate contradictions are caught.

## Priority order (top 10)

- **bb70a6833f36** (priority=26.24, size=2, rejections=0) — FAILURE in skill-absorption-map: hermes-harness should absorb hermes-agent and p

---

## 2026-06-29 (Mac session — wiring doc + H6 dispatch attempt)

### Completed this session
- ✅ OpenClaw → Hermes cross-harness wiring doc written + pushed: `orama-system/docs/how-to/openclaw-hermes-cross-harness-wiring.md` (commit `34d1a03`)
- ✅ Win peer probe: `portal-health` PASS · `peer-lmstudio` PASS (Win LM Studio serving 6 models on port 1234)
- ✅ Port 8002 reachable (Unauthorized = server up, just needs auth)

### Blocked / Pending
- ⛔ H6 dispatch: `HTTP 401` — requires `openclaw.gateway-auth-token` in Keychain
  - Fix: `printf '%s' 'ACTUAL_TOKEN' | bash orama-system/scripts/openclaw/store_keychain_secrets.sh openclaw.gateway-auth-token`
  - Once done: re-run `python3 bin/orama-system/skills/hermes-harness/scripts/lan_peer_assign.py drop --peer --file bin/orama-system/skills/hermes-harness/references/results/mac-hypothesis-h6-real-task.md --assignee win --topic autoresearch/gpu-run --fanout-id 2026-06-29-coord-021-h6`
- ⛔ Benchmark (Mac Ollama vs Win 27B): depends on H6 dispatch unblocking
- ⛔ `openclaw.gateway-auth-token` in Keychain: user must provide value
- ⛔ Win peer drop retry: `portal-status` is SKIP (same auth blocker) — will auto-resolve once gateway-auth-token is set
- 🔲 Optimization priorities L1: from `2026-06-24-optimization-priorities.md`
