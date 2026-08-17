# Model Registry Provenance Gate

Status: implemented with the Tier-5 transport composition work on this branch.
Publication remains blocked until the independent review gate recorded in the
[current operational disposition](2026-08-14-operational-work-disposition.md)
is closed. This document records configuration provenance, not release
approval.

`config/models.yml` has two distinct identifiers:

- `name` is a stable PT routing or local-deployment alias.
- `api_model` is the exact string sent to an external provider. Every cloud
  entry must carry a `provenance` record with the matching `source_model_id`,
  a direct HTTPS official source URL, and the date the source was checked.

`scripts/check_model_ids.py` validates that contract from configuration. It no
longer duplicates an independent hardcoded catalogue, so upgrading a model is
one reviewable configuration change: update the provider wire ID, source
record, tests, and any live default that emits the old identifier. The native
Tier-5 transport repeats the provenance check at execution time and fails
closed if an eligible cloud target is not documented.

## Verified provider API IDs

| PT routing key and wire ID | Provider evidence | Transport status |
| --- | --- | --- |
| `glm-5.2` | [BigModel chat completions](https://docs.bigmodel.cn/api-reference/%E6%A8%A1%E5%9E%8B-api/%E5%AF%B9%E8%AF%9D%E8%A1%A5%E5%85%A8) documents `glm-5.2`, the bearer header, and the native endpoint. | Tier-5 native adapter |
| `sonar-reasoning-pro` | [Perplexity Sonar Reasoning Pro](https://docs.perplexity.ai/docs/sonar/models/sonar-reasoning-pro) | Existing Perplexity path; not part of the new native Tier-5 recipe |
| `claude-sonnet-5` with `output_config.effort=medium` | [Anthropic model IDs](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions) establishes the current dateless ID scheme, including `claude-sonnet-5`. | Tier-5 native adapter |
| `grok-4.5` | [xAI Grok 4.5](https://docs.x.ai/developers/grok-4-5) | Cataloged as Tier-6; intentionally no adapter until a separately reviewed use case exists |

## Local models and aliases

Local model entries are deployment selection keys, not external provider wire
IDs. Their model-host provenance stays with the configured `hf_repo` or local
runtime catalog. `qwen3-30b-autoresearch-critic` is a local deployment alias;
its availability must be verified by the configured runtime's model-list
endpoint, not guessed as a vendor API model ID.

## Change procedure

1. Check the provider's official current model/API documentation.
2. Update one `models.yml` entry with `api_model` and matching provenance.
3. Update live dispatch defaults and focused tests, never historical evidence.
4. Run `python3 scripts/check_model_ids.py` and provider transport tests.
5. Review the model change with the same gate as any other external egress
   change: auth, cost, host allowlist, and failure redaction.
