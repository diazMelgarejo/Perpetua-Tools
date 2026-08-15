# Tier-5 ASGI branch code review + branch-sprawl reconciliation — closing record

**Date:** 2026-08-15
**Branch reviewed:** `feat/tier5-asgi-harmonized-20260811` (commits `248f7e4a`, `0473fe25`,
handoff commit `20147a37`), worked in a disposable worktree.
**Outcome:** review complete, reconciliation plan approved, then this exact
worktree was found to be superseded by `rebase/tier5-asgi-harmonized-20260814`
(same lineage, rebased 2026-08-14, with additional commits and a queued
durable-budget-ledger plan). Work continues there. This doc is the closing
record for everything done against the pre-rebase copy so none of it is lost.

## 1. Code review findings (against plan doc §C.3/C.5/C.6/C.7)

**Verified strengths** (do not re-litigate these — confirmed correct):
- Dependency alignment to FastAPI 0.141.1 / Starlette 1.6.0 genuinely landed.
- ASGI middleware rewrite (`BaseHTTPMiddleware` → pure ASGI
  `ControlPlaneAuthMiddleware`) is architecturally correct, including the
  subtle "register auth before CORS so CORS stays outermost" Starlette
  ordering claim.
- C.1 canonical chokepoint preserved: `frugality_router.py`/`gate.py`
  untouched; `tiered_pipeline.py` correctly defers to the pre-existing
  `gate_permits()`.
- C.4 flag/secret contract fully correct: flag-off blocks before dispatch,
  key presence doesn't auto-enable, missing key raises a controlled error.
- Host allowlisting in `model_transport.py::_endpoint` is careful anti-SSRF
  work (scheme/host/port/path validation, rejects embedded credentials).
- Provenance-gating (`_require_verified_provenance`) genuinely implemented;
  `config/models.yml` carries real provenance records with source URLs and
  `verified_on` dates.
- Two renames (`claude-4-5-thinking`→`claude-sonnet-5`,
  `grok-4-1-thinking`→`grok-4.5`) verified fully consistent — zero stale
  references anywhere in the repo, despite a removed comment that had
  explicitly warned "do NOT rename."
- Test-count claims verified by actually running them: 33/33 Tier-5 suite
  exact match to the handoff's claim.
- Full local suite: 1709 passed / 2 failed, both failures confirmed
  unrelated to this diff (missing optional `cryptography` package;
  uncommitted unrelated `.agent`/`.codex`/`vendor/ecc-tools` drift + a real
  but pre-existing "unclassified email literal" hygiene finding in
  `AGENT_LEARNINGS.jsonl` — explicitly out of scope per the handoff's own
  "do not include unrelated local changes" instruction).

**Critical finding:** no human-approval boundary before paid Tier-5 dispatch.
Plan §C.6 requires binding an approval record (trace_id, human identity,
purpose, recipe, route tier, max tokens, max cost, expiry, scope) validated
before stage one; §C.5 bans "self-approve a paid action." Neither
`TieredPipelineRunner.run()`'s signature nor `TieredPipelineRequest` carried
any approval concept. Grep-confirmed zero hits for
`approval|expiry|trace_id|human_identity|revoked` anywhere in the
implementation or tests.

**Important finding #1:** config validation gaps — `_load_and_validate`
doesn't reject unknown YAML keys (silently ignores anything not explicitly
`.get()`'d) and doesn't enforce the "more than three stages" cap from §C.3.

**Important finding #2:** telemetry gaps — `_emit_trace`'s payload omits
`trace_id` (no run-scoped correlation) and `error_class` on the failure
branch, both explicitly required by §C.5.

Full report delivered inline in conversation; see this doc's §3 for how each
finding maps into the reconciliation plan that superseded a from-scratch fix.

## 2. Branch-sprawl discovery

This exact P4 deliverable turned out to have been independently implemented
at least **five times** across different branches:

| Branch | tiered_pipeline.py | Model resolution | Dispatch | Approval | Notes |
|---|---|---|---|---|---|
| `feat/v1-p4-tier5-pipeline-and-recovery-memory` (singular), `609d0b43` | 297 | `env: PIPELINE_FAST_MODEL` indirection, unvalidated | Hardcoded OpenRouter, raw `aiohttp`, no host allowlist | None | User's original "why hardcode?" question pointed here |
| `feat/v1-p4-tier5-pipelines-and-recovery-memory` (plural), PT PR #350 (OPEN, unmerged, `CLEAN`/`MERGEABLE`) | 272 | Reverted to literal `fast: glm-5.2`, validated against `config/models.yml` `frugality_tier: 5` | Injected dispatcher | None | Successor to the row above — reversion is documented, not accidental (see §4) |
| `feat/p4-governed-tier5-pipelines` | 172 | — | — | — | Smallest/earliest, not deeply explored |
| `feat/v1-tier5-pipelines` | 521 | `provider: openrouter` + `model: <slug>` pairs | OpenRouter-only, `httpx`, bounded retry, **real cumulative cost/token tracking from OpenRouter's own `usage` field** | **Full `PipelineApproval` + `_validate_approval()`**, CLI-driven, local-JSON-file artifact (not inline HTTP fields) | Most mature approval/budget/validation layer of all five; 224 lines of tests; no ASGI/endpoint/host-allowlisting work |
| `feat/tier5-asgi-harmonized-20260811` (the branch under review) | 347 | Literal aliases, registry-validated | Multi-provider `ProviderTransportRegistry`: allowlisting, provenance-gating, bounded retries, redacted failures | None (the Critical finding) | Most mature transport/security layer; only branch with the real FastAPI endpoint + ASGI auth |

