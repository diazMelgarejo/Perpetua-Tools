# Portable prompt workspace (v1)

PT owns the portable prompt contract and persistent record operations. Orama consumes a reviewed, byte-identical snapshot for its Sites adapter. This module has no Python process, model provider, LAN access, RAG, or orchestration dependency. It is independent of the future v2 repositories.

## Contract

`compilePrompt({original, role?, goal?, constraints?, output_format?})` returns `{original, improved, mode, version}`. `mode` is `structured-contract`: visible defaults and user-supplied text form a role/context, goal/task, constraints, output-format contract. It does **not** infer improvements or certify execution of the full Oramasys method. Original Unicode and CR/LF characters are retained without trimming or normalization. Each input field is bounded to 32,768 UTF-8 bytes; unknown fields fail.

`new PromptStore(D1Binding)` provides `save(owner, requestKey, record)`, `get(owner,id)`, `list(owner,{limit,before})`, and `archive(owner,id)`. The host must supply a trusted authenticated owner, never a tool argument. Records are private per owner. Save retries use `(owner,request_key)` uniqueness; changed content with that key fails instead of overwriting history. Archive is reversible in storage and never deletes original text; restoring an archived record is not yet exposed as a tool. Get can read archived records. Listing returns metadata and a 240-character `original_preview`, never a full contract; use get for full text. Listing defaults to 20, caps at 50, and uses lexical UUID keyset order (not chronological order). It is bounded, deterministic, and not a transactionally frozen snapshot during concurrent edits.

Apply `schema.sql` to a fresh SQLite/D1 database, or use a migration ledger in a deployment. Do not rewrite already-applied migrations. Version/source changes require explicit consumer snapshot review, not runtime downloading from a moving main branch. Unknown save outcomes retain the same request key; never claim failure implies no write.

## Verification

Node 24: `node --test packages/prompt-workspace/tests/*.test.mjs`. Tests execute real in-memory SQLite with a D1-compatible facade, covering source-text preservation, invalid input, isolation, retry conflicts, archive retention, cursor bounds and page traversal. This is not proof of Cloudflare deployment, edge authentication, or production latency.

See `SPECS.md` and `.agent/memory/working/SITES_MCP_IMPLEMENTATION_2026-10-05.md` for ownership and operational hand-off.
