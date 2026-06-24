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

---


**Pending:** 4
**Oldest staged:** 2026-06-22T12:35:50.597659+00:00

Run `python .agent/tools/list_candidates.py` for detail, then:
- `python .agent/tools/graduate.py <id> --rationale "..."` to accept
- `python .agent/tools/reject.py <id> --reason "..."` to reject
- Review in a batch so cross-candidate contradictions are caught.

## Priority order (top 10)

- **c094d281f841** (priority=50.40, size=3, rejections=0) — FAILURE in path-hygiene: Use ..\.. as canonical path
- **b387cb3fb5bf** (priority=22.40, size=2, rejections=0) — FAILURE in path-hygiene: Use ..\.. as canonical path
- **c094d281f841** (priority=50.40, size=3, rejections=0) — FAILURE in path-hygiene: Use ..\.. as cano
- **b387cb3fb5bf** (priority=22.40, size=2, rejections=0) — FAILURE in path-hygiene: Use ..\.. as cano
- **bb70a6833f36** (priority=22.40, size=2, rejections=0) — FAILURE in skill-absorption-map: hermes-harness should absorb hermes-agent and p
- **60d836556ff0** (priority=14.00, size=2, rejections=0) — Core lesson of the gbrain self-heal journey; applies beyond gbrain.
