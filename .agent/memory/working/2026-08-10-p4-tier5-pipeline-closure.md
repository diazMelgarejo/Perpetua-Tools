# 2026-08-10 — P4 governed Tier-5 pipeline closure

**Prior state:** the 2026-06-28 deferred backlog records `config/pipelines.yml`,
`PIPELINE_TIERED_ENABLED=0`, and governed Tier-5 spans as deferred work.

## Current decision

Close that gap without creating another router or provider client.

The existing ownership remains:

```text
frugality_router.py -> tier policy
        |
        v
gate.py -> canonical pre-dispatch decision
        |
        v
tiered_pipeline.py -> ordered Tier-5 stage execution
        |
        v
injected dispatcher -> existing provider-specific execution
```

## Why this shape

PT already has a canonical frugality gate and current paid models in
`config/models.yml`. It does not have one universal provider HTTP client that the
pipeline can safely own without duplicating existing execution paths.

Therefore the pipeline runner:

- validates configured aliases against current model-registry names;
- requires every configured model to be `frugality_tier: 5`;
- remains disabled unless `PIPELINE_TIERED_ENABLED=1`;
- calls `gate_permits(5, ...)` before any stage dispatch;
- preserves the existing offline and privacy-critical policy;
- delegates provider execution through an injected async callback;
- emits only governed metadata, never prompt content, to its JSONL trace;
- enforces deterministic stage order, dependency order, and token caps.

## Provider choice

The checked-in recipe uses current PT routing keys rather than stale historical
provider IDs:

- `fast` -> `glm-5.2`
- `strong` -> `claude-4-5-thinking`

Both are currently classified as Tier 5 in `config/models.yml`.

The runner is intentionally provider-agnostic. If the registry later points a Tier-5
alias at OpenRouter or another paid backend, the pipeline contract remains unchanged.
Credential presence alone never enables the feature.

## Acceptance

The focused tests cover:

- default-off behavior with zero dispatch;
- deterministic stage ordering;
- `input_from` context propagation;
- token-cap and dependency validation;
- Tier-5 model classification;
- offline hard denial;
- privacy denial plus the existing explicit override contract;
- prompt-free Tier-5 trace metadata;
- checked-in production config resolving to current Tier-5 models.
