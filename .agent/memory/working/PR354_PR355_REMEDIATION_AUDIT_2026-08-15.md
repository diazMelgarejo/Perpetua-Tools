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

---

## 3. Mandatory Pre-Execution & Push Authorization Record

Per the repository's prime directives and safety rules (`AGENTS.md` and `protocols/permissions.md`):
- *"Edit first, commit later - Make changes, AskUserQuestion if they're correct, commit if YES; no question or no answer is NOT a yes."*
- *"Commit first, push later - Only push when everything is verified by the user and final."*
- *"Never push or force-push without explicit user authorization."*

### Pre-Execution Verification & Approval Sequence

1. **Authorization Gate:** An explicit confirmation prompt detailing proposed batches, target branches (`repair/memory-lossless-20260815`), test suites, and git guards was submitted to the operator.
2. **Operator Authorization:** Granted by the operator on 2026-08-15 (`"yes confirmed,GO!"`).
3. **Execution Batches:**
   - **Batch 1 (`f6223571`):** Memory provenance normalization for line 1366, sidecar capture, MD013 formatting.
   - **Batch 2 (`0e61959c`):** Forensic audit documentation in working memory.
   - **Batch 3 (`81a841a4`):** Exa MCP configuration using `scripts/resolve_orama_root.sh`.
4. **Final Gate & Push:** Verified with 35/35 passing unit tests and clean `verify-git-guards.sh` output (`banned=0 bad_author=0 bad_coauthor=0 commits=3 clean=yes`). Pushed cleanly to `origin/repair/memory-lossless-20260815`.

