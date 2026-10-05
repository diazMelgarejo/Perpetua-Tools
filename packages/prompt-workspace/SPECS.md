# Prompt workspace specifications

## 1. Intent and assumptions

Persist original prompts and explicitly structured outputs for authenticated Sites users.
Deterministic contract construction is the first deployable workflow; model inference is a
separately configured extension. No full-agent completion claims. Node/Web standard APIs only.
Version 1.0.0 is the module contract, not the root repository version.

## 2. Authority and architecture

PT owns schema, compiler, and SQL operations; Orama owns stateless MCP transport and UI. Consumers
pin exact reviewed bytes. A trusted hosting gateway authenticates and replaces the user-ID header.
Deployments exposing a raw Worker accepting arbitrary caller identity are forbidden. No connection
from Sites to a privileged local portal is part of this implementation.

## 3. Artifacts and invariants

Original text remains character/UTF-8-byte equivalent across compile, JSON roundtrip, SQLite
storage, and retrieval; caller transport bytes are not preserved (JSON escaping is not original
prompt content). UTF-8 valid strings are expected. Additive insert only, collision checked, archived
originals readable. SQL is parameterized and owner-scoped on every statement. List items expose only
metadata and a 240-character original preview, with indexed `(created_at, id)` cursor seeks (newest
first). No list/export-all and no arbitrary URL tool. Record IDs/request keys are limited to 128
safe characters; owner to 512 characters; fields and saved originals to 32,768 UTF-8 bytes; saved
structured text to 163,840 UTF-8 bytes.

## 4. Acceptance and tests

Run Node SQLite contract tests. Two users cannot read or archive one another's records. Identical
retries return the existing record; changed retries cannot replace it. A paginated traversal of
unchanged data has no omission or duplicate. Invalid owner/input/limit fails before writing. Schema
reapplication on an existing SQLite database retains records.

## 5. Risks and limits

Storage is not encrypted by this module; platform privacy, authentication, backups, retention and
quota controls remain deployment responsibilities. Archive is retention, not a legal erasure
workflow. Request rate/concurrency is governed by hosting; per-user quota and billing controls are
prerequisites before broad sharing. No model endpoint is configured. No distributed task queue, SSE
subscriptions, network-agent workflow, or local model execution is claimed.

## 6. Actions and rollout

Review PT and Orama PRs independently, then assemble with snapshot parity checks. Review private
Site/tools before publish. Test real authenticated isolation and D1 migration on the deployed
private Site before changing audience. Any inference extension needs an allowlisted reachable
gateway, endpoint identity/SSRF policy, bounded timeouts, cancellation, stable operation IDs,
uncertainty reconciliation, result verification and a separately approved credential configuration.
It must preserve original records and distinguish pending/failed/verified output.
