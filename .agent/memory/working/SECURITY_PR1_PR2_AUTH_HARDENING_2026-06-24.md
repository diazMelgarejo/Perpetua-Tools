# Security PR1+PR2 auth hardening session (PT #177 + orama #127)

**Branch (both repos):** `cursor/security-pr1-pr2-auth-hardening-f559`  
**Status:** CI green after parity fix; awaiting merge after #126 (orama hermes CI)

## Where to look

| Surface | PT | orama-system |
|---------|-----|--------------|
| Token persist 0600 | `orchestrator/control_plane_auth.py` | `src/utils/control_plane_auth.py` |
| /health SSRF guard | `orchestrator/fastapi_app.py` | — |
| Bootstrap redaction | `orchestrator/fastapi_app.py` + `tests/test_runtime_bootstrap_redaction.py` | — |
| Model endpoint policy | `src/utils/model_endpoint_url.py` | same path |
| Parity CI | `scripts/review/verify_model_endpoint_policy_parity.py` + `.github/workflows/ci.yml` | same |
| Portal CSRF | — | `src/orama_system/portal_server.py` + `tests/test_portal_lifecycle_csrf.py` |
| start.sh token weak check | — | `start.sh` |
| PS 5.1 LAN bind | — | `platform/windows/start.ps1` |

## CI parity failure (Oramasys diagnosis)

**Symptom:** `model-endpoint-policy-parity: FAIL — policy functions diverged`

**Root cause:** Comparator checked each PR branch against sibling `main`. Policy changes exist only on open PR branches → guaranteed false failure.

**Fix:** On `pull_request`, checkout sibling at `github.head_ref`; fallback `main` with `rm -rf` sibling dir first. Comparator uses `ast.dump()` not `ast.unparse()`.

**Green runs:** PT `28333911916`, orama `28334035588` (commits `c3957d7` / `e9059d1`).

## Lessons graduated (learn.py)

- `lesson_4b3d787319a1` — parity CI head_ref checkout
- `lesson_c97cfd0679bb` — ast.dump parity
- `lesson_816433497c31` — urlparse port → ModelEndpointPolicyError
- `lesson_67a7e561207f` — _secure_write_token 0600
- `lesson_1d3b8cae0eef` — /health SSRF guard
- `lesson_fb42336ab528` — bootstrap redaction
- `lesson_3e31f4040c55` — portal lifecycle CSRF
- `lesson_c935b0102fb9` — stacked cross-repo branch names
- `lesson_cc6cbd625069` — LINT-006 /tmp fixtures
- `lesson_*` — portal HTML escape (portal XSS)

## PR body rule

Append-only summaries for #127 and #177 — never replace original PR1+PR2 scope; add `## Updates` / `---` tail sections.

## Post-merge

Once both land on `main`, parity gate compares `main`↔`main` as intended.

## Local verify

```bash
ORAMA_SYSTEM_ROOT=/path/to/orama-pr-branch python3 scripts/review/verify_model_endpoint_policy_parity.py
```