Two of the five (`feat/v1-tier5-pipelines` and the branch under review) are
genuinely **complementary, not duplicative** — one has the mature
approval/budget layer, the other has the mature transport/security layer.

## 3. Reconciliation plan (approved by user, then superseded by the worktree switch — plan content still valid, just needs re-targeting)

Full plan file: this session's plan-mode output (locally at
`~/.claude/plans/nifty-rolling-lovelace.md` on the operator's machine, not
committed to any repo). Summary of resolved decisions, all still applicable
to whatever branch this work continues on:

1. **Approval boundary** — port `feat/v1-tier5-pipelines`'s `PipelineApproval`
   dataclass + `_validate_approval()` checks, adapted to the current branch's
   exception hierarchy (subclass `PipelineError` directly, NOT
   `PipelinePolicyError` — the endpoint's except-chain is type-ordered and a
   subclass would be silently swallowed by the existing policy-denied
   handler).
2. **Approval delivery mechanism — resolved via explicit security tradeoff
   analysis, not just picked:** single mechanism only, artifact-based,
   non-optional at the API layer. Rejected "support both inline and artifact
   modes" as a downgrade-attack shape (same class of problem as
   negotiable-weak-fallback in TLS) — if a caller can choose either mode, the
   system's real guarantee is defined by whichever mode is weaker, since any
   misbehaving/automated caller simply takes the easy path. Chosen design: a
   separate "register approval" step writes a local JSON artifact
   (`.state/pipeline_approvals/<trace_id>.json`, path pattern mirrors the
   existing `PT_PIPELINE_TRACE_PATH` env-var convention); the execution
   endpoint accepts only `trace_id`, never inline approval fields; a
   convenience wrapper script may do both steps in one shell invocation for
   interactive operators, but that convenience lives in tooling around the
   HTTP contract, never as an alternate code path inside it.
3. **Config validation gaps** — port `feat/v1-tier5-pipelines`'s
   `_reject_unknown()`/`_require_keys()` pair (stricter than what was
   originally planned — requires key presence too, not just rejects
   unknowns), applied at root/limits/model/stage levels using the CURRENT
   branch's actual top-level keys (`version`, `models`, `recipes` — a
   Plan-agent pressure-test caught that omitting `version` from the allowlist
   would break every existing test on day one).
4. **Telemetry gaps** — merge both branches' approaches: keep the current
   branch's failure-path tracing discipline (which `v1-tier5-pipelines`
   lacks entirely — it never traces a failed stage), add
   `v1-tier5-pipelines`'s `trace_id` + real cumulative
   `total_tokens`/`cost_usd` counters (current branch only has the
   *configured ceiling*, not actual usage), add `error_class` as a stable
   schema field present on every trace line (neither branch has this).
5. **OpenRouter** — port `v1-tier5-pipelines`'s already-written, already-
   tested `_openrouter_execute` dispatcher into
   `model_transport.py::ProviderTransportRegistry.dispatch()` as a new
   backend branch, rather than write one from scratch. Reuse `_openai_payload`/
   `_openai_text` where the response shape matches (verified via EXA research
   this session: OpenRouter is `Authorization: Bearer`, OpenAI-Chat-
   Completions-shaped).
6. **Model resolution — the user's original question, answered with
   evidence, not just judgment:** neither pure hardcoding nor pure env-var
   indirection alone is right. Read the plural branch's own committed memory
   doc (`.agent/memory/working/2026-08-10-p4-tier5-pipeline-closure.md`,
   still present on that branch) for the documented rationale behind its
   reversion away from env-var indirection: "PT already has a canonical
   frugality gate and current paid models in `config/models.yml`... [the
   runner] validates configured aliases against current model-registry
   names; requires every configured model to be `frugality_tier: 5`." A raw
   `env: PIPELINE_FAST_MODEL` value is an arbitrary string with no tie to
   that classification — it would let an operator silently route paid Tier-5
   dispatch to a never-vetted model. This was tried and reverted for that
   documented reason, in this exact codebase — not an oversight, not
   "hardcoding for its own sake." Resolution: hybrid — keep the registry
   validation as the floor (every resolved model must still be
   `frugality_tier: 5`), but allow an env var to override *which* registered
   alias substitutes for `fast`/`strong`, restoring the operational
   flexibility that motivated the original design without reopening the
   registry-bypass gap that motivated reverting it.
