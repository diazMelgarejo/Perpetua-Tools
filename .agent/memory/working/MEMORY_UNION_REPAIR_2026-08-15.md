# Memory union repair — reconciliation record

This repair retains valid, distinct memory records while excluding malformed
tool output and duplicate semantic identifiers. The invalid source rows remain
verbatim in `MEMORY_UNION_INVALID_ROWS_2026-08-15.txt` for forensic review.

## Original import accounting

- The parent repair commit records 62 source-ref aliases.
- Episodic rows before validation: 1367.
- Episodic rows after validation: 1365.
- Semantic rows before validation and identifier de-duplication: 1278.
- Semantic rows after validation and identifier de-duplication: 1275.

The four malformed rows in `MEMORY_UNION_INVALID_ROWS_2026-08-15.txt` were
non-record CLI tool-runner pagination warning banners (`Warning: truncated output...`,
`... N bytes omitted ...`) emitted during large-output command executions and
quarantined by strict JSON validation. The parent commit does not retain an
alias-to-tip map, source-order manifest, duplicate identifier, or compared payloads for the
additional semantic reduction. Consequently, this report does not claim first-occurrence
retention or complete 62-alias coverage; those facts require a new union run from a preserved
ref inventory.

The checked-in semantic corpus now contains 1,276 unique IDs: the 1,275-row
repair snapshot plus `lesson_5869d08b2179`, a later continuation that preserves
the D2–D5 decisions independently of the revised D1 lesson. The episodic
corpus contains valid post-snapshot entries (including line 1366 `proactive-recall`,
where truncated nested detail JSON was closed and normalized to valid JSON).

## Reconciliation verification

The original report used “conflict” for repeated presence without recording a
payload comparison. A fresh comparison of the 22 unique remote branch tips
visible at reconciliation produced the following limited result:

- 1,275 semantic IDs observed; zero IDs had differing canonical JSON payloads
- 470 graduated-candidate filenames occurred on more than one branch tip
- all 470 repeated candidate payloads were byte-identical

Accordingly, repeated records are called overlaps, not conflicts. The two
candidate files not counted as overlaps occur only on the repair branch.
This 22-tip check is not evidence of the parent commit's 62-alias coverage.
No local-ref inventory or alias-to-tip mapping survived in the checked-in
snapshot, so no additional payload differences or preservation coverage are
inferred from the original alias count.

## Preservation and resolution policy

For a repeated semantic ID, retain one canonical JSON record only after a
structured payload comparison confirms equality. Record the identifier, source
order, retained source, competing payload digest, and ref-to-tip mapping in the
union audit. For a repeated candidate, retain the canonical file when its
payload is byte-identical across sources. If future source refs reveal a
divergent payload for either case, preserve the variants with source commit IDs
and content digests before selecting a canonical form; do not silently
overwrite or label equality as a conflict.
