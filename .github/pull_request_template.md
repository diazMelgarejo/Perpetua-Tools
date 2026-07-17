<!-- Read CONTRIBUTING.md before requesting review. Use a concise,
     descriptive title (Conventional Commits style, e.g. fix(memory): ...).
     Answer what applies; write N/A with a short reason for the rest.
     These prompts inform reviewers — they do not replace the repository's
     documented merge requirements. -->

## Summary

<!-- What changed and why, in your own words — not the title repeated. -->

## Related issue, plan, or decision

<!-- Closes #123 / References <link> / N/A -->

## Verification and evidence

<!-- The exact tests, commands, or manual checks you actually ran, and their
     result. Prefer a focused test or programmatic check over "looks right".
     If the fix was found via real usage rather than a failing test, exercise
     the real path once and check the exact invariant that was broken. -->

- [ ] `python3 scripts/review/repo_hygiene.py .` passes
- [ ] Relevant tests run (`python3 -m pytest ...`) — paste the summary line

## Risk, compatibility, and rollout

<!-- User/operator impact, Mac/Windows differences, migration, rollback, or N/A. -->

## Security review

- [ ] I considered new or changed auth, input, secrets, and network boundaries.
- [ ] I did not add credentials, tokens, or workstation-specific paths to tracked files.
- [ ] I read [`SECURITY.md`](../SECURITY.md) where this change affects it.
- [ ] *N/A:* no security-relevant surface (explain below if unclear).

## Checklist

- [ ] This PR is one logical unit of work.
- [ ] Tests were added or updated when behavior changed.
- [ ] Documentation was updated where users, operators, or future contributors need it.
- [ ] Commit identity matches `.github/AUTHORIZED_CONTRIBUTORS.md`; AI assistance is `Co-authored-by`, not author.
- [ ] Any `.agent/memory/` change went through the memory tooling (not hand-edited JSONL), or the invariant was verified programmatically and noted below.
- [ ] This PR is ready for review, or it is marked draft.

## Optional: knowledge capture

<!-- ADR, runbook, skill, changelog, .agent/memory lesson, or why no update
     is needed. Promote repeated, well-evidenced lessons into durable policy;
     leave one-off observations local. -->

## Optional: cross-repository or vendor-overlay impact

<!-- orama-system / ECC / autoresearch coupling, or a vendor/ submodule and its
     blended .agent/ overlay: upstream pin, local intent, and how an operator
     re-verifies the surviving behavior. See scripts/git/agentic-stack-vendor.md
     for the overlay-catalog model. N/A otherwise. -->

## Optional: integration or conflict-resolution note

<!-- If this PR resolved conflicts, describe the synthesized result and any
     behavior deliberately retained from each side (append-only logs are
     union-merged; never silently drop one side). -->

## Additional context

<!-- Screenshots, performance data, alternatives considered, or follow-ups. -->
