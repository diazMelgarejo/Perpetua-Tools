# Review Queue

<!-- review-queue-dynamic -->

**Pending:** 4
**Oldest staged:** 2026-11-07T05:44:13.482004+00:00

Run `python .agent/tools/list_candidates.py` for detail, then:
- `python .agent/tools/graduate.py <id> --rationale "..."` to accept
- `python .agent/tools/reject.py <id> --reason "..."` to reject
- Review in a batch so cross-candidate contradictions are caught.

## Priority order (top 10)

- **35de991f1652** (priority=8.00, size=1, rejections=0) — Verify service lifetime after its command runner exits; disable scheduler instal
- **73d79fbe6645** (priority=8.00, size=1, rejections=0) — Inventory a measured Python environment without changing it: pip may intentional
- **0992c6e96410** (priority=8.00, size=1, rejections=0) — Use isolated test ports and state rather than assuming default service ports are
- **02c827dbcb5f** (priority=8.00, size=1, rejections=0) — Qualification runners should exclusively create private evidence and temporary d
