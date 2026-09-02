# Periscope watcher repair and GitHub authorization lessons

## Facts preserved

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

Never infer GitHub write capability from a displayed user role. Probe the
exact API boundary needed by the task: repository contents, pull-request
metadata, review-thread resolution, and merge are separate permissions.

In this incident, the GitHub connector authenticated as the repository owner
and reported admin/push repository metadata, yet Contents writes returned
`403 Resource not accessible by integration`. The same connector also failed
the collaborator-permission endpoint. This identifies an installation-token
scope limitation, not branch protection or a repository-code failure.

A backup PAT successfully wrote the two Contents commits but returned
`403 Resource not accessible by personal access token` for PR metadata. Thus,
PAT repository-content scope does not imply Pull Requests write or merge
scope. Diagnose and report that boundary precisely; do not retry unrelated
operations or claim that a PR description/merge changed.

## Durable operating rules

- Treat any token pasted into chat as exposed: never echo, log, commit, or
  place it in a PR body; rotate it after use.
- Do not use a token to broaden task scope. Use it only for the explicitly
  authorized repository and operation.
- Verify remote state after each API write by fetching the exact branch and
  checking the intended source/test markers and head SHA.
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
