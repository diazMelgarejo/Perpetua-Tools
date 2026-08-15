# Memory union repair — reconciliation record

This repair retains valid, distinct memory records while excluding malformed
tool output and duplicate semantic identifiers. The invalid source rows remain
verbatim in `MEMORY_UNION_INVALID_ROWS_2026-08-15.txt` for forensic review.

## Original import accounting

- Source-ref aliases inspected during the original import: 62
- Episodic rows before validation: 1367
- Episodic rows after validation: 1365
- Semantic rows before validation and identifier de-duplication: 1278
- Semantic rows after validation and identifier de-duplication: 1275

The four malformed rows were non-record tool output: two episodic and two
semantic. The remaining semantic-row reduction is one otherwise-valid row
whose identifier duplicated an already retained semantic record. It was not
an invalid tool-output row.

## Reconciliation verification

The original report used “conflict” for repeated presence without recording a
payload comparison. A fresh comparison of the 22 unique remote branch tips
available at reconciliation produced the following result:

- 1,275 semantic IDs observed; zero IDs had differing canonical JSON payloads
- 470 graduated-candidate filenames occurred on more than one branch tip
- all 470 repeated candidate payloads were byte-identical

Accordingly, repeated records are called overlaps, not conflicts. The two
candidate files not counted as overlaps occur only on the repair branch.
Source-ref aliases from the original 62-ref import may include multiple names
for the same underlying branch tip; this record intentionally does not infer
additional payload differences from aliases alone.

## Preservation and resolution policy

For a repeated semantic ID, retain one canonical JSON record only after a
structured payload comparison confirms equality. For a repeated candidate,
retain the canonical file when its payload is byte-identical across sources.
If future source refs reveal a divergent payload for either case, preserve the
variants with source commit IDs and content digests in a dedicated audit record
before selecting a canonical form; do not silently overwrite or label equality
as a conflict.
