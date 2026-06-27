# Workspace — Session Close 2026-06-27 (security hardening)

Last written by: cursor-agent (cloud)
Branch: `cursor/security-hardening-pre-v2-c4ae` (both repos)

---

## Next agent: START HERE

### Read these first (in order)
1. [`orama-system/docs/plans/2026-06-27-security-hardening-pre-v2.md`](../../orama-system/docs/plans/2026-06-27-security-hardening-pre-v2.md) — platform schedule + tier status
2. [`docs/LESSONS.md` §2026-06-27](../docs/LESSONS.md) — penultimate human-readable summary
3. This file's **Open gates** section below

### Run these first (confirm state)
```bash
cd orama-system && git checkout cursor/security-hardening-pre-v2-c4ae
cd orama-system && python3 scripts/sync_version.py --check
cd orama-system && python3 -m pytest -q tests/test_concurrent_lock.py tests/test_oramaclaw_store.py
cd Perpetua-Tools && git checkout cursor/security-hardening-pre-v2-c4ae
cd Perpetua-Tools && python3 scripts/check_model_ids.py
cd Perpetua-Tools && unset OPENCLAW_EXTRA_PORTS && python3 -m pytest -q tests/test_alphaclaw_bootstrap.py tests/test_git_attribution_guard.py::test_check_commit_message_malformed_coauthor_fuzz
```

### First task on live Mac + Windows 11 (tomorrow)
- `bash start.sh --status` → hard-requirements green
- Ollama probes: `qwen3.5:9b-nvfp4`, `bge-m3`
- Win LM Studio: `LM_STUDIO_WIN_ENDPOINTS` reachable from Mac LAN
- `start.sh --hardware-policy` harness
- If E2E green → merge PRs #113 + #154 → T5 tag `v1.1.1` + `oramasys/v2-foundation`

---

## System state (EOD 2026-06-27)

| Repo | Branch | Tip | Linux tiers |
|---|---|---|---|
| orama-system | `cursor/security-hardening-pre-v2-c4ae` | `de5c820` | T2-C, T3-A/C, T4-A/B/C ✅ |
| Perpetua-Tools | `cursor/security-hardening-pre-v2-c4ae` | `627d3a3` | T1-A/B/C, T2-B, T3-B ✅ |
| Version | both | `1.1.1.0` | T5 freeze ⏳ Mac/Win |

**PRs:** [orama #113](https://github.com/diazMelgarejo/orama-system/pull/113) · [PT #154](https://github.com/diazMelgarejo/Perpetua-Tools/pull/154)

---

## Security hardening completed (Linux cloud)

### Perpetua-Tools
- T1-A: `routing.json` jsonschema + RFC-1918 validation
- T1-B/C: URL canonicalization + `audit_policy_enforcement.py`
- T2-B: `scripts/check_model_ids.py` allowlist
- T3-B: Co-authored-by fuzz tests (6 cases)

### orama-system
- T2-A/C: LINT-014 + line-level LINT-013
- T3-A: concurrent lock stress test
- T3-C: orphan pending archive under `registry/orphan-conflicts/`
- T4-A/B/C: dep pins, LM token warning, SBOM JSON

---

## Open gates (priority order)

| Priority | Item | Status | Needs |
|---|---|---|---|
| **E2E** | `start.sh` + hardware-policy + keychain | ⏳ tomorrow | 🍎 Mac + 🪟 Win 11 |
| **T5** | Tag `v1.1.1`, release, `oramasys/v2-foundation` | ⏳ blocked | E2E green |
| **L1** | perpetua-core hardware review → `v0.2.0-alpha` | ⏳ local only | Live Mac+Win |
| Phase 6/9 | Hermes thin skills + Windows wrappers | ⏳ deferred | Live Windows |
| L6 | `schemas/*.schema.json` | 📋 planned | Any machine |

---

## .agent memory updates (this session)

- **lessons.jsonl:** 5 graduated lessons (`lesson_a0d29898cd65` … `lesson_2abff9b4e522`)
- **DECISIONS.md:** 2026-06-27 pre-v2 security freeze gate
- **episodic:** `2026-06-27-security-hardening-linux-complete`
- **docs/LESSONS.md:** penultimate §2026-06-27 (both repos)
