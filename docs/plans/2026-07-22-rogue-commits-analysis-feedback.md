# Rogue Commits Analysis — Identity CI Feedback

Date: 2026-07-22
Repository: `diazMelgarejo/Perpetua-Tools`
Canonical reset point: `288a27c032355d5d6d373b3e51b43897f2aa995b`

## Correction to the earlier analysis

The earlier identity remediation did not fix CI because it corrected the wrong execution paths.

The shell gates were updated to recognize an exact private-owner SHA-256 fingerprint:

- `scripts/git/check_identity.sh`
- `scripts/git/audit_attribution.sh`
- `scripts/git/banned_attribution_lib.sh`

However, the failing CI gate was `scripts/review/repo_hygiene.py::check_identity()`. That Python function remained unchanged. It still accepted only:

1. literal tuples in `APPROVED_IDENTITIES`; or
2. a private owner address loaded from `.verboten-literals.local`.

The CI checkout had the configured identity `cyre <private-owner-address>`, but the address was neither a public approved tuple nor available through the intentionally untracked local file. The shell fixes therefore could not affect the Python failure.

## Correct invariant

CI authorization must be deterministic and must not depend on operator-local files.

The corrected implementation uses one tracked registry:

```text
.github/authorized-private-identities.sha256
```

It stores only SHA-256 digests of canonical lower-case identity strings:

```text
<author name> <<author email>>
```

The registry is consumed by all three identity paths:

- Python repo hygiene;
- shell local identity guard;
- shell commit-author audit.

`.verboten-literals.local` remains an additive operator-only authorization source. It is no longer a CI prerequisite.

## Regression requirement

The regression test explicitly verifies both conditions with no private literals file present:

- a registered fingerprint is accepted;
- an unregistered private identity is rejected.

## Final lineage

```text
288a27c032355d5d6d373b3e51b43897f2aa995b
  └─ 387667181aa47211f699084797e6c763f9d42197
      fix(identity): make CI authorization deterministic
      └─ 90a68c914a328e7a70530e8119a7027a06f619dd
          fix(hygiene): preserve scanner self-exemptions after core split
```

This feedback supersedes the earlier recommendation to rely on a local private-literals file in CI or to treat shell-only changes as sufficient.
