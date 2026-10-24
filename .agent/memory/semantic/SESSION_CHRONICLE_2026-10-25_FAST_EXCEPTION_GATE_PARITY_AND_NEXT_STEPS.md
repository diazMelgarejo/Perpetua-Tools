# Session chronicle: fast-mode exception gate, V1 parity and next steps (2026-10-25)

**Author:** claude-opus-5-5 (Claude Code). Additive to
`SESSION_CHRONICLE_2026-10-25_E1C2_CLOSEOUT_HANDOFF_LANES_AND_TAKEOVER.md`, which is not edited.
**Status:** record only; it merges, ratifies and activates nothing. No secrets, keys, tokens,
network addresses, account identifiers, emails or workstation paths. Repositories by public
`owner/repo`, commits by SHA.

## 1. Operator ruling

The P5-approved exception for direct-xAI `fast=True` takes precedence over the unconditional
refusal in orama `be571568`. The ruling assigns the two layers different jobs:

| Layer | Rule |
| --- | --- |
| Policy helpers (PT, orama) | Always refuse `fast=True` for direct-xAI. Metadata (an `EscalationProof`, flag, file, cached value) cannot prove an operator decision. Default `fast=False` stays allowed. |
| Trusted dispatcher (Phylax) | The only place the exception exists: one fresh, one-use P5 receipt, bound to the exact launch, consumed before provider invocation. |

## 2. What was done

| Repo | Change | State |
| --- | --- | --- |
| oramasys/phylax#20 | Review fixes: dispatch key id and seed read from one active-key snapshot (rotation race); two-keyring stale-key test across permit, finalization and event. | Pushed `f72084b` |
| diazMelgarejo/orama-system#438 | Section 5 heading marked complete. | Pushed `818e939` |
| oramasys/phylax (new branch) | `model.launch.fast` action in its own signature domain, limited to direct-xAI at medium effort, created only through the verified human-evidence path; `authorize_direct_xai_fast` rebuilds the intent from the dispatcher's own launch fields and spends the receipt once. Store reload fixed for model-launch actions. Offline tests only. | `e79ab8a` |
| diazMelgarejo/Perpetua-Tools#463 | Codex's F1/F2 fix kept as the base (stricter `is not None` alias rule, explicit `fast: false`); byte-identical parity vectors added; refusal names the dispatch exception. | `e1a4fd83` |
| diazMelgarejo/orama-system (new branch) | Same parity vectors; alias rule and direct-xAI default aligned with PT #463. | `45e59f6`, `08fc4e2` |

Not wired: no production dispatch path calls `authorize_direct_xai_fast` yet; no provider call,
serving, signing activation or pin change happened.

## 3. Corrections Claude made to itself

* A local duplicate F1/F2 branch was built before checking open PRs. PT #463 already covered it;
  the duplicate was dropped and its unique parts (parity vectors, message) moved onto #463.
* A stray `git checkout <sha> -- .` discarded uncommitted Phylax edits; they were restored from a
  backup before committing. Never run a tree-wide checkout to inspect state.

## 4. Next steps (not done yet)

1. **F3/F4 (Oramasys):** two-independent-store SQLite race tests with controlled synchronization
   and no shared mutex (F3); current-status addenda that preserve historical ratification bytes
   (F4). Open in oramasys/oramasys#76 and orama-system#438; review and finish there.
2. **Joint cryptographic evidence:** real positive and negative tests with reciprocal pinned runs:
   wrong issuer with a valid other key, wrong key id, altered digest or body, expired or revoked
   authority, approval-binding substitution, P5 one-use consumption and recovery, replay, no-write
   refusal. No network provider effect.
3. **`model-route.md` refresh (PT issue #462):** ids-only update; PT's copy still names an outdated
   Cursor model id. Policy text is not changed.
4. **orama Part 3 addendum:** contract or receipt addendum covering the fast-mode exception and the
   trusted-composition boundary, if the operator wants it recorded in the Part 3 packet.
5. **`SignedGrantLookup` binding:** bind it to authenticated grant and revocation facts (Phylax
   trusted-composition slice), instead of unauthenticated rows.
6. **Wire the gate:** call `authorize_direct_xai_fast` from the trusted dispatch composition before
   any provider invocation, then exercise the P5-to-dispatch handoff in the disabled or offline
   composition suite.
