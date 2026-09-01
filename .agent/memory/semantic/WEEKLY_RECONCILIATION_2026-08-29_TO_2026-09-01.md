# Weekly reconciliation — 2026-08-29 through 2026-09-01

This record captures one continuous work thread across the period: the
Claude-Desktop-LLM canonical modernization and its downstream ripples into
`oramasys/oramasys`, `orama-system`'s CIDF sub-skill, and a new `oramasys/alexandria`
placeholder repo. It is an append-only semantic summary, not a replacement for the
individual lessons, PR histories, or rendered `LESSONS.md`.

## 1. Claude-Desktop-LLM: canonical TypeScript modernization → v2.2.1

`diazMelgarejo/Claude-Desktop-LLM` was rewritten from a duplicated
`mcp-server/` + per-extension-copy layout into one canonical `src/` TypeScript
tree (strangler pattern): single provider contract, tool registry, endpoint
policy, effect policy, and storage layer, with the `.mcpb` extensions and the
combined CLI server as thin build products of that one tree.

Security hardening across several review rounds: connection-time IP pinning
against DNS-rebinding, HTTPS required for any allowlisted non-loopback
provider endpoint, `AbortSignal` propagated through endpoint validation,
path-traversal-safe storage naming, effect-class tool gating, a public-error
whitelist so internal URLs/paths never leak to the MCP client, DNS-resolved-
loopback rejection (an attacker-controlled domain pointing DNS at 127.0.0.1
must never earn loopback trust), and IPv6-bracket/canonical-form handling.

**Critical bug found and fixed post-release:** `pinnedDispatcher`'s custom
undici `connect.lookup` only implemented the bare `(err, address, family)`
callback form. Node 22's `net.Socket.connect` requests Happy-Eyeballs-style
lookups (`options.all === true`) for any **hostname** target — IP-literal
targets never invoke `connect.lookup` at all. This meant every real request
against the documented default (`OLLAMA_URL=http://localhost:11434`, a
hostname) failed with a generic "fetch failed", while all 64 unit tests
stayed green because every test used a `127.0.0.1` IP literal. Only surfaced
by manually driving the compiled server over real stdio against a live local
Ollama instance — see [[lesson_d74d82b3b257]] and the CLAUDE.md-adjacent
takeaway that policy/security code intercepting DNS/connections needs at
least one hostname-target integration test, not just IP-literal unit tests.

**Repo promotion:** `oramasys/Claude-Desktop-LLM` (a GitHub fork) is now the
established, released canonical home going forward. `diazMelgarejo/Claude-Desktop-LLM`
and its open PR #1 are superseded and intentionally left untouched — the
promotion pattern was fast-forwarding the fork's `main` directly to the
finished commit, not merging a PR into the stale personal-repo `main`.

**Release history:** `v2.2.0` was published, then found broken by the
Happy-Eyeballs bug above and deleted (tag + release) same-day; `v2.2.1`
(HOTFIX) supersedes it with the fix, the corrected default models
(`qwen3.5:9b-mlx` for Ollama, `qwen3.5-9b-mlx` for LM Studio — the
Apple-Silicon-native MLX build, not the NVIDIA-native `nvfp4` tag which has
no Apple acceleration path), and a 190s default `TIMEOUT` (up from 120s,
since `qwen3.5` is a thinking-capable model whose hidden reasoning trace can
push wall-clock time past the old default on real prompts).
Current: <https://github.com/oramasys/Claude-Desktop-LLM/releases/tag/v2.2.1>

**Live verification, not just unit tests:** ran the actual compiled server
over real stdio against live Ollama and LM Studio instances — `local_llm_query`,
`check_llm_status`, `save_conversation`/`load_conversation`,
`save_prompt_template`/`load_prompt_template`, `list_local_models` all
confirmed working against both providers individually.

**Retracted, then correctly closed: Ollama + LM Studio concurrency.** An
early "both providers work fine concurrently" claim was vacuous — it was
based only on `check_llm_status`'s lightweight `healthCheck()`, which proves
an HTTP server is reachable, not that a model is actually resident in
memory at that instant. The user then stated plainly, from direct incident
history, that this question is **closed, not open**: a prior agent session
ran both engines under real concurrent heavy inference load on this M2 Pro
Mac and caused an overheat + force shutdown, with no replacement hardware
available. This is now a standing INVARIANT in the top-level `CLAUDE.md`
(search `lesson_f60e9a3a7ade`) — never design, propose, or run any test that
would load both engines' models and drive concurrent generation, however
small it looks.

## 2. `orama-system` PR #338 — CIDF core/skill sync

PR #338 synchronized CIDF's executable v1.3 contract (Python core, TS core,
policy JSON, linters, tests) with `bin/orama-system/cidf/SKILL.md`.
CodeRabbit's review flagged several of the findings below; independent
verification against actual runtime behavior surfaced at least one more
same-class bug CodeRabbit's review did not catch (see below) — each finding
was checked against real code before fixing, not applied blind, regardless
of which review process first surfaced it:

