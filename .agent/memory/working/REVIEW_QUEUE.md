# Review Queue

<!-- review-queue-dynamic -->

**Pending:** 1
**Oldest staged:** 2026-06-22T12:58:32.342470+00:00

Run `python .agent/tools/list_candidates.py` for detail, then:
- `python .agent/tools/graduate.py <id> --rationale "..."` to accept
- `python .agent/tools/reject.py <id> --reason "..."` to reject
- Review in a batch so cross-candidate contradictions are caught.

## Priority order (top 10)

- **bb70a6833f36** (priority=29.07, size=2, rejections=0) — FAILURE in skill-absorption-map: hermes-harness should absorb hermes-agent and p

---

## 2026-07-01 (Mac session — ClinePass/dispatch-race verification, Win subnet blocker)

### Confirmed already shipped (verified live, not re-implemented)
- ✅ ClinePass AutoResearcher fallback (Mac + Win): `orama-system/scripts/cline_autoresearcher.py` — 26/26 tests pass. Live check on Mac: gateway running, ollama idle, cline CLI available, `should_fallback: false` (correct — gateway is up).
- ✅ Parallel dispatch race (cursor-agent vs Hermes+LM Studio, first-wins): `orama-system/scripts/spawn_agents.py::_dispatch_race`.
- ✅ Solo-mode resilience (10x unreachable → demote → 15min recheck): `lan_peer_session.py` state machine. Live check confirms `solo_mode: true`, `failure_count: 65`, `retry_seconds: 900` — working exactly as designed.
- ✅ Added missing `.claude/skills/cline-openclaw-agent/SKILL.md` thin wrapper (every other OpenClaw fabric skill had one; this one didn't) — commit `df6f910`.

### Blocked — real infra, not a bug
- ⛔ Win moved to a **different subnet** (`192.168.9.18`) vs Mac's `192.168.254.x` — this is a genuine cross-subnet/VPN situation, not a retry-fixable issue. `probe_lan_peer.py` correctly reports unreachable; solo-mode is correctly engaged. No action possible from Mac until Win rejoins the same LAN or a VPN/route is added.
- `config/devices.yml` left uncommitted intentionally (user: "ignore this run, IP will return after brief interruption") — do not commit until Win IP stabilizes.

### Not done (needs a human on the Win box or Win back on-LAN)
- Actual dispatch/benchmark run against Win coder (blocked by the subnet issue above)
- H6 real task, coord-022 listen task — still queued, waiting for reachability
