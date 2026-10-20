# E1 C2 Claude Five-Day Chronicle (2026-10-16 to 2026-10-20)

**Author:** claude-fable-5, written 2026-10-20 UTC. Additive to the Agnes chronicle, the Cline
addendum and the Codex appendix in this directory; nothing in them is edited.
**Status:** record only. It ratifies, merges, promotes and activates nothing. `ORAMA_GRANT_SERVING`
stayed unset for the whole period.

## 1. Scope and provenance

This is the account of one engagement, in order, with its errors left in. Provenance matters:

* **Direct:** 2026-10-18 to 2026-10-20 is work I did or reviewed in this session.
* **Documentary:** 2026-10-16 and 2026-10-17 are known only from the M1 closeout handoff, merge
  timestamps and the E1 draft's own decision records. They are marked as such.
* Every SHA below was read from the remote or from git, not remembered. Where an agent supplied a
  SHA or a quotation, it was checked against the exact commit before use (lesson `c22a66e94ff1`).

## 2. Timeline

| Day (UTC) | What happened |
| --- | --- |
| 10-16 (documentary) | M1 closeout handoff. Oramasys #46 merged 23:00Z; PT #444 merged 11:40Z. |
| 10-17 (documentary) | Oramasys #45 merged 00:43Z. The E1 draft records operator decisions: a 60 s skew for the provider `NOT_ACCEPTED` window, issuer cascade chosen, and decision 7 (the integrated schema contract is reviewed and pinned before ratification). |
| 10-18 | E1 C2 purpose, version and refusal contract and the permit wire contract authored and reviewed; the rollback-gap and preflight reviews on orama-system. |
| 10-19 | Spec merged (orama-system #423, head `1481bc58`, merge `fe9003a1`, 04:24Z). Slice 1 built in two repositories and independently reviewed. Phylax #13 and Oramasys #65 merged (08:37Z, 08:38Z); PT #450 merged 08:55Z; pin PRs Phylax #14 and Oramasys #66 merged (09:14Z, 09:15Z); PT #451 merged 10:21Z. E1 ratified by the operator at orama-system main `59c623fa`; bounded T3 planning authorized. T3 seam (Oramasys #67) and slice 2 (Phylax #15, Oramasys #68) opened. |
| 10-20 | CodeRabbit findings answered; seven open items converged; Part 3 amendment drafted as docs PRs #425 and #426; Codex remediations; a CI regression on PR 68 found and fixed; shared rules R1 to R6 agreed. |

## 3. What was built

* **Phylax slice 1 (issuer):** a pure wire module with byte-exact vectors, a SQLite permit store
  in one serialization domain, admit, finalize and abort, a hash-chained event stream. Merged as
  `dc35f6ff`.
* **Oramasys slice 1 (consumer):** strict validators, an injected verifier port (no cryptography in
  Oramasys), the six step 4.3 rules in one transaction, fork persistence. Merged as `198273e3`.
* **Interop evidence kept outside both repositories:** a real-signature probe, 7 of 7 scenarios,
  then an abandon and successor check (7 of 7) and a scope-binding check (5 of 5). The permit
  probe was later vendored byte-identical into both repositories with a CI job each, pinned to the
  other side; both pins were moved together after merge (#14, #66).
* **T3 first seam (Oramasys #67):** a proposal record distinct from authorization, a scoped
  single-use reservation consumed in the 4.3 transaction, outcomes limited to `confirmed`, `failed`
  and `unknown` (starting `unknown`), one durable send per attempt, evidence-gated settlement.
* **Slice 2 issuer (Phylax #15):** attested abandon (audit evidence only), successor issuance,
  operator-authenticated abort, abandon and lookup through a required port.
* **Slice 2 consumer (Oramasys #68):** catch-up envelope validation, the 15 s finalization window,
  a circuit breaker, request validators, a durable clock high-water mark with audited recovery, the
  consumer abandon record, a sender precondition and an availability gate.

Method on every change: failing test first, then the fix, then each new guard removed in turn to
prove a test fails (more than 80 mutations; three survivors found, two covered by new tests and
one equivalent).

## 4. Decisions and who made them

* The permit lifetime is 90 s with strict expiry; no new hard dependency for serving; the
  containment numbers (15 s window, breaker at 5 failures, a probe every 15 s, alert after 120 s)
  are starting values (spec decisions 1, 3 and 8).
* **E1 was ratified by the operator at `59c623fa`, stated directly in the session.** A board row
  labelled as the operator had said the same earlier; it was treated as a relayed claim and the
  operator was asked (lesson `03f368db3c16`). The same happened once more for the section 14
  precondition and the two docs PRs (row 5249): confirmed directly before the hold was lifted.
* Merge, pin promotion and serving activation were never taken by an agent.

## 5. Errors and corrections, mine included

| Error | Where found | Correction |
| --- | --- | --- |
| A peer's reviews cited lines that did not exist | proof rule (`wc -l`, `grep -n`) | reviews retracted; rule adopted |
| A stale branch conflicted with main | trial merge | withdrawn, not opened as a PR |
| A queue task used a free-text dependency and was unclaimable | queue state | replacement task enqueued |
| My attestation text embedded attempt state, so a retry could be refused | Codex review | retries compare identity fields |
| My abandon outcome check matched ids only | Codex review | injected authenticator, fail closed |
| My clock recovery took a name only and could revive an expired reservation | reading the approved clock policy | audited recovery, anti-revival |
| A reservation was tied to a permit by id only | automated review, test first | scope bound to the permit's digests |
| A peer's test added a skip to every oracle cell | CI log, six cells failed | defined only when available |
| My first fix for that moved a file into a gated directory | packet tests before pushing | reverted, nothing pushed |
| I called a stacked-PR history change suspicious | operator, then committer and patch-id | it was the host's rebase |
| I approved a design without naming the section 14 precondition | rereading the draft | operator confirmed it directly |

## 6. Pull request ledger at the time of writing

| PR | State |
| --- | --- |
| Phylax #13, #14 | merged |
| Oramasys #65, #66 | merged |
| PT #450, #451 | merged |
| orama-system #423 | merged |
| Phylax #15 (issuer slice 2) | open, clean |
| Oramasys #67 (T3 seam) | open, clean |
| Oramasys #68 (consumer slice 2) | open, all 16 checks passing at `79cb8369` |
| orama-system #425 (status addendum), #426 (Part 3) | open, not ratified |

Merge order for the open three is 67, then 68 retargeted to main, then 15.

## 7. The seven open items, as converged

Events carry only the minimal delta; a checkpoint is a retained signed event with a consumer floor;
grant v2 is the 19 fields already in Part 1; `effect_class` stays a default-deny registry; operator
authentication reuses the existing trusted-human path; the step ledger performs the reservation
release; the clock skew stays zero. Event body shapes, the checkpoint rule and witness fields wait
on the Part 3 review and the operator's exact-commit pin.

## 8. Lessons added with this chronicle

* `4b14722a0c6f`: a published row separates local from CI and says "CI pending".
* `f20949b625c6`: read the validator before touching a capability-gated directory.
* `5172a6a9a9a9`: stacked-PR rebases change SHAs, not patches; pin evidence to the remote head.
* `de9f7b729355`: verify a bot finding against the spec glossary before applying it.
* `da4ea4ecfb16`: bind a reservation to its permit by content as well as by id.
* `fd1652d91c55`: an unsafe-compatible default flag needs a structural guard.
* `287e5917e666`: audited clock recovery that cannot revive expired authority.
* `c22a66e94ff1`: verify every agent quotation against the exact commit.
* `8a491abf7644`: reuse an existing signed record before designing a new signed object.

Shared rules R1 to R6 were agreed by Claude and Agnes (row 5314); Codex had not yet replied agree or
amend. R1 is Agnes's lesson `5bfa7d518bcc`; R2 to R4 are encoded above; R5 and R6 sit inside
`5172a6a9a9a9`.

## 9. State at writing

Held locally in the canonical PT memory worktree, on top of Agnes, Cline and Codex; not pushed.
Serving unset; merges, pin promotion and ratification remain the operator's.
