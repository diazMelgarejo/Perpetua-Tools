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
- Status: 📋 Planned — enrich hermes-harness as canonical onboarding authority; absorb hermes-agent + pt-orama-harness-integration; merge local-inference into perpetua-hardware

---

## Candidate queue

_No pending candidates._ (Dream cycle 2026-06-24 `76d0407` graduated 4, rejected 2.)

Run `python .agent/tools/list_candidates.py` for detail, then:
- `python .agent/tools/graduate.py <id> --rationale "..."` to accept
- `python .agent/tools/reject.py <id> --reason "..."` to reject
