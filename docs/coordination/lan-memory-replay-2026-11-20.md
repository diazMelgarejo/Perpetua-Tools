# LAN memory replay and identity reconciliation — 2026-11-20

The operator directed that PT #516 be fixed first, then #517 be rebased and
replayed on top. The new base is
`305c555803f75e4844624f9aaba51d3e79956aa8`. The original #517 tip remains
`8e6082b35549daf4330deacf0ad02463dde1b34e`; it is preserved by the backup tag
`backup/pt517-before-replay-20261120` and this provenance record.

## History preservation

The two branches independently appended to the same byte-identical memory
snapshot, `dbcc1ab904342671b06781cef0b295690e5a4740`. Divergent suffixes were
not evidence of an edited historical row. Replay keeps the complete #516
prefix, then the complete original #517 suffix, then native review corrections.
No record is deduplicated away: order and duplicate observations remain intact.

The episodic file adds 20 original branch records and seven correction mirrors
after the #516 prefix. Semantic history adds 19 original branch records, seven
accepted corrections and 17 explicit identity migration records. Original
graduated candidate snapshots remain byte-identical. Derived Markdown is
regenerated from the resulting source, rather than merged by replacing a tail.

## Supersession and identity

PT recall establishes the existing rule: the latest row determines an ID's
status; a different accepted lesson may retire that ID through `supersedes`.
A provisional replacement does not retire accepted guidance. Rendering, recall
and review must respect that distinction.

The bounded native identity migration normalizes historical bare IDs without
newly accepting claims. Eleven currently effective accepted decisions retain
their exact reviewed content and metadata under canonical `lesson_` IDs, with
an accepted edge retiring the original identity. Six already-retired identities
get inactive historical canonical records; their old guidance is not revived.
The original accepted candidate status and prior semantic bytes remain intact.
Matching `key` and `name` fields normalize with the ID; original fields, exact
source-row hash and candidate-file hash remain in migration provenance.

An independently active provisional source refuses migration. Conflicting
canonical identities, changed source/candidate hashes, duplicate IDs and invalid
IDs also refuse. Every proposed row is validated before appending. A process
failure during appends can leave a complete prefix of the migration; validated
retry handles that prefix. Torn historical JSON refuses parsing and needs a
separate preservation procedure. This tool does not claim batch atomicity or
multi-writer safety on platforms where the existing semantic lock is unavailable.

## Review dispositions

The accepted corrections distinguish fleet-mode classification from delivery,
persisted token restoration from rotation, directional token support from shared
credentials, local storage from best-effort LAN forwarding, and observed
transport behavior from required fail-closed policy. They scope unavailable
external flush commands to unverified ownership, correct platform launchers,
mark contradictory pin history unknown, distinguish delivery acceptance from
content identity, and retain the TLS front end with its loopback upstream.
No credentials or new host evidence are introduced.

Focused migration, presence, recall, render, search, review and preservation
verification: 49 tests passed. The native episodic gate preserves all 1,592
base rows and adds 27 records. Identity migration preserves the effective
accepted claim multiset. Publication still requires a fresh remote lease and
the exact pinned stack base; this document is not a merge or activation receipt.
