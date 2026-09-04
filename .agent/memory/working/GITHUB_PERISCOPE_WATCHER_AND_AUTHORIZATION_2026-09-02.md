# Periscope watcher repair and GitHub authorization lessons

## Facts preserved

### Empty-commit proof

Periscope PR #49 later demonstrated the exact empty-commit failure mode.
GitHub's raw comparison establishes that `faf515e4` has parent
`214b0c03`, is one commit ahead, and has an empty changed-file list. In
contrast, `214b0c03` contains the real 45-line watcher regression. The
same subject line on both commits is not evidence of duplicated work; the
tree/diff proof is authoritative. Treat `faf515e4` as a publication-record
failure: it adds history but no content.

Before declaring a commit published, compare `HEAD^..HEAD` and require at
least one changed file when the task claims a code or documentation change.
For API publication, verify the returned commit tree differs from its
parent's tree and that the expected path/blob is present on the target ref.
Do not use commit count, subject, or a successful HTTP response as proof of
content publication.

The Windows timeout in Periscope's watcher tests was a real deadlock, not a
test-timeout problem. A remove or rename event had already invalidated the
native fsnotify watch; calling `Remove` again from the event loop could block
on Windows and prevent `Stop` from joining that loop. The repair removes only
that redundant native removal while retaining ownership cleanup and runtime
watch-budget reclamation. A focused regression proves that no second native
removal occurs and that the ownership ledger and budget are still repaired.

The repair belongs on Periscope PR #49 because that discovery branch is the
evidence record. It was rebased onto that PR's exact head and published there.
It must not be merged merely because the repair was published: discovery,
publication, review, and merge authorization are distinct decisions.

## Authorization diagnosis procedure

Never infer GitHub write capability from a displayed user role or repository
metadata. The connector acts as a GitHub App installation identity, not as the
linked repository owner. Probe the exact endpoint needed by the task:
repository contents, pull-request metadata, review-thread resolution, and
merge have distinct authorization checks.

In this incident, the installation token received `403 Resource not
accessible by integration` from the Contents-write endpoint and the
collaborator-permission endpoint. Repository metadata also displayed
`admin`/`push`, but those fields did not authorize either failing request and
must not be used as endpoint-specific evidence. The responses' token type and
endpoint are known; their `X-Accepted-GitHub-Permissions` headers were not
captured, so the exact missing App permission is unproven.

A fine-grained PAT successfully performed Git/Contents writes, but
`PATCH /repos/diazMelgarejo/periscope/pulls/49` returned `403 Resource not
accessible by personal access token`. This proves only that the PR-metadata
update was denied. No merge-endpoint request was made after the operator said
not to merge, so this incident does not prove merge permission was absent.
For future 403s, record token type, exact method and endpoint, status/message,
and `X-Accepted-GitHub-Permissions` before drawing a scope conclusion.

## Durable operating rules

- Treat any token pasted into chat as exposed: never echo, log, commit, or
  place it in a PR body; revoke or rotate it before further privileged use,
  then obtain any replacement through a secure channel.
- Do not use a token to broaden task scope. Use it only for the explicitly
  authorized repository and operation.
- Verify the resource changed by each write: branch content/blob and head SHA
  for content writes; PR metadata for description changes; review state for
  thread resolution; and merged state plus target-branch content for merges.
- Keep PR descriptions truthful. If a discovery branch gains a production
  repair, its description must be corrected before review; inability to edit
  metadata is a documented authorization blocker, not permission to merge.
- `save`, `commit`, `push`, `publish`, or `fix` never authorizes a merge.
  Merge only on an explicit instruction and after current-head verification.

## Reusable verification sequence

1. Rebase the repair onto the target PR head, not merely its base branch.
2. Run `git diff --check` and the focused regression suite.
3. Publish source and test as separate, auditable commits when practical.
4. Fetch the remote PR head and confirm both changes are present.
5. Inspect unresolved review threads and current checks.
6. Stop at the first missing authorization boundary and describe the exact
   required GitHub scope.
