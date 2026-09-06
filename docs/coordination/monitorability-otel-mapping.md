# Monitorability to OpenTelemetry Mapping — v1

The Perpetua-Tools v1 handoff is a redacted, local evidence contract. It does
not install an OTel SDK, collector, exporter, database, or network path.

| Packet path | OTel field | Projection rule | v1 rationale |
| --- | --- | --- | --- |
| `otel.operation_name` | `gen_ai.operation.name` | local/redacted only | identifies agent, workflow, plan, or tool operation |
| `otel.provider_name` | `gen_ai.provider.name` | local/redacted only | records client instrumentation’s best-known provider |
| `otel.agent_id` | `gen_ai.agent.id` | local/redacted only | stable logical agent identity |
| `otel.agent_name` | `gen_ai.agent.name` | local/redacted only | optional display identity |
| `otel.agent_version` | `gen_ai.agent.version` | local/redacted only | optional immutable version |
| `otel.request_model` | `gen_ai.request.model` | local/redacted only | exact configured model when known |
| `otel.conversation_id` | `gen_ai.conversation.id` | local/redacted only | only a genuine application conversation ID |
| `phylax.*` | `oramasys.phylax.*` | allowlisted audit projection | namespaced developing Phylax semantics |
| `integrity.redacted_manifest_sha256` | `oramasys.evidence.manifest_sha256` | allowlisted audit projection | redacted evidence correlation only |

Never project prompts, messages, system instructions, tool definitions, raw
tool payloads, outputs, secrets, raw reasoning, sealed references, capability
grant IDs, or fabricated correlation values. In particular, do not use a trace
ID/content hash as `gen_ai.conversation.id` or a host hash as `server.address`.

The v2 adapter reviews this mapping when developing OpenTelemetry GenAI
conventions change. Full migration: [Orama v2 Part 1](https://github.com/diazMelgarejo/orama-system/blob/main/docs/v2/references/phylax-monitorability-part-1-v1-evidence-contract.md).
