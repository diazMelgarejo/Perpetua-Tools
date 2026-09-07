# Gate 4 Half A — Full Cycle, 17-Finding Review, and 48-Hour Timeline (2026-09-05 → 2026-09-07)

**Author:** cline-gate4-halfa (Cline/Claude session)
**Status:** memory record — read alongside `references/2026-09-07-gate4-halfa-pr3-independent-review-and-fixes.md` (OpenClaw) for the full findings report.

## What happened in the last 48 hours (timeline)

1. **2026-09-06:** orama-system docs wave — PRs #342 (doc 65 Gate-2 evidence), #343 (doc 66 Gate-4 + dedicated-dialer scope), #344 (onboarding doc), #345 (doc 67 landmark), #346 (doc 65 → main) all merged by claude-main; v2.1 dense-info-layer decision live on main. PT PR #380 (SSRF /health fix) progressed: merged codex ECC-harmonization branches, fixed 3 markdownlint CI failures, closed a real CodeRabbit finding (LM_STUDIO_WIN_ENDPOINTS pool probing — down-first/healthy-second previously reported unhealthy). Still OPEN, human-review gate.
2. **2026-09-06:** oramasys PR #2 (`fix/gate1-telosport-canonical-schema`) — canonical TelosPort (EndpointRef/EndpointUseRequest) replacing the legacy string-based port; claude-main found + fixed a reintroduced double-cancellation claim-cleanup bug (CodeRabbit flagged it independently on oramasys#1), landed as `fca971f` + corrective `c85f3ac` after an honest RED/GREEN detour (first fix over-fit a stricter invariant that broke oramasys#1's accepted test design — lesson: match accepted patterns, don't invent stricter ones).
3. **2026-09-06:** oramasys/telos and oramasys/phylax published as real GitHub repos (previously local-only scaffolds); tests verified before publishing (5/5 telos, 4/4 phylax).
4. **2026-09-07 (this session):** Gate 4 Half A dispatched on the PT coordination board (`gate4-half-a-dialer-and-telos-wiring-20260907`, no PT dependency). cline-gate4-halfa implemented the dedicated model-server dialer + GatewayLifecycle dial-path wiring in oramasys/oramasys (commit `db35f4b`, 16 dialer tests + 3 wiring tests, 40/40), rebased onto `c85f3ac` as `33b539a` in a fresh worktree after claude-main's review request, hit push-credential blocker (HTTPS token invalid + no SSH key).
5. **2026-09-07:** claude-main APPROVED the implementation (verified 40/40 independently), pushed the branch on our behalf via keyring-authenticated gh credential, opened **oramasys/oramasys PR #3** (stacked on PR #2), fixed 3 CodeRabbit findings as `e23e1c1` (telos via git+https, 10s dial deadline `REASON_DIAL_TIMEOUT`, real gateway actor_id at dial-time re-auth). 44/44.
6. **2026-09-07:** cline-gate4-halfa independent fresh-eyes review of `e23e1c1` → **CHANGES-REQUIRED**, 17 consolidated findings published to `references/2026-09-07-gate4-halfa-pr3-independent-review-and-fixes.md` and the board. Majors: F01 Teredo/6to4 misclassified local (6to4-embedded metadata bypass), F02 vacuous `allow_public=endpoint.is_public` opt-in gate, F03 unpinned telos dependency.
7. **2026-09-07:** Codex (`codex-telos-phylax-handoff`) remediated in a fresh worktree (`57a0153` hardening, `295ef51` pin Telos @ `88fba4b`, `3f7bc94` style); claude-main verified all 17 findings against those commits (several fixed *better* than suggested — e.g. F05 used a whitelisted `REASON_TELOS_DECISION_EXPIRED` constant instead of a suffix that would have failed the exact-membership check) and pushed `6cc3f6c` (::1 loopback regression found + fixed + regression test). **59/59 tests green.** cline-gate4-halfa's second independent review of `e23e1c1..6cc3f6c`: **APPROVE-WITH-NITS** — all 10 code findings honestly resolved; residual nit: `chosen: str | None` passed to the `address: str` connector protocol (type-checker only); info: 6to4 relay-anycast `192.88.99.0/24` not in the prohibited set (fold into the F07 fast-follow). F07 remains a documented accepted residual risk (per-purpose port allowlist is the fast-follow; needs real deployment port confirmation — do not hardcode 80/443/8080/11434/1234 without checking actual Ollama/LM Studio configs).

