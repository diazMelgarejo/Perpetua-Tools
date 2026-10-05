# Sites MCP audit, implementation and agent hand-off

Evidence date: 2026-10-05. Classification: AFRP Type C, Practitioner, Mode 2. This is a new v1 integration, not a revival of September PR branches or a migration into the independent v2 repositories. Reference: `docs/v2/references/ORAMASYS-MASTERY-v3.md`; governing authority: `docs/2026-05-14--UNIFIED-ABSORPTION-PLAN.md`. Source contract: `integrations/sites-mcp/SPECS.md` and PT `packages/prompt-workspace/SPECS.md`.

## Audit findings and consequences

| Evidence inspected at current main | Finding | Implementation consequence |
| --- | --- | --- |
| Orama `bin/mcp_servers/oramasys_orchestration_server.py` `_solve` / `_delegate` | Solve records `started`; delegation explicitly remains a stub. The transport is stdio. | Do not expose these as tools promising completed cloud work. New prompt preparation has a real, bounded completion contract. |
| PT `orchestrator/orama_mcp_client.py` | Launches stdio child; incomplete solve triggers HTTP fallback. | A browser/Worker cannot simply host this child process; portable contract removes process-launch overhead. |
| Orama `src/orama_system/api_server.py` | Python local inference endpoint depends on endpoint/hardware configuration. | No provider/gateway configured in this task; no invented inference result. |
| Orama local portal routes | Privileged configuration, lifecycle and LAN helpers exceed prompt workspace authority. | No generic URL, local execution, portal launch/stop or secret-changing MCP tool. |
| Sites Workers/D1 hosting | JavaScript request handlers and durable database fit; local Python/stdin does not. | Canonical PT module + Orama adapter + generated Workers Site, no Python dependency. |
| Attached `MCP-oramasys.md` literal steps 4, 5, 8, 10 | Review tools/UI; explicit approval before publish; private audience until change requested. | Register and save private review version. Never equate save/registration with deployment or plugin installation. |

## Architecture and complete vertical slice

PT owns compiler/schema/data operations. Orama consumes reviewed snapshots whose bytes must match PT before assembly. The generated Site receives these modules directly; it never imports a sandbox-specific checkout or fetches executable main-branch code at request time. UI → same MCP handler → PT validation/SQL → D1 → MCP structured result → UI is the implemented slice. Source provenance hashes accompany assembly. Version 1.0.0 applies to this new contract, not global repo versions.

Five tools: prepare (read), save (write), list (read), get (read), archive (write). Identity comes from Sites' authenticated gateway and never from arguments. All SQL includes owner identity; browser Origin is checked. Unauthenticated tool calls fail before touching storage. Discovery exposes no private records. Whole-body streaming limits avoid unbounded allocation; fields have UTF-8 byte bounds; pagination uses indexed owner/archived/ID keyset order, bounded to 50. List items contain metadata and 240-character previews; full contracts are fetched with get. UUID ordering is lexical, not chronological. No inference cost, provider roundtrip, RAG, local process launch or full-list scan is required for prompt construction.

Original prompt text is immutable. Compile, save, retry and get preserve whitespace, Unicode and CR/LF characters. The invariant concerns prompt text, not the wire serialization of JSON. Records use unique `(owner_id, request_key)` and never overwrite on retry. A changed payload with an existing key fails. Archive keeps originals accessible; it is retention, not erasure. The UI retains input and the retry key when a save response is uncertain. It distinguishes preview (no write) from structure-and-save. It confirms archive and reports failures without treating them as evidence of no remote side effect.

## Method, execution and gotchas

The 5-stage method informed context inspection, architecture, minimal tool surface, tests, and crystallization. CIDF's actual decision for cross-repo transformation/external integration was scripting with verification required: no field/editor/clipboard upload surface was available for source assembly. This decision was evaluated during final assembly/publishing preparation, after initial source edits; it is not retroactive proof that every insertion followed CIDF in advance. No multi-agent network execution is claimed.

Fresh isolated branches started from PT main `50192e07b7eb8c0bae04827b766e6a19a94d3902` and Orama main `65e120905dd63d8ff32155b35cd5f6f0d4cee12c`. Prior memory and lessons files were not rewritten. Initial feature tests failed before implementations existed; Origin rejection was separately observed failing before its fix. Real SQLite lifecycle tests then checked storage through the adapter, avoiding pure mock assertions. Worker assembly caught and fixed a relative-route import; TypeScript caught optional DB binding and unknown JSON response shape; lint caught effect-based loading structure. The starter adopted pnpm but retained a root npm lockfile: preserve the original outside active build inputs and retain exactly one intended manager/root lock. Full starter lint also inspected temporary validation copies with unrelated starter errors; application/DB lint is the recorded scoped check. Do not claim full starter lint passed.

