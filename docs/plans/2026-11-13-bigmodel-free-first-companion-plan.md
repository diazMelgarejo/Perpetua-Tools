# PLAN: PT companion for BigModel free-first qualification

Date: 2026-11-13
Status: proposed; additive documentation only.
Policy ID: bigmodel-free-first-2026-11-13-v1

## Baselines and canonical plan

- PT PR #497 head: f38634a65188feec55737af95aab4d1a0f0baf55.
- Orama PR #493 head: c8d22852db685d10997d3ede793ad1bf05f0080a.
- Primary plan to apply in Orama: docs/plans/2026-11-13-bigmodel-free-first-plan.md.
- This file is a companion handoff, not a second canonical mutable policy list.
- The source PRs concern discovery lessons and queue documentation, respectively.
- PT #497 targets memory/2026-11-11-cline-session-lessons, not main.
- GitHub reported mergeable_state=dirty; no conflict repair is authorized here.

Do not interpret operator-selected snapshots as independently certified releases.
Do not rebase, push, merge or rewrite either source PR as part of applying a plan.

## Decisions carried from the primary plan

Default free_only mode can end in a safe failure. It never spends to preserve
availability. The proposed coding primary is glm-4.7-flash; other eligible free
candidates are considered only after pricing, activity and task qualification.

The primary plan owns candidate order. Runtime candidates will be owned by a
single proposed PT artifact: config/bigmodel-free-first-policy.json. Do not
manually duplicate its future list in this handoff or independent parsers.

GLM-Z1-Flash's model page says the series is offline, even though a historical
free pricing row remains. Exclude retired models. FlashX names are not free.
Zero-priced input/output is distinct from account eligibility and cache storage,
which the pricing table says is temporarily free.

HTTP 429 with structured code 1113 is billing/resource-entitlement blocked. It
must not trigger generic rate-limit retry, automatic recharge or paid escalation.
An account failure does not demonstrate a model generated successfully.

GLM-5.3-Flash is a separately authorized paid last resort, not the default.
No paid-run budget was supplied with this planning request. Leave it blocked.

## PT ownership and implementation checklist

- [ ] Trace existing provider adapters, orchestration, CLI bridge and budget code.
- [ ] Implement/reuse pure model eligibility, selection and result classification.
- [ ] Keep endpoint reconstruction and hardware checks in canonical PT utilities.
- [ ] Introduce versioned declarative policy, capability evidence and source dates.
- [ ] Bind free status to exact endpoint/model; reject arbitrary endpoint overrides.
- [ ] Expose policy ID/hash to Orama without introducing a PT -> Orama import.
- [ ] Define mirror/consumer parity checks; missing evidence must not count as parity.
- [ ] Carry financial mode and per-candidate outcomes through worker dispatch.
- [ ] Atomically reserve bounded spend before paid requests across concurrent workers.
- [ ] Stop on unresolved executions; avoid duplicate jobs after tool side effects.
- [ ] Test request builders independently from Cline adapters.
- [ ] Append a dated lesson without rewriting historical records.

A proposed shared policy is a design artifact until implemented and tested; do
not claim the config file or API exists merely because it is named here.

## State and safety requirements

A selector must distinguish success, model unavailable, capability ineligible,
request rejection, throttle, billing blocked, credentials blocked, uncertain
execution, safety blocked and recovery required. See primary plan's transition
table. A timeout or ambiguous stream is not clean free-tier exhaustion.

Do not model 'all free exhausted' as 'all models returned something non-200'.
Unknown eligibility blocks qualification; rate limits require bounded waiting;
errors after tool effects require containment. Generic 400 is not universally an
unsupported effort. request_id is not assumed to guarantee idempotency.

Disable separately billed provider tools in free-only mode. Keep local tool
permissions, filesystem restrictions and hardware affinity enforcement intact.
Do not rotate accounts or evade throttling/safety controls through fallback.

The paid gate requires all eligible free candidates resolved, current explicit
per-run authorization, finite positive budget, token/request limits, current
prices and no unaccounted pending reservation. A profile switch cannot implement
this contract alone. A hard monetary ceiling needs suitable provider or gateway
controls; local estimates alone do not guarantee charges.

## Reasoning contract

Never emit max or xhigh. GLM-5.3-Flash requires explicit high, or separately
qualified low. Its documented default is max and medium is not supported.
For older free models, validate documented thinking.type; do not fabricate a
medium/high level or inject unsupported reasoning_effort.
Record uncontrollable effective intensity as unobservable. If the operator's
policy requires a strict internal-intensity bound, block that lane instead of
silently relaxing the rule. Preserve raw reasoning only in-memory as needed for
protocol continuation; do not publish it as evidence.

## Independent evidence lanes

Keep PT direct SDK, direct test client, Cline 3.0.74, ClinePass CLI, any supported
ClinePass gateway, Cline usage billing and BigModel Coding Plan separate.
A W&B/OpenRouter success, a paid subscription or a direct-API success does not
qualify a free BigModel Cline worker. Unsupported lanes remain excluded.

For PT, test generation, harmless tool call, tool-result continuation, isolated
edit/test repair and failure containment. Record endpoint, model, policy and
baseline hashes, transmitted settings, usage, retry history, tools and outcomes.
Do not call zero-cost metadata evidence of a free service.

## Validation and historical preservation

- [ ] Offline fixtures prove paid transport unreachable in free_only mode.
- [ ] Billing code 1113 is tested independently of ordinary HTTP 429 throttling.
- [ ] Retired/unknown-priced/ineligible candidates cannot be promoted.
- [ ] Ambiguous execution and side effects stop blind model/task replay.
- [ ] No default reasoning or extra paid tools bypass financial policy.
- [ ] Concurrent reservation tests prevent double-spending remaining budget.
- [ ] Unknown costs remain unknown; cache-promotion expiry is fail-closed.
- [ ] Policy parity, endpoint/hardware and relevant adapter tests pass.
- [ ] Historical episodic JSONL byte prefix stays unchanged.
- [ ] Append-only preservation gate runs against pinned base and refreshed head.
- [ ] No discovery address is misused as a peer control-plane/TLS address.
- [ ] No secrets, private prompts or reasoning text enter public artifacts.

Do not append to the episodic log until its schema and preservation mechanism
are inspected. This plan patch intentionally leaves that log untouched.

## Application and release

Apply only the PT patch in a PT worktree at the pinned SHA. Verify the Orama
primary plan separately in its own worktree. Do not apply a combined cross-repo
diff from one repository root. Preserve newer local work by content comparison.

Subsequent implementation belongs on dedicated branches. Use tree-content
reanchor rules where repository history has been rewritten. Preserve source PR
scope and do not use this document to ratify queue-fencing gates.

Promotion requires actual relevant test runs, authorized lane evidence, review
and rollback validation. Rollback disables dispatch first; it must not restore
an unavailable or paid model as the default free route.

No runtime code, provider settings, memory log, subscriptions or credentials are
changed by this patch. No paid inference or repository write has been performed.
