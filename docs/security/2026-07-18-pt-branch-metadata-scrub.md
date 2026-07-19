# PT Branch Metadata Scrub — 2026-07-18

> Scope: `docs/coordination-consolidation-plan-20260717` only.  
> Orama-system is explicitly deferred for a separate decision.

## Summary

The current PT PR branch carried private-identity labels in Git commit metadata
and a small number of commit bodies. The current tracked file tree was clean
before the rewrite.

The branch was rewritten in a disposable cleanroom clone with `git filter-repo`
using local-only replacement inputs generated from the operator-owned
forbidden-literal registry outside the repo. The actual forbidden values were
not written to this report, board notes, commit messages, memory, or tracked
files.

## Pre-Scrub Inventory

Final branch tip before scrub:

```text
66886ddaf3cce169b846effecfcabf56daf796b0
```

Metadata hits on the final upstream branch before scrub:

| Label | Count |
|---|---:|
| `owner_gmail` | 114 |
| `owner_name` | 114 |

Field counts before scrub:

| Field | Count |
|---|---:|
| `author_email` | 110 |
| `committer_email` | 103 |
| `body` | 6 |

Other checked surfaces:

| Surface | Result |
|---|---|
| Current tracked tree | 0 forbidden-label hits |
| Current branch `forbidden_attribution` metadata | 0 hits |

## Scrub Action

Applied branch-only history rewrite in a cleanroom clone:

```bash
git filter-repo \
  --force \
  --refs refs/heads/docs/coordination-consolidation-plan-20260717 \
  --mailmap ~/pt-owner-scrub.mailmap \
  --replace-message ~/pt-owner-scrub-replace-message.txt
```

The local-only filter files mapped private owner identity metadata to a neutral
operator identity and replaced private identity mentions in commit messages with
placeholder text.

The attribution audit policy was also updated to recognize the public-safe
Codex noreply identity and the neutral operator placeholder used by this scrub.
Private owner identity remains handled through the existing local-only owner
exception path, not by hardcoding private literals into tracked policy.

## Post-Scrub Verification

Scrubbed branch tip before this report commit:

```text
c5eac74fbdf230ba87de92e046f2f5bfa700bb5c
```

Post-scrub checks:

| Check | Result |
|---|---|
| `HEAD` commit metadata scan | 0 forbidden-label hits |
| Current tracked tree scan | 0 forbidden-label hits |
| 79-commit attribution audit window | 0 bad authors after allowlist update |

## Remaining Gap

Historical blob scanning across all refs exceeded the practical five-minute
time box during preflight. The current branch tip and current tracked tree are
clean for the targeted labels, but a future all-ref blob audit should use a
faster offline object index or a narrowed candidate-ref set before making an
all-history claim.

## Orchestration Notes

- Claude was notified through the PT coordination board before and after the
  rewrite.
- The final Claude-pushed tip `66886dda` was preserved as the scrub base.
- Orama-system history was not rewritten in this operation.
- The remote branch requires a force-with-lease push because the branch history
  was intentionally rewritten.
