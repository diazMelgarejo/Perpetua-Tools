# Review Queue

## Next session — read this plan first

> Added: 2026-06-24

**Optimization priorities for both repos — 5-level strategic backlog**
- Plan file: [`orama-system/docs/plans/2026-06-24-optimization-priorities.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-06-24-optimization-priorities.md)

| Priority | Item | Status |
|----------|------|--------|
| **L1 BLOCKING** | perpetua-core hardware review (Mac Ollama + Win LM Studio) → `v0.2.0-alpha` | ⏳ Gate open |
| **L2 Critical** | `orama-system/src/oramaclaw/store.py:163` TOCTOU lock → atomic `O_CREAT\|O_EXCL` | ✅ Done `890e0c8` |
| **L3 Systemic** | `repo_hygiene.py` — LINT-010/011/012 | ✅ Done `55ec2f4` |
| **L4 Efficiency** | GitHub Action: post-merge-review-sweep.yml | ✅ Done `890e0c8` |
| **L5 Protocol** | combine-never-replace in `PT/.agent/AGENTS.md` | ✅ Done `c91a4f6` |

### New (2026-06-24): orama-system skill absorption plan
- Plan file: [`orama-system/docs/plans/2026-06-24-hermes-harness-canonical-onboarding.md`](https://github.com/diazMelgarejo/orama-system/blob/main/docs/plans/2026-06-24-hermes-harness-canonical-onboarding.md)
- Status: 📋 Updated `36b876e` — 3 architecture decisions added:
  - **Phase 7:** parametrize all LAN IPs to env vars (no raw literals in tracked files)
  - **Phase 8:** localhost-when-local rule — own machine → `localhost`, cross-machine → `$IP`; shared helper in `alphaclaw_bootstrap.py`
  - **Phase 9:** preserve Windows Hermes locals until migration complete; additive wrapper-first → no deletion until separately approved
- Ground truth: `agent_launcher.py` already has the locality rule + env-var IPs; gap is `alphaclaw_bootstrap.py` + Hermes docs

---

### Cursor agent commits landed in PT (2026-06-24, post-session)

| Commit | What |
|--------|------|
| `63b2f88` | hardware_policy_cli.py + hardware_policy.py: agent-oriented docstrings (CodeRabbit coverage) |
| `5709454` | hardware-affinity stack surfaced into skills + wiki (hardware/SKILL.md, docs/wiki/09, 15 files) |
| `17782d4` | Hermes Windows harness documented as PT policy consumer in wiki/09 + .agents/skills/hermes-harness |

All additive, no conflicts with our session work. Verified via git show.

---

<!-- review-queue-dynamic -->

_No pending candidates._