7. **Provider catalog** — catalog-only entries (`model_provenance`, no
   execution code) for Gemini, Cohere, Bedrock, Azure OpenAI; real adapters
   (config entry + `model_transport.py` dispatch branch, reusing OpenAI-shape
   helpers) for Mistral, DeepSeek, Groq, DashScope, Meta Llama API. All 8 new
   providers' base URLs/auth patterns/representative model IDs verified via
   EXA this session, not guessed.

## 4. Governance finding: PT PR #350 conflict (still open, not yet resolved)

PT PR #350 (`feat/v1-p4-tier5-pipelines-and-recovery-memory`, the plural
branch — NOT the singular branch a coordination-board memory doc had
incorrectly claimed) is `state: OPEN`, `mergedAt: null`,
`mergeStateStatus: CLEAN`, `mergeable: MERGEABLE` against `main`, last
updated 2026-08-10. It touches exactly `config/pipelines.yml` and
`orchestrator/tiered_pipeline.py` — the same two files this reconciliation
plan rewrites. If PR #350 merges before this branch's eventual PR opens, that
PR will conflict on both files immediately. Recommendation (not yet acted
on, needs explicit user sign-off before closing someone's open PR): close PR
#350 with a comment pointing at whichever PR eventually comes from the
reconciled branch, since its content (registry-validated literal-alias
resolution, shallower unknown-key rejection) is fully subsumed once
`feat/v1-tier5-pipelines`'s stricter validation is ported in.

Separately: `.agent/memory/working/TIER5_PIPELINE_AND_APPRENTICE_STACKS_2026-08-15.md`
(main PT checkout, authored by agent `antigravity`, referenced from a
COMPLETED GossipBus board entry) contains two factual errors worth a
correction pass later — it names the wrong branch (singular instead of
plural) for PR #350, and claims that PR is a "Canonical merged baseline" when
it is in fact open and unmerged. Verified directly against `gh pr view`
rather than trusted as-is, per this session's own "verify before replaying
past agent work" doctrine.

## 5. Why this worktree was abandoned mid-implementation

Immediately before starting the code changes (Task #39 in this session's
tracked task list — "Port `PipelineApproval` + validation"), a routine
`git status` check surfaced pre-existing local drift including an
**uncommitted** `docs/superpowers/plans/2026-08-14-tier5-durable-budget-ledger.md`.
Investigating it (rather than ignoring it as unrelated noise) found:

- The doc describes a materially more rigorous solution to exactly this
  review's cost/telemetry findings — a SQLite-backed, idempotency-key,
  HMAC-fingerprinted atomic budget ledger, touching the same files this
  reconciliation plan touches.
- It **was** committed, but on a different commit (`e546f1dc`) that is
  **not an ancestor** of `feat/tier5-asgi-harmonized-20260811`'s HEAD — i.e.
  it lives on a separate, newer lineage, not on the branch this review had
  been checked out against.
- That lineage is `rebase/tier5-asgi-harmonized-20260814`, a rebase of the
  exact branch under review, checked out in a separate worktree at
  `/private/tmp/pt-tier5-rebase-20260814`, with 6 additional commits
  including ones that explicitly reference "Tier-5 review handoff" and
  "sanitize Tier-5 review provenance" (this review's own output, already
  being incorporated) and a current, authoritative status doc
  (`docs/next/2026-08-14-operational-work-disposition.md`) that lists
  "Tier-5 publication closure" as item #1, explicitly **BLOCKED**, exit gate:
  "Reserve budget atomically before provider dispatch, account conservatively
  for partial-stage failure, close the recorded review findings, and pass
  focused transport, auth, and cost tests."

In short: the worktree this review and reconciliation plan were built against
had already been superseded by a newer rebase with more work layered on top,
sitting in a sibling worktree the whole time. Flagged to the user rather than
continuing on the stale copy; confirmed correct; work continues at
`/private/tmp/pt-tier5-rebase-20260814` on `rebase/tier5-asgi-harmonized-20260814`,
reconciling this plan with the durable-budget-ledger plan already queued
there.

## Gold-nugget lesson

Before starting implementation on a reviewed branch, check for local
uncommitted drift and sibling worktrees on rebased/superseding lineages of
the *same* branch — not just for merge conflicts on `main`, but for the
possibility that the exact branch just reviewed has already moved on without
the review session's knowledge. A `git status` full of "unrelated" drift is
worth a few seconds of triage before being dismissed as noise; one of the
"unrelated" files here was the single most important piece of context in
the whole session.
