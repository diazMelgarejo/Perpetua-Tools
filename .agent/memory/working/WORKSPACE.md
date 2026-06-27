# Workspace — Session Close 2026-06-27 (end)

Last written: claude-sonnet-4.6

---

## Next agent: START HERE

```bash
# 1. Confirm branch state
git -C orama-system log --oneline origin/cursor/security-hardening-pre-v2-c4ae -3
git -C Perpetua-Tools log --oneline origin/cursor/security-hardening-pre-v2-c4ae -3

# 2. Verify CI
# PT PR #154:  https://github.com/diazMelgarejo/Perpetua-Tools/pull/154  ← 4/4 green
# OS PR #113:  https://github.com/diazMelgarejo/orama-system/pull/113    ← 13/14 (see notes)

# 3. DO NOT MERGE #154 or #113 — human review required
```

---

## System state

| Repo | Branch | Tip | CI |
|---|---|---|---|
| orama-system | main | `b962ab0` | ✅ |
| orama-system | `cursor/security-hardening-pre-v2-c4ae` | `81e909dbd5` | ⚠️ 13/14 (see note) |
| Perpetua-Tools | main | `43641a2` | ✅ |
| Perpetua-Tools | `cursor/security-hardening-pre-v2-c4ae` | `c8e771f` | ✅ 4/4 |
| perpetua-core | local `feat/salvage-plugins-rc1` | 56 tests ✅ | push gate OPEN |

---

## PRs awaiting human review (DO NOT MERGE)

| PR | Repo | What | CI | Status |
|---|---|---|---|---|
| #154 | Perpetua-Tools | S4: _validate_pt_state + RFC-1918 allowlist; S8: module-level URL canonicalization at import time; S3: audit_policy_enforcement.py; T2-B: check_model_ids.py (allowlist); version 1.1.1.0 | 4/4 ✅ | Awaiting human review |
| #113 | orama-system | LINT-014 argv secret scan; orphan conflict archival; concurrent lock stress test; SBOM v1.1.1.0; check_dep_pins.py; version 1.1.1.0 | 13/14 ⚠️ | Awaiting human review (see CI note) |

**PR #113 CI note:** 1 failing job (`test` matrix entry) = `pytest-asyncio` not installed
in that CI step. `pytest-asyncio~=0.23.0` IS declared in `pyproject.toml` dev deps and
the test passes locally. Reviewer should verify CI `pip install` includes `[dev]` extras.

**PR #156** (CodeRabbit UTG): ✅ merged into the PT security branch (not main).
22 new tests added; 3 regressions in check_model_ids.py fixed (see AGENT_LEARNINGS #98-99).

---

## Open gates (priority order)

| Priority | Item | Status | Needs |
|---|---|---|---|
| **Human gate** | Review + approve PR #154 (PT) | ⏳ awaiting | Human decision |
| **Human gate** | Review + approve PR #113 (OS) | ⏳ awaiting | Human decision (fix CI note first) |
| **L1 BLOCKING** | perpetua-core hardware review → push → tag `v0.2.0-alpha` | ⏳ local only | Live Mac+Win |
| Phase 6 | `install_hermes_thin_skills.py --install --verify --test` | ⏳ | Live Windows |
| Phase 9 | Windows thin wrapper migration | ⏳ | Live Windows |
| L6 | `schemas/` JSON Schema files | 📋 planned | Any machine |
| T3-A | Concurrent lock stress test (already in PR #113) | In PR #113 | Merges with #113 |

---

## Architectural decisions this session

1. **S4 fix pattern**: unvalidated JSON from filesystem → schema validation + hostname allowlist.
   Any file consumed via `json.load()` and fed to network dispatch must be schema-validated.
2. **S8 fix pattern**: helper fixes don't protect callers that bypass the helper.
   Module-level constants set at import time from env vars must be canonicalized at that same
   import time, not deferred to the helper's return path.
3. **Merge gate rule**: 'for manual review' = read + fix branch + document + stop.
   Never merge without explicit 'merge', 'ship', 'land it' authorization.
4. **YAML regex pattern**: `^\s*name:` misses `- name:` (list items). Always use `^\s*-?\s*name:`.
5. **Path display in tests**: functions using `.relative_to(ROOT)` need try/except when
   tests monkeypatch the path to tmp_path outside the repo root.

---

## Append: branch catalog gold nuggets (2026-06-27)

**Catalog:** `.agent/memory/working/BRANCH_COMPARISON_2026-06-27.md` (tree-twin / `reanchor_scan` — corrected)

**Sticky git skills (before next rebase/delete):**
- orama `bin/orama-system/skills/git-history-surgery/SKILL.md`
- `references/reanchor-after-rewrite.md`
- PT `scripts/git/reanchor_scan.sh . origin/main heads`

**Key correction:** `cursor/critical-bug-investigation-0df5` is **MERGED/in-main** (twin `ad702c5`), not unrelated orphan — re-anchor or delete local; do not rebase.

**PR candidates after `git cherry` verify:** `chore/domain-knowledge-windows-shims`, `fix/pr135-lint006-windows` (orama), `2026-06-11-001-win-endpoint-discovery-sync`, `clean-pt127`.

**Memory updated:** DOMAIN_KNOWLEDGE § Git gold nuggets, DECISIONS 2026-06-27 tree-twin, episodic + learn.py lessons (this session).