Performance refinement found that a cursor OR prevented SQLite from seeking into the ID range. An EXPLAIN QUERY PLAN regression failed before replacing the OR with a conditional range query and passed afterward. A large-original regression failed before limiting list rows to metadata/240-character previews; full originals and contracts remain available through get. No historical memory was rewritten.

Registration source credentials can expire during a long session. Renew the same Site's credential; never create a second Site, expose a token, put it in shell arguments or persist it in source. Workflow credentials were passed through hidden stdin. Registration, source push, archive save and deployment are distinct checkpoints. A native source SHA or successful API acknowledgement is not sufficient remote-content evidence for GitHub: verify each returned blob against local Git hash, verify tree/path entries, fetch exact published branch head and compare content before reporting success. UTF-8 direct writes avoid the previous Base64 corruption path. If Base64 is ever needed, encode once or use raw chunk boundaries divisible by three (12,288 bytes), then prove byte size and exact Git blob hash before any tree/ref publication.

## Verification and performance evidence

- PT: seven Node 24 tests, including real SQLite owner isolation, retry/conflict, archive retention, schema reapplication, and complete bounded page traversal, indexed query-plan regression and limited list payloads.
- Orama: eight tests, including actual MCP-to-SQLite save/list/archive/get, unauthenticated rejection, malformed/oversize requests, notifications, foreign Origin and sanitized storage errors.
- Cross-repo source and schema snapshots were byte-identical under the check script and assembler.
- UI application/DB ESLint and TypeScript checks passed. D1 migration generation produced one additive table with two indexes; the Workers production build passed before final packaging. Packaging reruns the final build against current inputs.
- Local compile benchmark: 1,000 iterations, 3,200-byte original, p50 0.003769 ms and p95 0.015669 ms. These are sandbox compiler timings, not a production SLA, edge latency or database benchmark.
- Legacy Python pytest could not run: the environment has no pytest module. No legacy Python runtime files changed. Visual browser tooling was unavailable in this session; rendered desktop/mobile appearance is not claimed verified. Production two-identity gateway/D1 checks require private deployment.

## Requirement mapping and remaining production decisions

| Guide requirement | Delivered | Pending before claim of full readiness |
| --- | --- | --- |
| Persistent original + improved output | Deterministic structured contract, immutable original, D1 migration/store | Private production migration and authenticated readback |
| Tools derived from both v1 repositories | PT canonical contract/data ownership, Orama method/transport/UI | Review companion PR snapshot synchronization |
| Smallest useful read/write surface | Five schemas, annotations, isolation tests | Live client discovery/write confirmation behavior |
| Site UI and source links | Editor, contract result, pagination, archive, repo links | Owner UI review; rendered viewport review |
| Private until approved | Registered owner-private, no audience expansion | Explicit owner publish approval |
| Web/mobile/desktop plugin | Workers-compatible MCP build and declared capability | Publish, install/connect in supported clients; availability is platform-governed |
| Model-driven prompt improvement/full agent network | Not claimed or simulated | Reachable authenticated inference bridge and durable operation redesign |

A full inference workflow remains feasible, but not by pointing Workers at localhost or exposing the privileged portal. PT should own a durable operation state machine (pending/running/verified/failed/unknown), operation IDs and reconcile. An allowlisted HTTPS gateway must enforce endpoint-policy identity/SSRF checks, authentication, quotas, timeout/cancellation, retry budgets and result verification. Separate upstream failure from an unknown remote write outcome; never mark verified on a queued/stub response. Caller secrets require approved configuration. Fault injection must cover timeout after acceptance, duplicate retry, worker restart and late completion. Broad sharing also requires per-user quotas, abuse handling, retention/erasure and backup decisions. No service dependency or new credential is silently invented in these PRs.

## Coordination envelope for the next agent

```yaml
job: sites-mcp-v1-prompt-workspace
status: implementation-reviewed-locally-awaiting-owner-publish-review
owner: site-owning-agent
mode: AFRP-Type-C-Practitioner-Mode-2
source_authority:
  PT: packages/prompt-workspace
  Orama: integrations/sites-mcp
site_project_id: appgprj_6ac3eb5dccd0819182070b700ca3e377
constraints:
  - no merge without repository review
  - no Site deploy or audience change before explicit owner approval
  - no historical memory rewriting
  - no inferred model/network completion
handoff_inputs:
  - current paired PR heads and remote blob verification
  - Sites saved version and immutable archive
  - tool SPECS and source provenance hashes
next_actions:
  - review UI and five tools with owner
  - on approval deploy same private Site version
  - verify trusted authenticated identity and two-user isolation on private deployment
  - install generated plugin and demonstrate prepare then save/list
  - record any model bridge work as a separate approved production contract
```

Do not re-register the Site or manufacture a live URL. Use its saved identity and native deployment status. Do not merge the paired PRs or modify unrelated old PR bodies. Repository reviewers can validate independently; deployment remains gated by the attachment. Update this envelope with measured production evidence through an additive follow-up, preserving this audit.
