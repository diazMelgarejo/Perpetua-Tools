# Episodic memory: preserve historical bytes

`.agent/memory/episodic/AGENT_LEARNINGS.jsonl` is an append-only historical log.
Object equality is necessary but insufficient: the previous complete byte stream
must be a prefix of the proposed stream. Preserve order, duplicate records,
Unicode spelling, escape sequences, whitespace and line endings.

## Check before publication

Pin the PR's actual base and head commits, fetch both, then run:

```bash
python3 scripts/review/check_episodic_append_only.py \
  --base "$BASE_SHA" --head "$HEAD_SHA"
```

Use `--worktree` instead of `--head` for a deliberate local preview. It is not
remote-content evidence. After publishing, fetch the exact remote branch head
and run the committed-revision check again. An API acknowledgement or returned
blob SHA alone does not establish the branch's contents.

The checker reports counts, byte lengths, commit identities and SHA-256 hashes;
it never prints memory records. It rejects missing/nonregular/executable files,
truncation, reordered or rewritten prefixes, malformed UTF-8/JSON additions,
duplicate JSON keys in additions and incomplete final records. It allows
unchanged history and valid initial records when the base has no log.
Existing duplicate records are history, not an invitation to deduplicate.

## PR #391 byte restoration

The audited base is `f2ce7a450cb02d27c5f48e40eb7c2f4192b30299`.
The reviewed head before repair is `76fbc96aa73ff3e69c0c0a9155636b6b244ae739`.
Base: 811 lines, 778,032 bytes, SHA-256:

`a3516c147ede3ae6b142d66cca6bf97cb6a72240c7df447d9c36b89e0bb24e0d`

The reviewed head had 817 lines. Eighteen historical lines starting at line 794
were reserialized while their JSON objects remained equal. The repair restores
the original base bytes and appends the six existing new lines without parsing
and serializing them again. Net PR history is therefore six additions.

For this authorized repair, compare against the PR base above, not the previous
damaged head. Comparing against the damaged immediate parent correctly detects
the restoration as a change; that is not the net-PR preservation invariant.
Do not treat this incident-specific restoration as a general rewrite exception.

## Corrections and processing tools

Use native memory capture/review tooling to append a new record that explicitly
references the superseded record and explains the correction. Do not patch or
reserialize old records to improve wording. Regenerating a derived semantic view
is distinct from rewriting its episodic source.

Processing paths such as `scripts/auto_dream.py` can sanitize, decay or reserialize
records. Their output must not replace this tracked history. Use working copies
or separately defined projections, and review additive corrections before
publication. This change adds a boundary guard; it does not redesign those
processors or certify every memory-writing path as append-only.

If an old record contains sensitive material requiring removal, stop normal
publication and obtain a separately reviewed incident procedure. A normal
supersession record cannot remove exposed historical content.

## CI and enforcement boundary

`.github/workflows/episodic-append-only.yml` runs independently on every PR to
main, merge-group check and main push, without path filters. PR checks compare
event base/head; merge groups compare their supplied base/head; main pushes
compare before/after. Missing Git objects and zero/unknown revisions fail closed,
rather than choosing a convenient fallback base. A complete checkout is required.

The required-check name is `Episodic append-only integrity`. Repository operators
must add it to branch/ruleset requirements to make it a merge gate. Adding the
workflow alone does not configure that server policy. Protect checker/workflow
changes through trusted review: a repository-controlled check is not tamper-proof
against an actor authorized to change or bypass it. Main-push checks detect a
bad destination after the fact; they cannot undo a merge.

Run the hermetic checker suite with:

```bash
python3 -m unittest discover -s tests -p test_episodic_append_only.py -v
```

No new Python package is needed. This focused suite supplements the repository's
existing full CI and reviewer gates; it does not replace them.
