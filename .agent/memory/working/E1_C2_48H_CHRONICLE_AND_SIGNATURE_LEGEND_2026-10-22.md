# E1 C2: 48-hour chronicle and the two Ed25519 versions (2026-10-20 to 2026-10-22)

Author: claude-fable-5 (identity not independently verified). Record only; it merges, ratifies, promotes
and activates nothing. `ORAMA_GRANT_SERVING` stays unset. Repositories: Phylax (issuer), Oramasys (consumer),
orama-system (docs and governance), Perpetua-Tools (this repository).

## Legend: the two signature versions

| | Pure Ed25519 (RFC 8032 PureEdDSA) | Ed25519ph (RFC 8032 HashEdDSA, SHA-512 prehash) |
| --- | --- | --- |
| What is signed | the message bytes directly | the SHA-512 prehash of the message, via `crypto_sign_ed25519ph_*` |
| Role here | **test stand-in only**; generic wording in the Part 3 text ("detached Ed25519 signature") | **the recorded and implemented production scheme** for grants, permits, finalizations and events |
| Message framing | stand-in signed domain + digest text with plain Ed25519 | domain bytes followed by the body; for events, the domain then the 64 ASCII hex characters of the event digest |
| Domains | none fixed | adjustment grant `phylax-adjustment-grant-v1\x00`; permit `phylax-dispatch-permit-v1\x00`; finalization `phylax-dispatch-finalization-v1\x00`; event `phylax-issuer-event-v1\x00` |
| Signature wire form | n/a | base64url without padding, 86 characters |
| Interchangeable? | **No.** A pure Ed25519 signature over the same bytes is rejected by an Ed25519ph verifier, and the reverse | |

`phylax-dispatch-grant-v2` does not exist. Do not cite it.

### Where each version lives (commit by commit)

| Version | Repository and commit | What it holds |
| --- | --- | --- |
| Ed25519ph | Phylax `1318cb3` (2026-10-12) | `adjustment_grant.py`: first Ed25519ph issuer with the grant domain |
| Ed25519ph | Phylax `1f59362` (2026-10-19) | `dispatch_wire.py` sign/verify for permit, finalization and event; `docs/e1-c2-permit-contract-freeze.md` FREEZE-CHOICE 4 and 5; byte-exact vectors `docs/vectors/dispatch-permit-v1.json` |
| Ed25519ph | Oramasys `28c0cb7` | consumer wire validators and the vendored vectors (main now `7369934`) |
| Ed25519ph | Oramasys PR 72, `05e818b` | test-only `SignatureVerifier` adapter verifying Phylax-signed events; 512 flipped signature bits, 64 changed digest characters, wrong key, wrong or missing domain and pure Ed25519 all fail; `bootstrap_anchor` accepts a real signed anchor and refuses a tampered one |
| Ed25519ph | live check, not committed | Phylax `sign_event` produced 8 fresh events; the adapter verified all 8; 320 flipped-signature cases were rejected by both Phylax `verify_event` and the adapter |
| Pure Ed25519 | orama-system `6459b30e` | Part 3 text wording "detached Ed25519 signature" (scheme left to the injected verifier) |
| Pure Ed25519 | orama-system PR 434, `e99750ea` then `c19857c8` | the 31-test reference-model suite signs with plain Ed25519; relabeled as a stand-in in `c19857c8` |

Still missing for production: an `IssuerSigner` wrapper with key custody on the Phylax side, a production
Oramasys-side verifier adapter (Oramasys source imports no `nacl` by design), and a `TrustedIssuerKeys`
adapter.

## Chronicle of the last 48 hours

| Area | Result | Evidence |
| --- | --- | --- |
| Slice-2 runtime closeout | R5 consumer clock recheck and R6 issuer abort grant-binding merged by the operator | Oramasys PR 71 to `7369934`; Phylax PR 17 to `6ee39ee`; probe parity R7, `c2_slice2_probe.py` sha256 `682129b1d1f359fa04548c75f2bb362f93648e5673bddb96390453d3b4d8d878` |
| Part 3 documentation | R8, R9 and hardening merged | orama-system PR 432, head `6459b30e` |
| Part 3 section 3.3 | ratified by the operator for section 3.3 only (contract and specification decision) | packet record `571863ee`; amendment sha256 `984065ab236f7bd9178049de312d54c501b2a393eccb229b6d8f42360b3143f4`; no implementation, serving or pin promotion authorized |
| Packet items 3 and 5 | 31-test reference-model suite; agy verdict APPROVE_WITH_CHANGES at `6459b30e` | orama-system PR 434 (stacked on 433) |
| Implementation of 3.3 | draft, consumer-local: `bootstrap_anchor`, checkpoint-aware `acked_through`, floor gate, quarantine, audited clear | Oramasys PR 72, `a920faa`; 24 real-store tests |
| Governance R1 to R4 | final synthesis published on both PR heads; main merged into PR 422 with hooks on | orama-system `76dd8c8f` on PR 381; Perpetua-Tools `b5f7796a` then `3799e225` on PR 422 |
| Gate debt on main | OSSF-1 fix and `swarm.test.ts` on orama-system PR 433 (`c12616a1`, `95962397`); memory-record allow-list merged (`9be8b73f`) | PR 433 open; PT PR 459 merged |
| Dependabot | critical `certifi` and the high alert addressed on existing PRs | PT PR 427 `103c0647`; PT PR 457 `d21384cc`; alerts clear when the operator merges them |
| Serving prerequisites | 15-item audit: 12 confirmed open, 2 refined, 1 corrected, none closed | `references/2026-10-22-serving-prerequisites-audit.md` sha256 `65bb53e72a123ebca45eb43cea3459320eee54176aab802e73e81d31666f2e6d` |
| Board tooling | the board snapshot JSON now refreshes on every logged note | PT PR 459, `15cf3595` |

## Still waiting on the operator

Merge orama-system PR 433, then main into PR 381; merge Oramasys PR 72 after review; merge PT PR 427 and 457;
any pin promotion or serving (not appropriate while the serving prerequisites stay open).
