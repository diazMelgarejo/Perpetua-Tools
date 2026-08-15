# Forensic Audit & Remediation Report: PR #354 & PR #355

**Date:** 2026-08-15  
**Scope:** Perpetua-Tools PR #354 (`repair/memory-lossless-20260815`) & PR #355 (`fix/sync-check-tdd-commit-bash32-20260815`)  
**Review Cross-References:** GitHub PR #354 (`discussion_r3788626078`, `discussion_r3789236814`), PR #355 (`pullrequestreview-4943811201`), Commits `4d968f9ef92d`, `f6aab5c01bd3`  

---

## 1. Executive Summary

This document records the empirical root-cause analysis and remediation steps applied across the Perpetua-Tools memory union and Git-guard synchronization PRs:

1. **Forensic Integrity of Line 1366 in `AGENT_LEARNINGS.jsonl`:**
   - *Problem:* A proactive-recall entry truncated at 500 characters by `post_execution.py` was previously repaired by adding unverified metadata (`"considered": 1275, "source_counts": {"lessons.jsonl": 6}`).
   - *Remediation:* Fabricated keys were removed. The JSON array was closed cleanly at the truncation boundary. The un-normalized raw string is preserved verbatim in `.agent/memory/working/MEMORY_UNION_INVALID_ROWS_2026-08-15.txt`.
2. **MCP Topology Resolution in `.codex/config.toml`:**
   - *Problem:* Switching to `mcp-remote` broke local execution due to subshell SSL certificate verification and missing Authorization headers.
   - *Remediation:* Replaced with the canonical in-repo resolver (`scripts/resolve_orama_root.sh`), which natively detects `$ORAMA_SYSTEM_PATH` / `$ORAMA_SYSTEM_ROOT` and crawls outward without fragile hardcoded paths.
3. **PR #355 Review Fixes & Git Guard Hardening:**
   - Addressed CodeRabbit review findings regarding `git diff-tree` on merge commits in `.githooks/pre-push` and scanner self-matching in `scan-tracked-banned-tokens.sh`.

---

## 2. Commit SHA Cross-References

| Component | Target SHA / Branch | Resolution Summary |
|---|---|---|
| Memory Union & Line 1366 Normalization | `repair/memory-lossless-20260815` (PR #354) | Closed JSON array without fabricating unverified counts; preserved raw capture in sidecar |
| Exa MCP Local Resolver Integration | `4d968f9ef92d` $\to$ PR #354 remediation | Configured `.codex/config.toml` to use `scripts/resolve_orama_root.sh` |
| Bash 3.2 Guard & CI Catch-up | `8a8942d4d2f5`, `7691f7252685` (PR #355) | Full manifest catch-up from canonical orama-system |