## Final state

- PR #3 `gate4/half-a-rebased-20260907` @ `6cc3f6c`: implementation + all 17 findings addressed, 59/59 tests, awaiting CI + human review. Stacked on PR #2 (reviewable before PR #2 merges; landable only after).
- Half B (PT `agent_launcher.py` adoption of the dialer) stays gated on PT PR #380 merging — human decision, never a same-repo agent edit.
- `model_egress` purpose remains out of Gate 4 scope (paid-dispatch accounting gate first).

## Lessons learned (durable)

1. **CPython `::1` quirk:** `ipaddress.ip_address("::1").is_reserved == True` on 3.13 — a loopback check must precede reserved/prohibited predicates or you reject the most common local target. Missed by three review passes; caught in remediation.
2. **`allow_public` doctrine:** an opt-in flag must never be inferred from the object it gates (`allow_public != endpoint.is_public`). One bit serving two checks is a collapsed gate.
3. **Reason-code whitelists are exact-membership contracts:** suggested `telos_denied:expired` suffixes break them — use dedicated constants (Codex got this right unprompted).
4. **Timezone-ambiguous expiry datetimes fail closed** — naive datetimes are treated as expired, not trusted.
5. **CPython `is_private` is too broad for egress boundaries** (Teredo/6to4/ULA/CGNAT nuances) — enumerate prohibited networks explicitly rather than trusting `is_private` to mean "local".
6. **`255.255.255.255` is `is_reserved=True` on 3.13** — the explicit broadcast check was dead code; removal is safe but pin behavior with a parametrized test.
7. **Test counts must be tied to the exact commit under review** — a 41-vs-44 discrepancy came from running the suite one commit behind the PR tip.
8. **Reviewer output is a claim, not evidence** — every subagent/reviewer finding was re-verified against the actual interpreter and code before publishing; one major claim (0.0.0.0) was wrong and retracted.
9. **Credential handoff pattern works:** push-blocked agent posts to the board; a keyring-authenticated agent pushes on its behalf — no credentials shared, full audit on the board.
10. **Fresh worktree per task from freshly fetched origin refs** (per oramasys-method); base-branch choice must follow docs/v2 invariants over literal instructions (canonical TelosPort > origin/main when main still carries the legacy port).
11. **Pin git dependencies to commit SHAs** — mutable main in a dependency is a live supply-chain channel into CI.
12. **Stacked PRs are reviewable before the base merges** — just not landable.

## Open threads for the next session

- PR #2 + PR #3: CI green, human review pending; after PR #2 merges, PR #3's base can move to main.
- F07 fast-follow: per-purpose port allowlist (needs a real port inventory from actual Ollama/LM Studio deployments first).
- Type nit: `chosen` narrowing in dialer.py (assert or non-optional local).
- 192.88.99.0/24 (6to4 relay anycast) candidate for `_IPV4_PROHIBITED_NETWORKS`.
- Half B once PT PR #380 merges.

## Related memory (consolidated on this hotfix PR branch)

- `.agent/memory/working/GATE4_ENDPOINT_CAPABILITY_HANDOFF_2026-09-07.md` — v2-only F07 transport-capability follow-up (Ollama/LM Studio/gateway/MLX endpoint evidence; implementation local pending review).
- Episodic provenance: be97d89c (proactive-recall record) and 78197e69 (handoff record) — the two unpushed commits this branch was ahead of origin before this consolidation.
- Full findings report: OpenClaw `references/2026-09-07-gate4-halfa-pr3-independent-review-and-fixes.md`.
