# Portal facade review and draft plan

**Status:** Complete on lockstep branch `cursor/portal-facade-hardening-751b` (orama PR #374, PT PR #414).  
**Perpetua-Tools `main`:** `8eabb6e3769ddf5c8d63bda07bb07c71b4aa1f50` (merge of #408, 2026-10-01)  
**orama-system `main`:** `fe247da0b55e491e745be9e6014ae6d518a8b35d` (merge of #372, 2026-10-01)  
**Complexity:** Medium

**Working copy location (for clone / IDE):**  
`Perpetua-Tools/.agent/memory/working/portal-facade-review-and-plan.md`

**Note (2026-10-01):** An agent started Phase 1 locally on `cursor/lineage-replay-provenance-8633` (uncommitted edits to `orchestrator/fastapi_app.py` and `orchestrator/supervisor.py`). That work was **not** approved; it is **not** reverted. Finish or discard it only after you review this plan.

`orchestrator/fastapi_app.py`, `orchestrator/supervisor.py`, `orchestrator/worker_registry.py`, and `src/orama_system/portal_server.py` on those tips match the copies read for this review. Tests and CI logs were not re-run.

---

## 1. Requirements restatement

Close the gaps found after the portal and swarm merges, without moving knowledge, MCP, or A2A into Perpetua-Tools.

Perpetua-Tools stays the durable job authority and the co-install route shim (`POST /models/route`, hoisted job identity, supervisor replay). orama-system stays the Knowledge Portal: preview cache, fail-closed launch approval, and a proxy to Perpetua jobs.

This document records what those merges already guarantee, what is still wrong, and the implementation plan to fix the remaining gaps. Implementing it requires a separate yes.

---

## 2. Why this stack exists

Perpetua-Tools `.agent/memory/working/PORTAL_FACADE_ORAMA_SWARM_2026-09-28.md` and `2026-09-30-three-day-cycle-pr404-pr408-pr410-pr413-synthesis.md` record one decision. The Orama Knowledge Portal and fail-closed swarm approval needed Perpetua as the job authority. Knowledge search, MCP, and A2A stay in orama-system.

That decision produced three defect classes:

1. Portal launch rebuilt previews, and job identity lived only in metadata. Perpetua #404 added `POST /models/route` and hoisted job fields. Orama stopped rebuilding the preview at launch.
2. Terminal lifecycle events omit `JobSpec`. Replay from those events had no task. #408 rebuilds from the durable `QUEUED` event, admits only terminal predecessors, and restamps `caller_reported`. Graduated as `lesson_2517668c02a5`.
3. Route hints and CI had to match the live FastAPI app. #410 keeps specialization and omits an unassigned backend hint. #413 isolates route tests and maps replay to 404, 409, and 422. Orama #372 sends `specialization` on the route POST.

The findings below are what those merges left open.

---

## 3. Decision checks on these SHAs

| Claim | On these tips |
|---|---|
| `POST /models/route` returns `backend_hint` and `model_hint`; `GET` still returns `fallback_chain` | Holds. `_models_route_payload` is shared and also adds `backend`, `provider`, `model`, and `model_id`. |
| `POST /v1/jobs` hoists role, specialization, session, parent, and artifact policy; top-level wins | Holds. `_field()` prefers the explicit value, then metadata. `task_type` falls back to `constraints`. |
| Session and parent ids are correlation, not authentication | Holds. Submit sets `lineage_trust="caller_reported"`. Replay's only override is `authenticated_lane` from the current request. |
| Replay failures map to 404, 409, and 422 | Holds for the three supervisor phrases. Other `ValueError`s become 400. A bad job id is a separate 400 before the supervisor runs. |
| Orama sends top-level job identity plus `metadata.model`, and omits `auto` | Holds in `api_swarm_launch`. |
| Launch uses the cached preview and fails closed | Holds. `cached_preview`, then `check_launch`, then hardware policy (`ok` defaults false), then `consume_launch`, then job posts. |
| Route failures are recorded as `routing_error` | Holds. The value is the exception class name. |
| Perpetua checkout order | Holds: three env vars, sibling `Perpetua-Tools` / `perpetua-tools`, then the historical `perplexity-api` path. |
| Orama stores no job state | Holds. Preview cache plus a proxy to Perpetua. |
| Specialization is on the route call | Holds. Orama sends it. `resolve_role_backend(role, specialization)` consumes it before the fallback chain. |
| Spawn affinity treats a name containing `win` as Windows | Holds in `api_spawn_agent`. |
| Knowledge, MCP, and A2A skip portal auth | Holds. `portal_path_is_public` allows `/health`, `/.well-known/agent-card.json`, `/api/mcp`, `/api/a2a`, `/assets/`, and `/api/knowledge/`. |
| Approval tokens are single-use and drift-checked | Holds. `check_launch` compares the fingerprint. `consume_launch` pops the cache. A second consume fails. |

---

## 4. Vertical: replay

`POST /api/jobs/{job_id}/replay` (`api_job_replay_proxy` in `src/orama_system/portal_server.py`) posts to Perpetua `POST /v1/jobs/{job_id}/replay`.

`supervisor_replay_job` in `orchestrator/fastapi_app.py`:

1. Rejects a non-UUIDv4 id with HTTP 400 and the fixed detail `job_id must be a uuid4-formatted server-issued identifier`. That string is absent from orama's allowlist, so the portal shows `Request failed` and still returns `upstream_status`.
2. Calls `OrchestrationSupervisor.replay` with one override: `authenticated_lane` from the current request.
3. Maps `ValueError` through `_replay_value_error_to_http` by substring:
   - text containing `not found` becomes 404 `Job not found`
   - `not replayable` becomes 409 `Job is not replayable`
   - `queued specification` becomes 422 `Job has no queued specification`
   - anything else becomes 400 `Replay request could not be completed`

`OrchestrationSupervisor.replay` in `orchestrator/supervisor.py`:

- The latest event must be `SUCCEEDED`, `FAILED`, or `CANCELLED`. `QUEUED`, `RUNNING`, and `WAITING_INPUT` raise `not replayable`.
- The new `JobSpec` is rebuilt from the first `QUEUED` event via `_queued_spec_for_job`, not from the terminal event. A missing queued spec raises `has no queued specification`.
- `lineage_trust` is forced to `caller_reported`. The HTTP override replaces `authenticated_lane` and does not promote a stored label to `verified`.
- The new job goes through `submit_job`, so it receives a fresh id and a new `QUEUED` event.

Orama `_REPLAY_UPSTREAM_DETAILS` keeps only the three fixed details. The generic 400 and the malformed-id detail become `Request failed`.

The fragile layer is the substring classifier inside Perpetua, not the copied allowlist. Any unrelated `ValueError` whose text contains `not found` becomes 404. A reworded supervisor message falls through to 400, and the portal shows `Request failed`. That degrades the message and fails safe.

---

## 5. Vertical: `POST /models/route`

`_build_swarm_preview` calls `api_status()`, then posts one route body per role in `_SWARM_PREVIEW_ROLES`. Each body carries `objective`, `task_type`, `role`, `specialization`, and `preferred_device` (`mac`, `windows`, `shared`, or `auto`).

`route_post` delegates to `_models_route_payload` in `orchestrator/fastapi_app.py`:

- `_normalize_preferred_device` drops `auto`, `none`, and `default`. `mac`, `windows`, and `shared` pass through unchanged.
- `registry.route_task` builds `fallback_chain`. Device preference is an exact match on `ModelTarget.device` (`mac-studio`, `win-rtx3080`, `shared-ollama` in `config/models.yml`). The portal words do not match those ids, so they do not reorder the chain.
- The frugality gate in `orchestrator/gate.py` still treats a device string containing `win` as `windows_only`. The word `windows` contains that substring.
- If `role` is set, `resolve_role_backend(role, specialization)` in `orchestrator/worker_registry.py` wins. On this SHA the map is static:
  - `executor-agent` plus `python-coding` or `test-writing` goes to `lmstudio-win` and the Windows Qwen id
  - `context-agent` specializations go to `ollama` and `qwen3.5:9b-nvfp4`
  - an unknown specialization falls back to `(role, None)`
- If that map misses, the first chain entry supplies `backend_hint` and `model_hint`. LM Studio devices containing `win` become `lmstudio-win`. Other LM Studio devices become `lmstudio-mac`.
- The same backend string is copied to `backend`, `provider`, and `backend_hint`. The model string is copied to `model`, `model_id`, and `model_hint`.

Orama reads backend keys in the order `backend_hint`, `backend`, `provider`, and treats `auto` as unset. Model keys are `model_hint`, `model`, `model_id`. A failed post stores `routing_error` as the exception class name and may fill `backend_hint` from the hardware-policy safe default (`lmstudio-win` for context and architect when Windows is safe, otherwise Mac, otherwise Windows). Preview `routing_source` is `pt:/models/route` when any assignment succeeded, otherwise `portal:fallback`.

Launch submits those cached hints. It does not call `/models/route` again.

`provider` is the backend name. Orama already treats it as a backend hint. Renaming it would break that reader.

---

## 6. Findings

### Medium

1. **Import-time crash on Windows.** `HEALTH_LM_STUDIO_CANDIDATES` is computed while `orchestrator/fastapi_app.py` is imported. On Windows, an unset `LM_STUDIO_WIN_ENDPOINTS` raises `RuntimeError`. The co-install shim fails before `/health`. The loud failure belongs on health and on dispatch. `worker_registry.py` already fails loudly for the Windows endpoint on the dispatch path.
2. **Job list redaction is uneven.** `/api/jobs/{id}` and `/api/app/state` use `redact_job_record` / `redact_jobs_payload` in `src/utils/control_plane_auth.py`. `GET /api/jobs` (`api_jobs_proxy`) and `GET /api/v1/jobs` (`api_get_jobs`) return the Perpetua payload unchanged, including prompt and metadata. Portal auth still covers those routes.
3. **A partial swarm launch leaves orphans.** `consume_launch` in `src/orama_system/swarm_approval.py` runs before the five `POST /v1/jobs` calls in `api_swarm_launch`. If a later post fails, earlier jobs stay queued under the same `session_id`, the response is `accepted: false`, and the token cannot be reused.
4. **Preview and launch run the full status path.** `_build_swarm_preview` and `api_swarm_launch` call `api_status()`. That probes backends and, when notifications are enabled, publishes an event. Preview and launch pay that cost for a hardware-policy read.

### Low

- `supervisor_submit_job` returns `detail=str(exc)` on 400. Replay uses fixed details.
- Portal `preferred_device` values are not registry device ids. See section 5.
- Orama's replay allowlist omits the generic 400 detail and the malformed job-id detail.
- Perpetua CORS lists `http://localhost:3000` and `http://localhost:8002` twice each.
- `_co_orchestration_html_response` resolves a loopback control-plane token. `_portal_cp_fetch_bootstrap` discards the argument so the page never embeds a bearer.
- `_write_env_var` imports `fcntl` outside its `try`. `/api/configure-tool` raises before the handler on Windows. `_pid_on_port` depends on `lsof` or `ss`.

### Leave unchanged

- Public knowledge, MCP, and A2A routes. Tightening them is an auth-policy change, not a defect in this stack.
- The `provider` key, as long as the route docstring says it is a backend-hint alias.

---

## 7. Patterns to mirror

| Category | Source | Pattern |
|---|---|---|
| Naming | `orchestrator/fastapi_app.py` `_replay_value_error_to_http` | Fixed client details. Status comes from a known failure class. |
| Errors | `src/orama_system/portal_server.py` `_client_safe_error` | Log the exception. Return a stable client string. |
| Logging | `orchestrator/fastapi_app.py` `_startup_log.warning` | Warning for a degraded startup path. Full exception stays server-side. |
| Data access | `orchestrator/supervisor.py` `_queued_spec_for_job` | Read the durable `QUEUED` event from the jobs JSONL. Do not invent a second store. |
| Redaction | `src/utils/control_plane_auth.py` `redact_jobs_payload` | Allowlist job fields. Drop prompt and metadata. |
| Tests | `tests/test_swarm_launch.py`, `tests/test_fastapi_supervisor.py` | Patch the live function the route calls. Assert status and body. |

---

## 8. Files to change (when implementation is approved)

| File | Action | Why |
|---|---|---|
| `Perpetua-Tools/orchestrator/fastapi_app.py` | UPDATE | Lazy health candidates, device-word normalization, stable replay errors, fixed submit 400 detail, CORS list |
| `Perpetua-Tools/orchestrator/supervisor.py` | UPDATE | Raise distinct replay errors instead of free-form sentences the HTTP layer parses |
| `Perpetua-Tools/tests/test_fastapi_health.py` | UPDATE | Import succeeds on Windows without `LM_STUDIO_WIN_ENDPOINTS`; `/health` still reports the gap |
| `Perpetua-Tools/tests/test_fastapi_supervisor.py` | UPDATE | 404 only for the missing-job error; submit 400 uses a fixed detail |
| `Perpetua-Tools/tests/test_portal_facade_route.py` | UPDATE | `windows` / `mac` / `shared` affect route order; exact device ids still match |
| `Perpetua-Tools/tests/test_hardware_routing.py` | UPDATE | Same device-alias coverage at the registry boundary if the helper lives there |
| `orama-system/src/orama_system/portal_server.py` | UPDATE | Redact job lists, hardware-policy helper, launch rollback, replay allowlist, drop unused token resolve, guard `fcntl` |
| `orama-system/src/orama_system/swarm_approval.py` | UPDATE | Consume the token only after a full accept, or restore it when the batch rolls back |
| `orama-system/tests/test_swarm_launch.py` | UPDATE | Partial failure cancels or reports orphans, and one retry of that preview works |
| `orama-system/tests/test_swarm_preview.py` | UPDATE | Preview does not publish a notification |
| `orama-system/tests/test_control_plane_auth.py` | UPDATE | List routes omit prompt and metadata |
| `orama-system/tests/test_portal_jobs_redaction.py` | ADD | HTTP + unit coverage for `/api/v1/jobs` bare list shape |

---

## 9. Tasks

### Phase 1 — Perpetua-Tools (done)

Branch from `main` `8eabb6e3769ddf5c8d63bda07bb07c71b4aa1f50` only after this plan is approved for implementation.

**Task 1. Lazy Windows health candidates** — [x]

- Action: Stop calling `_resolve_health_lm_studio_candidates()` at import. Resolve on `/health` and on any probe that needs those URLs. An unset `LM_STUDIO_WIN_ENDPOINTS` on Windows logs a warning and makes `/health` report the failure. Import of `fastapi_app` succeeds.
- Mirror: The existing loud failure in `worker_registry.py` stays on the dispatch path.
- Validate: `pytest tests/test_fastapi_health.py -q`

**Task 2. Portal device words** — [x]

- Action: Map `mac`, `windows`, and `shared` onto the configured device ids before `route_task`. Leave exact ids such as `win-rtx3080` unchanged. `auto` stays unset.
- Mirror: `select_for_role` already partitions candidates by exact `device`. The new helper feeds that function. It does not add a second router.
- Validate: `pytest tests/test_portal_facade_route.py tests/test_hardware_routing.py -q`

**Task 3. Stable replay errors** — [x]

- Action: Raise named errors (or stable codes) from `replay` for missing job, non-terminal state, and missing queued spec. Map those types in `_replay_value_error_to_http`. Keep the three public detail strings. A `ValueError` whose text merely contains `not found` stays 400.
- Mirror: Today's fixed detail strings in `_replay_value_error_to_http`.
- Validate: `pytest tests/test_fastapi_supervisor.py -q`

**Task 4. Fixed submit error detail** — [x]

- Action: `supervisor_submit_job` returns one fixed 400 detail for `ValueError` and `RuntimeError`. Log `str(exc)` server-side.
- Mirror: `_client_safe_error` on the orama side, and the replay mapper's generic 400.
- Validate: the same supervisor test module.

**Task 5. CORS list** — [x]

- Action: Keep one entry each for `http://localhost:3000` and `http://localhost:8002`.
- Validate: import or a one-line assertion if a CORS test already exists. Do not add a test file only for duplicate strings.

### Phase 2 — orama-system (done)

Branch from `main` `fe247da0b55e491e745be9e6014ae6d518a8b35d` after Phase 1 freezes the public replay strings. The allowlist is lockstep with Perpetua.

**Task 6. Redact job lists** — [x]

- Action: Run `redact_jobs_payload` in `api_jobs_proxy` and `api_get_jobs` before returning. Read the jobs-panel script first and keep every field it renders (`job_id`, `status`, `role`, and the other allowlist keys).
- Mirror: `redact_job_record` already used by `/api/jobs/{id}`.
- Validate: [x] `pytest tests/test_control_plane_auth.py -q` — `test_redact_jobs_list_omits_prompt_and_metadata_for_portal_pollers`; plus `tests/test_portal_jobs_redaction.py` (`GET /api/v1/jobs` bare list) and `tests/test_portal_jobs_proxy.py`.

**Task 7. Hardware policy without a status publish** — [x]

- Action: Extract the hardware-policy read from `api_status()`. Preview and launch call that helper. Notification publish stays on `GET /api/status` only.
- Mirror: `api_hardware_policy` already returns `status["hardware_policy"]`. The new helper is what both that route and preview should share, with publish remaining in `api_status`.
- Validate: `pytest tests/test_swarm_preview.py tests/test_swarm_launch.py -q`

**Task 8. Partial launch** — [x]

- Action: Submit the five jobs first. If any post fails, cancel the accepted job ids in that `session_id` through the existing Perpetua cancel route. If cancel fails, include those ids as `orphaned_jobs` in the response. Pop the approval token only after every post succeeds. If the batch rolls back, restore the preview so one retry works. A second successful launch still fails.
- Mirror: `consume_launch` remains the single pop. `check_launch` remains the drift and signature check.
- Validate: `pytest tests/test_swarm_launch.py tests/test_swarm_approval.py -q`

**Task 9. Replay allowlist** — [x]

- Action: Add the stable generic replay detail and the malformed job-id detail to `_REPLAY_UPSTREAM_DETAILS` once Phase 1 freezes those exact strings.
- Mirror: The comment that already says the set is lockstep with `_replay_value_error_to_http`.
- Validate: the portal replay proxy tests.

**Task 10. Dead token and `fcntl`** — [x]

- Action: Stop calling `resolved_control_plane_token()` in `_co_orchestration_html_response`. Move `import fcntl` inside the lock `try`, and return a clear unsupported-platform result on `ImportError`.
- Mirror: `_portal_cp_fetch_bootstrap` already ignores its token argument.
- Validate: the co-orchestration and configure-tool tests that already exist. Leave `_pid_on_port` unless a Windows lifecycle test fails.

### Phase 3 — Docstring only (done)

**Task 11.** — [x] In `_models_route_payload`, state that `provider` is a copy of `backend_hint`. Do not rename the key. Do not change `portal_path_is_public`.

---

## 10. Validation

Perpetua-Tools:

```bash
pytest tests/test_fastapi_health.py tests/test_fastapi_supervisor.py tests/test_portal_facade_route.py tests/test_hardware_routing.py -q
```

orama-system:

```bash
pytest tests/test_swarm_launch.py tests/test_swarm_preview.py tests/test_swarm_approval.py tests/test_control_plane_auth.py tests/test_portal_jobs_redaction.py tests/test_portal_jobs_proxy.py -q
```

---

## 11. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Jobs UI expects `prompt` or `metadata` from `/api/v1/jobs` | Medium | Read the poller before redacting. Keep the allowlist fields it renders. |
| `windows` maps onto the wrong GPU id | Medium | Prefer the hardware-policy safe default, then the first matching Windows device id. Exact ids stay exact. |
| Delaying `consume_launch` allows a double submit | Medium | Pop the token once, only after every post succeeds. Keep the existing second-consume test. |
| Lazy health resolution hides a bad Windows deploy | Low | `/health` still fails when `LM_STUDIO_WIN_ENDPOINTS` is missing. Dispatch in `worker_registry.py` stays loud. |
| Allowlist drifts from Perpetua detail strings | Medium | Change the orama set in the same implementation pass as the Perpetua strings, after those strings are frozen. |

---

## 12. Acceptance

- [x] Windows import of `fastapi_app` succeeds with `LM_STUDIO_WIN_ENDPOINTS` unset, and `/health` still reports the gap.
- [x] `preferred_device=windows` changes route order toward a Windows device id. `win-rtx3080` still matches exactly.
- [x] Replay 404 is only the missing-job case. The three public details stay `Job not found`, `Job is not replayable`, and `Job has no queued specification`.
- [x] Submit failures return a fixed 400 detail. The exception text stays in the server log.
- [x] `GET /api/jobs` and `GET /api/v1/jobs` omit prompt and metadata.
- [x] A launch that fails on job 3 does not leave jobs 1 and 2 running without saying so, and one retry of that preview is possible.
- [x] Preview and launch do not publish a status notification.
- [x] The pytest commands in section 10 pass.
- [x] Knowledge, MCP, and A2A remain on the public portal allowlist.

---

## 13. Remediation (2026-10-01, PR #374 / #414)

- **Exclusive swarm claim:** `claim_launch_for_dispatch` holds a process lock, validates
  HMAC, and removes the preview before any PT job posts. `finalize_launch_claim` runs
  only after a full batch success; `release_launch_claim` restores the preview only when
  rollback cancelled every accepted job (no `orphaned_jobs`).
- **Job list timestamps:** `_coerce_job_epoch_seconds` rejects non-finite values; list
  redaction skips rows that still fail projection.
- **CI:** v2 doc MD013 wraps; PT health tests build LAN URLs without committed literals.

## 14. Out of scope until a later yes

- Renaming `provider`.
- Requiring auth on `/api/knowledge/`, `/api/mcp`, or `/api/a2a`.
- Rewriting `_pid_on_port` for Windows.

## 15. CodeRabbit / review remediation workflow (PT memory)

During bot or CI remediation on an **open** lockstep PR (`cursor/portal-facade-hardening-751b`):

1. Fix every file in the sweep **once** locally (no push per file).
2. **Commit in separate logical batches** (one concern per commit).
3. **Push exactly once per repository** after full verification (`pytest` commands in §10; `repo_hygiene` when the diff touches scanned paths).

Not: one commit + one push per repo per fix. See also `2026-09-30-three-day-cycle-pr404-pr408-pr410-pr413-synthesis.md` §D and `CODERABBIT_REMEDIATION_AND_REANCHOR_ARC_2026-08-09.md`.

## 16. Plan closure (2026-10-01)

- Phases 1–3 and §13 remediation are implemented on lockstep branch `cursor/portal-facade-hardening-751b` (orama PR #374, PT PR #414).
- **Canonical plan:** this file only (`Perpetua-Tools/.agent/memory/working/portal-facade-review-and-plan.md`). No orama working-memory mirror.
- Task 6 validation: `tests/test_control_plane_auth.py::test_redact_jobs_list_omits_prompt_and_metadata_for_portal_pollers` plus portal jobs redaction/proxy tests (§9 Task 6).

## 17. Not part of portal facade PR #414

PR-body grant hardening is **Perpetua-Tools PR #415** (`cursor/pr-body-grant-parity-751b`), not the portal-facade branch.