- `execution_tools.py`'s `cidf_insert()` silently dropped
  `estimated_setup_seconds`/`estimated_run_seconds` from `task_meta` and
  reported a stale `cidf_version: "1.2"` — both fixed.
- **Real bug:** the TS core's `automationJustified()` checked
  `!== undefined` on timing fields, but the JSON policy's own convention
  represents "unknown" as `null` — `null !== undefined` is `true` in JS, so
  a `null` run-estimate slipped past the guard and got coerced to `0` in the
  `>` comparison, closing the automation gate on a false "run is instant"
  assumption. Fixed by typing the fields `number | null` and checking
  `!= null`.
- **Real bug, both cores:** `execute_with_fallback`/`executeWithFallback`
  validated the blocked-decision branch *before* checking the signature was
  non-empty, so an empty signature was silently accepted whenever no method
  was eligible — exactly the path most likely to reach production
  unnoticed. Fixed by validating signature first in both languages.
- FRAMEWORK.md's CLOSED-gate description was missing the "for initial
  selection" qualifier the JSON policy already had, reading as "scripting is
  blocked whenever any simpler method is eligible" when the real behavior is
  that scripting stays in the fallback chain, just never the initial pick.
- SKILL.md had 4 stale v1.2 references and a stale "30 passed" test count
  (actual: 34, confirmed via `pytest --collect-only`).
- **Same-class bug CodeRabbit missed:** the TS conformance test's
  `makeEnv({ field_accessible: true })` fixture also silently enabled
  `direct_typing`/`clipboard_paste` (no executors registered for either),
  producing extra `no_executor_registered` attempts the assertion didn't
  expect. The *identical* bug existed in the Python suite's equivalent test
  — confirmed red via a real pytest run, not assumed — and was fixed the
  same way in both languages.

Also discovered and resolved in-flight: this SKILL.md file had never
satisfied the repo's own OSSF-1 pre-commit gate (missing `## Purpose`/`##
When to Use` and `## Boundaries` with `Always Do`/`Ask First`/`Never Do`
subsections) — a pre-existing gap unrelated to the sync work, but blocking
on any further commit to the file. Added real, grounded content (not
filler) rather than bypassing the hook.

Result: 37/37 pytest passing (was 34), 35/35 jest passing (verified via a
scratch ts-jest harness since this environment has no local tsc/jest
install). Pushed to `codex/sync-cidf-core-v1-3`; PR #338 is `MERGEABLE`/
`CLEAN`, not yet merged as of this record.

## 3. `oramasys/oramasys` PR #1 — Gateway Lifecycle review

Reviewed the new owner-separated Gateway Lifecycle capability (Telos/
Phylax/Agate/Claude-Desktop-LLM as injected ports, idempotent routing-state
store, immutable Pydantic contracts with strict semver/commit-SHA and
SHA-256 digest validation). CodeRabbit's 3 findings were verified against
the actual code:

- **Confirmed real, Major:** `GatewayLifecycle.run()` is not actually
  cancellation-safe during claim acquisition, despite the PR listing
  "cancellation-safe claim release" as an already-solved safety property.
  If `await self._store.claim(key)` is cancelled after the store internally
  reserves the key but before the await returns, the local `claimed` flag
  is still `False` (it's only set `True` on the next line), so the
  `CancelledError` handler's `if claimed` guard skips releasing the
  reservation — the key leaks permanently and every later identical request
  blocks forever waiting on a completion that will never arrive.
  Recommendation: do not merge until fixed or explicitly accepted as a
  known limitation.
- Two Minor doc-wording findings confirmed real but non-blocking (README
  overstates what `OperatorConsent`'s fields actually gate vs. what the
  design doc's authoritative digest/provenance owner — Phylax — actually
  checks; idempotency wording says replay has "no side effects" when
  progress events still fire on replay, only owner calls are skipped).

Not fixed in this pass — this was a review request, not a fix request; the
findings are reported for the PR author/reviewer to act on.

## 4. `oramasys/alexandria` — created, deliberately inactive

Per explicit user direction: created `oramasys/alexandria` (public,
MIT-licensed, matching every other `oramasys/*` repo's convention) as the
future central documentation hub for the org, per the orphaned ADR at
`orama-system/docs/v2/41-alexandria-repository.md` (committed there but
never acted on — confirmed the repo didn't exist before this). Scoped
narrowly per explicit instruction: README only, describing the destined
purpose and governance model — **no content migration**.
`orama-system/docs/v2/` remains the canonical, actively-maintained
specification tree; a full migration is explicitly not scheduled.

## Retrieval cues

Use this memory for queries involving:

- Claude-Desktop-LLM v2.2.1 / canonical repo migration / Happy-Eyeballs bug
- CIDF v1.3 core sync / PR #338
- oramasys/oramasys Gateway Lifecycle / PR #1 / cancellation safety
- oramasys/alexandria / docs-hub scaffolding
- Ollama + LM Studio concurrent-load INVARIANT (closed, not open)
