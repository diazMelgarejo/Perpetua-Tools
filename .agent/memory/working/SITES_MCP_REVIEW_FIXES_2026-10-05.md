# Sites MCP review fixes (additive hand-off)

Evidence date: 2026-10-05. Scope: review findings on PT #423 and Orama #382. This note is additive;
the earlier implementation memory and all historical JSONL records are unchanged except where the
earlier file's own ordering statements became false (corrected in place, same PR).

## What changed and why

| Finding | Fix | Evidence |
| --- | --- | --- |
| History used `ORDER BY id`, and ids are random UUIDs | Order and cursor use `(created_at, id)`; cursor is `<created_at>\|<id>` and is validated | Test inserts an old record with the largest id and a same-millisecond pair |
| Cursor OR scan risk | Row-value range `(created_at, id) < (?, ?)` served by `prompt_records_owner_history` | Query-plan test: index used, no temp B-tree |
| Save did not bound stored bytes | `save` checks original (32,768 UTF-8 bytes, non-blank) and improved (163,840 bytes) | Multi-byte test: 16,385 two-byte characters rejected, 16,384 accepted |
| Markdown lint (MD013) | Paragraphs reflowed at 100 columns | Line-length scan |
| Checkout token reachable by PR tests | `persist-credentials: false` | Workflow diff |

## Gotchas

- The index was renamed (`prompt_records_owner_history`) rather than redefined under its old name,
  because `CREATE INDEX IF NOT EXISTS` silently keeps an already-applied old definition.
  Nothing is deployed yet, so no migration ledger entry exists.
- Cursor format changed from a bare id. Unreleased, so no compatibility shim.
- Output remains a deterministic structured contract. There is no inference, and none is claimed.

## Next actions

- Orama re-pins the byte-identical snapshot of `src/index.mjs` and `schema.sql`.
- Deployed authentication, two-identity isolation and D1 migration remain unverified.
