# Review Queue

<!-- review-queue-dynamic -->

**Pending:** 10
**Oldest staged:** 2026-11-07T05:44:13.482004+00:00

Run `python .agent/tools/list_candidates.py` for detail, then:
- `python .agent/tools/graduate.py <id> --rationale "..."` to accept
- `python .agent/tools/reject.py <id> --reason "..."` to reject
- Review in a batch so cross-candidate contradictions are caught.

## Priority order (top 10)

- **02c827dbcb5f** (priority=9.14, size=1, rejections=0) — Qualification runners should exclusively create private evidence and temporary d
- **0992c6e96410** (priority=9.14, size=1, rejections=0) — Use isolated test ports and state rather than assuming default service ports are
- **35de991f1652** (priority=9.14, size=1, rejections=0) — Verify service lifetime after its command runner exits; disable scheduler instal
- **73d79fbe6645** (priority=9.14, size=1, rejections=0) — Inventory a measured Python environment without changing it: pip may intentional
- **4d7396e640e0** (priority=8.00, size=1, rejections=0) — Retain an unreaped POSIX child identity through every effectful group signal, re
- **5f7e10031478** (priority=8.00, size=1, rejections=0) — Containment must return unknown when permission to observe process-group members
- **67973dd9435b** (priority=8.00, size=1, rejections=0) — Provision external test tools in every CI workflow that collects dependent tests
- **75e0f7fa40ee** (priority=8.00, size=1, rejections=0) — Treat provider wire IDs, CLI capabilities, governance permission and verified la
- **9991c28c75b9** (priority=8.00, size=1, rejections=0) — A protected local ownership record must bind canonical repository metadata and a
- **d18a82793512** (priority=8.00, size=1, rejections=0) — After an interrupted multi-agent run, re-read Gossip and live PR heads, preserve
